$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimeRoot = (Join-Path $projectRoot '.runtime') + '\'
$statePath = Join-Path $projectRoot '.local-run\processes.json'

try {
    if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'No launcher-managed project processes are recorded.'; exit 0 }
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($role in @('dashboard', 'api')) {
        $entry = $state.$role
        if (-not $entry -or -not $entry.pid -or -not $entry.createdTicks) { continue }
        $processInfo = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
        if (-not $processInfo) { continue }
        $executable = [string]$processInfo.Path
        $commandLine = $null
        try {
            $cimProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$entry.pid) -ErrorAction Stop
            $commandLine = $cimProcess.CommandLine
        } catch { }
        $isProjectPython = $executable -ieq $pythonPath -or (
            $executable.StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase) -and
            [IO.Path]::GetFileName($executable) -ieq 'python.exe'
        )
        $matchesRole = $true
        if ($commandLine) {
            $matchesRole = $commandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
            if ($role -eq 'api') { $matchesRole = $matchesRole -and $commandLine -match '-m\s+uvicorn\s+server:app\s+--app-dir' }
            else { $matchesRole = $matchesRole -and $commandLine -match '-m\s+streamlit\s+run\s+' -and $commandLine -like '*view.py*' }
        }
        $matchesCreation = $processInfo.StartTime.ToUniversalTime().Ticks.ToString() -eq [string]$entry.createdTicks
        if ($isProjectPython -and $matchesCreation -and $matchesRole) {
            # Windows virtual environments can launch a runtime child process.
            # Stop only the verified launcher process and its descendants.
            & taskkill.exe /PID ([int]$entry.pid) /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw ('Could not stop project ' + $role + ' (PID ' + $entry.pid + ').') }
            Write-Host ('Stopped project ' + $role + ' (PID ' + $entry.pid + ').')
        } else {
            Write-Host ('Left PID ' + $entry.pid + ' alone because it does not match the recorded project process.')
        }
    }
    Remove-Item -LiteralPath $statePath
} catch {
    Write-Host ('Could not finish stopping the project: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
