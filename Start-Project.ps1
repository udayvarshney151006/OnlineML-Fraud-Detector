param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimeRoot = (Join-Path $projectRoot '.runtime') + '\'
$runDirectory = Join-Path $projectRoot '.local-run'
$statePath = Join-Path $runDirectory 'processes.json'
$state = @{}

function Get-ProcessIdentity([int]$processId) {
    $runningProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $runningProcess) { return $null }
    try {
        $identity = [pscustomobject]@{
            pid = $runningProcess.Id
            executable = $runningProcess.Path
            createdTicks = $runningProcess.StartTime.ToUniversalTime().Ticks.ToString()
            commandLine = $null
        }
        try {
            $cimProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $processId) -ErrorAction Stop
            $identity.commandLine = $cimProcess.CommandLine
        } catch { }
        return $identity
    } catch { return $null }
}

function Get-OwnedProcess($entry, [string]$role) {
    if (-not $entry -or -not $entry.pid -or -not $entry.createdTicks) { return $null }
    $processInfo = Get-ProcessIdentity ([int]$entry.pid)
    if (-not $processInfo -or -not $processInfo.executable) { return $null }
    $executable = $processInfo.executable
    $isProjectPython = $executable -ieq $pythonPath -or (
        $executable.StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($executable) -ieq 'python.exe'
    )
    if (-not $isProjectPython) { return $null }
    if ($processInfo.createdTicks -ne [string]$entry.createdTicks) { return $null }
    # Exact executable and creation time identify the process even when CIM is restricted.
    if ($processInfo.commandLine) {
        $commandLine = [string]$processInfo.commandLine
        if ($commandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $null }
        if ($role -eq 'api' -and $commandLine -notmatch '-m\s+uvicorn\s+server:app\s+--app-dir') { return $null }
        if ($role -eq 'dashboard' -and ($commandLine -notmatch '-m\s+streamlit\s+run\s+' -or $commandLine -notlike '*view.py*')) { return $null }
    }
    return $processInfo
}

function Test-Port([int]$port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne(300)) { return $false }
        $client.EndConnect($connection)
        return $true
    } catch { return $false } finally { $client.Dispose() }
}

function Save-State {
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Start-Component([string]$role, [int]$port, [string[]]$arguments) {
    $entry = $state[$role]
    if (Get-OwnedProcess $entry $role) {
        Write-Host ('Reusing project ' + $role + ' (PID ' + $entry.pid + ').')
        return
    }
    if (Test-Port $port) {
        throw "Port $port is already in use by another process. Close that application, then try again."
    }
    $argumentLine = ($arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $process = Start-Process -FilePath $pythonPath -ArgumentList $argumentLine -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDirectory "$role.stdout.log") -RedirectStandardError (Join-Path $runDirectory "$role.stderr.log")
    $processInfo = Get-ProcessIdentity $process.Id
    if (-not $processInfo) { throw "$role stopped during startup. See .local-run\$role.stderr.log." }
    $state[$role] = @{ pid = $process.Id; createdTicks = $processInfo.createdTicks }
    Save-State
    Write-Host ('Started project ' + $role + ' (PID ' + $process.Id + ').')
}

function Test-Ready([string]$url) {
    try { return (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200 } catch { return $false }
}

try {
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'The project environment is missing: .venv\Scripts\python.exe.' }
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    if (Test-Path -LiteralPath $statePath) {
        $savedState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        foreach ($property in $savedState.PSObject.Properties) { $state[$property.Name] = $property.Value }
    }
    # Both applications stay on this laptop. Streamlit inherits the telemetry setting.
    $env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
    $env:PYTHONUTF8 = '1'
    Start-Component 'api' 8000 @('-m', 'uvicorn', 'server:app', '--app-dir', $projectRoot, '--host', '127.0.0.1', '--port', '8000')
    Start-Component 'dashboard' 8501 @('-m', 'streamlit', 'run', (Join-Path $projectRoot 'view.py'), '--server.address', '127.0.0.1', '--server.port', '8501', '--server.headless', 'true', '--browser.gatherUsageStats', 'false')
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $ready = $false
    do {
        if (-not (Get-OwnedProcess $state['api'] 'api')) { throw 'The API stopped. See .local-run\api.stderr.log.' }
        if (-not (Get-OwnedProcess $state['dashboard'] 'dashboard')) { throw 'The dashboard stopped. See .local-run\dashboard.stderr.log.' }
        $apiReady = Test-Ready 'http://127.0.0.1:8000/'
        $dashboardReady = Test-Ready 'http://127.0.0.1:8501/_stcore/health'
        $ready = $apiReady -and $dashboardReady
        if (-not $ready) { Start-Sleep -Milliseconds 500 }
    } until ($ready -or [DateTime]::UtcNow -ge $deadline)
    if (-not $ready) { throw 'Startup did not finish within 30 seconds. See the logs in .local-run, then use Stop-Project.cmd before retrying.' }
    Write-Host 'Dashboard: http://127.0.0.1:8501'
    Write-Host 'API documentation: http://127.0.0.1:8000/docs'
    Write-Host 'Use Stop-Project.cmd to stop these project processes.'
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8501' }
} catch {
    Write-Host ('Could not start the project: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Use Stop-Project.cmd to stop any project process that was started.'
    exit 1
}
