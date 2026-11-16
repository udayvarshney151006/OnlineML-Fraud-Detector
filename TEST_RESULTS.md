# Verification results

Date: 16 November 2026. Platform: Windows x64. Runtime: private Python 3.12.16; River 0.27.0; Streamlit 1.67.0. Exact packages: `requirements-local.lock`.

## Executed checks

| Check | Actual execution and result |
| --- | --- |
| Dependency installation | The earlier laptop setup executed `uv venv --python 3.12 --managed-python --seed .venv` and `uv pip install --python .venv/Scripts/python.exe -r requirements.txt`. Installation completed. The installed environment is reused for this adaptation. |
| Dependency consistency | Executed `.tools/uv.exe pip check --python .venv/Scripts/python.exe`: all installed packages compatible (53 inspected). |
| Data preparation | Earlier setup executed `.venv/Scripts/python.exe split_data.py`. This pass independently checked the 31-column schema, chronological order and exact equality of the split CSVs to the original slices. Raw: 284,807 rows/492 frauds. Prefix: 142,403/269. Suffix: 142,404/223. |
| Full pretraining | Earlier setup executed `.venv/Scripts/python.exe -u pretrain.py`: completed all 142,403 historical rows, including 269 frauds, in 79.6 seconds. This pass loaded the pickles and verified HAT, ARF and the scikit-learn Pipeline types. All primary model files exist. Training code is unchanged. |
| Paced stream | Earlier setup executed `payment_edge.py --server http://127.0.0.1:8000 --rows 1000 --delay 0.01 --feedback-delay 0`. The API completed 1,000 transactions with no prediction/feedback errors. Streaming code is unchanged. |
| Turbo stream | This pass executed `boost.py --server http://127.0.0.1:8000 --rows 1000`. Verified the backend transaction count increased by exactly 1,000, independently of the CLI's summary. |
| Drift injection | This pass executed `boost.py --server http://127.0.0.1:8000 --rows 10000 --drift --drift-start 1500 --drift-len 800`. Verified exactly 10,000 additional completed API transactions. The simulator reported 141 fraud labels during this run. |
| ADWIN and replay | After the live runs, the API had 12,000 cumulative transactions, 17 cumulative ADWIN events, a 100/100 fraud buffer and 1,184 replays. The latest replay contained original and augmented features. These are observed run values, not benchmark accuracy claims or proof that every event was caused by the injected interval. |
| API health/contracts | Actual GET requests to `/`, `/models_status`, `/stats`, `/logs?limit=5`, `/prauc_history?limit=5`, `/drift_info`, `/replay_info`, `/config`, `/pr_curve` and `/openapi.json` all returned HTTP 200. `POST /config` with the existing configuration returned `config_updated`; values were retained. |
| Source preservation | `git diff HEAD -- server.py pretrain.py split_data.py payment_edge.py boost.py requirements.txt` produced no differences. Dashboard checks retained API field names, numerical values and layout structure. |
| Syntax/whitespace | Executed `python -m compileall -q` over all seven Python source files and `git diff --check`; passed. |
| Launchers | Earlier setup executed the Start/Stop launchers, verified restart/reuse behavior, and confirmed ports 8000/8501 closed on stop before restarting. The standard API/dashboard remain running after verification. |
| Live dashboard rendering | Opened the translated standard dashboard at port 8501 and the advanced dashboard at port 8502 in the browser. Verified English controls, model labels, live metrics, charts, drift markers, audit tables and replay/augmentation output. Saved screenshots outside the source repository. The temporary advanced test process was then stopped; it can be launched with the documented command. |
| Publication hygiene | During the earlier adaptation/verification pass, verified ignored environments, runtime/tools, data, models, PID/status/log files; removed three generated files from the index while keeping disk copies. Created local branch `college-mini-project`; no remote change, commit or push was performed during that pass. |

## Isolated frontend verification: 21/21 passed

Executed from the chat workspace:

```powershell
.\outputs\OnlineML-Fraud-Detector\.venv\Scripts\python.exe -u work\verify_frontends.py
```

The temporary harness uses Streamlit AppTest with mocked HTTP and process operations; it does not modify the live API configuration. It ran outside the restricted sandbox because sandboxed asyncio initialization stalled before the app could execute.

- 19 dynamic scenarios: both populated dashboards, both offline/empty states, missing history/replay/models, a running stream, uniform replay/no noise, drift timing controls, both threshold-update dispatch paths, replay-form success/failure, and mocked server/stream/warmup failures.
- Two static UI-string scans, supplemented by rendered-text scans and source/browser review.
- No Streamlit exceptions. No remaining Vietnamese or outdated SGD/Adam model labels in tested rendered text, tooltips, table labels or Plotly specifications. Existing non-rendered comments do not affect the interface.
- Populated standard dashboard: two charts, two tables, six metrics. Populated advanced dashboard: four charts, three tables, thirteen metrics, including a synthetic drift marker and augmented-sample comparison.
- Separate mocked warmup checks exercised missing training data, missing required model outputs and successful output validation. The actual pretraining script had already been executed during laptop setup.

## Not verified or intentionally retained

- A fresh Windows machine's Python installer/`py` launcher and Git installation were not executed; those README steps are instructions for a new machine. This laptop uses the working private runtime.
- Actual OS start/stop/stream/retrain button actions inside the advanced dashboard were not clicked during this pass. Their helper logic is retained, except the documented pretraining validation guards; failure text and dispatch paths were tested with mocks. The upstream Stop Server control still acts on port 8000; use the provided launcher lifecycle for a launcher-managed API.
- No independent 30,000-transaction benchmark, production latency guarantee, statistical accuracy validation, Kafka/Flink integration or deployment test was performed.
- Injected drift does not guarantee a detector alert every time. Random replay/augmentation can change observed metrics between runs.
- The command-line training/stream scripts retain their upstream Vietnamese console text. Both Streamlit dashboards are English.
- No GitHub fork, authentication, publication or push was performed during the earlier adaptation/verification pass. No explicit upstream reuse license was found. The later maintainer authorization and destination creation are recorded below; this historical test result is not a claim about the final push status.

## Publication follow-up — 16 November 2026

The student maintainer confirmed that they have permission to publish the adaptation and explicitly authorized publication. A new public repository was created at [udayvarshney151006/OnlineML-Fraud-Detector](https://github.com/udayvarshney151006/OnlineML-Fraud-Detector), with default branch `main`. The README was updated to use this destination while preserving the original source and author attribution.

No written license or permission text was supplied for inclusion, and no new downstream license is granted. This follow-up records authorization and destination creation only; it does not record a completed initial push or remote-clone verification. No application test result above was changed by these documentation edits.
