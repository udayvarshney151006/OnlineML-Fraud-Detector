# Adaptation change log

Base: Membau/OnlineML-Fraud-Detector at `7f44990df61850b4b2829e5ac026b4d1d3436348`.
Date: 16 November 2026. Local adaptation branch: `college-mini-project`. Publication target: `main` in [udayvarshney151006/OnlineML-Fraud-Detector](https://github.com/udayvarshney151006/OnlineML-Fraud-Detector).

## Focused source changes

| File | Changes |
| --- | --- |
| `view.py` | Translate all visible dashboard text, tooltips, chart/hover labels and table headers to English. Display HAT/ARF instead of outdated SGD/Adam model names while retaining compatibility API keys. Use accurate confirmed-fraud and rolling PR-AUC labels. Close the missing Random Forest Markdown code fence. Use supported `width="stretch"` arguments instead of deprecated width flags. |
| `view_optimize.py` | Translate server/stream controls, notifications, metrics, chart/hover labels, tables, drift monitoring, replay and augmentation panels. Correct model names, recall wording and metric descriptions. Keep the existing layout and numerical values. Use supported width arguments. Add checks for missing training data and missing model outputs so the pretraining control cannot report success for those cases. |

`server.py`, `pretrain.py`, `split_data.py`, `payment_edge.py`, `boost.py` and `requirements.txt` are byte-for-byte unchanged from the base Git commit. The API, algorithms, feature processing, training methodology and numeric parameters are preserved. Original process-control behavior in the advanced dashboard is retained.

## Documentation and publication preparation

| File or operation | Changes |
| --- | --- |
| `README.md` | English project overview, actual three-model architecture, technology stack, dataset counts, Windows/VS Code instructions, execution/drift commands, correct metric/API explanations, original attribution, license limitation, publication destination and update workflow. Remove unsupported benchmark/latency and implemented-Kafka claims. |
| `LOCAL_SETUP.md` | Refresh the laptop quick-start, English-dashboard description and advanced-dashboard/drift commands. |
| `.gitignore` | Exclude environments, private runtime/tools, datasets, models, PID/status/log files and secrets. Remove overly broad documentation/text exclusions so useful project documentation can be tracked. |
| `requirements-local.lock` | Record the exact already installed package versions. Original `requirements.txt` remains intact. |
| `Start-Project.cmd`, `Start-Project.ps1` | Existing local setup additions: start the API and standard dashboard locally with readiness checks and process-ownership records. |
| `Stop-Project.cmd`, `Stop-Project.ps1` | Existing local setup additions: stop only the launcher-owned processes. |
| `Stream-Transactions.cmd` | Existing local setup addition: send 1,000 public sample transactions. |
| `CHANGELOG.md`, `TEST_RESULTS.md` | Record the adaptation scope, executed verification and remaining limits. |
| Git index cleanup | Remove upstream-tracked `boost_status.json`, `server.pid`, `uvicorn_server.log` from the next commit's index; keep local files and preserve their historical commits. |

No new framework or dependency is introduced for the adaptation. Temporary test scripts, logs and fixtures are outside the tracked project or in ignored `.local-run`. Dataset and model files remain local. No new license is assigned to upstream code. During the earlier adaptation and verification pass, no remote was redirected, no commit was created, and no push was performed.

## Publication follow-up — 16 November 2026

The student maintainer confirmed that they have reuse authorization for publishing this adaptation and explicitly approved publication to their GitHub account. A new public destination was created at [udayvarshney151006/OnlineML-Fraud-Detector](https://github.com/udayvarshney151006/OnlineML-Fraud-Detector), with default branch `main`.

The README now clones from the maintainer's repository, preserves all upstream source links and author credits, and documents future synchronization and update commands. Permission statements record the maintainer's confirmation; no written license or permission text was supplied for inclusion, and no general downstream license is granted. These documentation changes prepare the publication commit; this entry does not assert that the initial push has completed.
