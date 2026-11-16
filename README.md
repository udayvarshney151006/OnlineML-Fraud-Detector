# Real-Time Credit Card Fraud Detection Using Online Machine Learning and Data Stream Mining

A college mini-project adaptation of [Membau/OnlineML-Fraud-Detector](https://github.com/Membau/OnlineML-Fraud-Detector). It replays historical credit-card transactions through a FastAPI scoring and incremental-learning service, with two Streamlit monitoring dashboards.

Credit for the original implementation belongs to its upstream authors and contributors, including **Lomgz** and **MemBau** in the preserved Git history. This adaptation translates the dashboards, corrects presentation labels, and documents Windows setup. It is adapted work, not an implementation developed entirely by the student. The original algorithms, backend, training scripts, streaming scripts, dataset split and numerical parameters are retained.

## Technology and architecture

| Component | Technology |
| --- | --- |
| Online models | River Hoeffding Adaptive Tree (HAT), Adaptive Random Forest (ARF) |
| Static baseline | Scikit-learn Random Forest |
| API | FastAPI, Pydantic, Uvicorn |
| Dashboards | Streamlit, Plotly, pandas |
| Simulation | Python CSV readers and Requests HTTP clients |
| Adaptation | ADWIN, Prioritized Experience Replay (PER), Gaussian noise augmentation |

```text
Historical prefix CSV -> pretrain.py -> model_*.pkl
                                            |
Streaming suffix CSV                        v
 payment_edge.py / boost.py -> FastAPI server.py -> Streamlit dashboards
                               predict first        view.py
                               receive label        view_optimize.py
                               update HAT/ARF
                               replay + noise + ADWIN + metrics
```

The current code has **three models**. The `sgd` and `adam` fields and model files are compatibility aliases for HAT and ARF, not additional logistic-regression models. The Random Forest stays fixed after pretraining. `payment_edge.py` sends prediction and feedback separately; `boost.py` uses micro-batches when available. The gateway blocks when ARF's probability exceeds the configured threshold.

Kafka/Flink are possible extensions discussed upstream, not implemented integrations. No production latency or independently reproduced 30,000-transaction benchmark is claimed here.

## Dataset and training protocol

The [ULB/Worldline Credit Card Fraud dataset](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) contains 284,807 transactions, including 492 frauds. The [official TensorFlow tutorial](https://www.tensorflow.org/tutorials/structured_data/imbalanced_data) provides a public CSV download of the same dataset.

| Local file | Purpose | Transactions | Fraud cases |
| --- | --- | ---: | ---: |
| `data/creditcard_prefix.csv` | Historical pretraining | 142,403 | 269 |
| `data/creditcard_suffix.csv` | Streaming evaluation | 142,404 | 223 |

`split_data.py` preserves row order and divides the data in half. `Class` is the label (`1` = fraud); scripts drop `Time` and use `V1` through `V28` plus `Amount` as features. Dataset/model files are excluded from Git. Check the dataset provider's terms before redistributing data.

## Already configured laptop

Open this folder in VS Code and select `.venv\Scripts\python.exe` with **Python: Select Interpreter**. The private runtime is in `.runtime`; no environment activation is required.

1. Double-click **Start-Project.cmd** to start the API and standard dashboard.
2. Double-click **Stream-Transactions.cmd** to send 1,000 transactions.
3. Double-click **Stop-Project.cmd** when finished.

Dashboard: <http://127.0.0.1:8501> | API documentation: <http://127.0.0.1:8000/docs>

Logs are in `.local-run`. The launchers bind locally and stop only the project processes they recorded. Keep this configured folder in its current location: the virtual environment references the private runtime by absolute path.

## Fresh Windows setup

Install 64-bit Python 3.12 and Git first. These steps are for a new checkout; this laptop already has its environment, dataset and models prepared. Read the permission section before distributing modified code.

```powershell
git clone https://github.com/udayvarshney151006/OnlineML-Fraud-Detector.git
cd OnlineML-Fraud-Detector
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In this adapted checkout, use `requirements-local.lock` instead of `requirements.txt` for the exact package versions verified on this laptop. The original requirements are unchanged.

Download and prepare data from PowerShell in the project folder:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest -Uri 'https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv' -OutFile 'data/creditcard.csv'
.\.venv\Scripts\python.exe split_data.py
.\.venv\Scripts\python.exe pretrain.py
Get-Item model_hat.pkl, model_arf.pkl, model_rf.pkl
```

Pretraining also writes `model_sgd.pkl` and `model_adam.pkl` as aliases. Verify output files: the upstream preparation scripts can return exit code zero after printing a missing-input message. Restart the API after training to load the saved models.

## Manual execution in VS Code

Run commands from this project directory. Use either a manual API process or the provided launcher for the API lifecycle.

**Terminal 1 — API**

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — choose a dashboard**

```powershell
# Standard dashboard
.\.venv\Scripts\python.exe -m streamlit run view.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false

# Advanced dashboard: replay, augmentation and drift
.\.venv\Scripts\python.exe -m streamlit run view_optimize.py --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false
```

The advanced dashboard is at <http://127.0.0.1:8502> and uses the same API on port 8000. Its original process controls are retained. For a launcher-managed API, use **Stop-Project.cmd**. The advanced dashboard's upstream Stop Server control stops the process using port 8000; reserve that port for this project.

**Terminal 3 — transactions**

```powershell
# Paced prediction and feedback, with no additional feedback delay
.\.venv\Scripts\python.exe payment_edge.py --rows 1000 --delay 0.01 --feedback-delay 0

# Faster micro-batches
.\.venv\Scripts\python.exe boost.py --rows 5000
```

Both dashboards are English; the streaming scripts retain their original command-line messages. Stop foreground terminal processes with Ctrl+C. Counters and in-memory learning state reset when the API restarts.

## Concept drift demonstration

With the API and advanced dashboard running:

```powershell
.\.venv\Scripts\python.exe boost.py --rows 10000 --drift --drift-start 1500 --drift-len 800
```

The original simulation changes selected fraud features and injects additional fraud labels during the specified interval. Watch PR-AUC history, ADWIN markers, fraud-memory size, replay count and original-versus-augmented feature comparisons. The advanced sidebar also exposes drift controls. Injection does not guarantee an ADWIN alert on every run; the detector responds to its observed statistical signal.

For a presentation, explain the unchanged sequence: predict, receive the label, update online models, replay historical fraud examples, and monitor performance. Changing PER/noise settings is an experiment, not a guarantee of improved accuracy.

## Interpret the metrics correctly

- **Confirmed Fraud Transactions** counts ground-truth positive labels, not successful detections.
- **Recall** is true positives divided by confirmed frauds, not overall accuracy.
- River **Rolling PR-AUC** retains its original 1,000-observation window. The configurable evaluation window affects average precision (AP), Precision@k and PR curves.
- Confusion matrices use cutoff `0.5`; gateway blocking uses ARF with default configurable threshold `0.70`.
- Service-level ADWIN monitors `1 - rolling ARF PR-AUC` with original `delta=0.005`; model-internal adaptation is unchanged.
- Disabling PER uses uniform replay selection; replay continues. Disabling noise reuses original feature values.

## API and project files

| Endpoint | Purpose |
| --- | --- |
| `GET /`, `GET /models_status` | Health and saved-model availability |
| `POST /predict`, `POST /feedback` | Score, then learn from labels |
| `POST /stream_tx`, `POST /batch_stream` | Combined streaming paths |
| `GET /stats`, `GET /logs`, `GET /prauc_history`, `GET /pr_curve` | Evaluation and monitoring |
| `GET /drift_info`, `GET /replay_info` | Drift and replay details |
| `GET /config`, `POST /config` | Gateway, evaluation, PER and noise settings |
| `POST /reload_models` | Load saved models |

There is no `/replay_config` endpoint: replay settings use `POST /config`.

Original source files remain in place: `server.py`, `pretrain.py`, `split_data.py`, `payment_edge.py`, `boost.py`, `view.py`, `view_optimize.py`, and `requirements.txt`. See [CHANGELOG.md](CHANGELOG.md) for all local changes, [TEST_RESULTS.md](TEST_RESULTS.md) for executed checks and limits, and [LOCAL_SETUP.md](LOCAL_SETUP.md) for quick laptop instructions.

## Attribution, permission and GitHub publication

Base: [Membau/OnlineML-Fraud-Detector](https://github.com/Membau/OnlineML-Fraud-Detector), commit `7f44990df61850b4b2829e5ac026b4d1d3436348`. The upstream README also referenced [Lomgz/OnlineML-FraudDetection](https://github.com/Lomgz/OnlineML-FraudDetection). The preserved history includes Lomgz and MemBau. Retain these credits and the Git history.

**No explicit reuse license was found** in the inspected upstream commit. GitHub metadata reported `license: null` on 16 November 2026. The student maintainer confirmed on 16 November 2026 that they have permission to publish this adaptation and authorized publication to their GitHub account. No written permission or license text was supplied for inclusion, and no new license is applied here. This maintainer confirmation does not grant a general license to downstream users. [GitHub's guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) explains the limitations of an unlicensed public repository; downstream users should obtain the applicable authorization before modifying or redistributing the original code.

Publication destination: [udayvarshney151006/OnlineML-Fraud-Detector](https://github.com/udayvarshney151006/OnlineML-Fraud-Detector), with default branch `main`. This new repository was created after the maintainer's publication approval. The original attribution and Git history are preserved. Local adaptation work was prepared on `college-mini-project`; generated `boost_status.json`, `server.pid` and `uvicorn_server.log` are excluded from the publication tree while disk copies remain available locally.

For future updates from a checkout of this repository's `main` branch, review and test changes before committing and pushing:

```powershell
git remote -v
git pull --ff-only origin main
git status --short
git diff
# Stage only the source or documentation files you intentionally changed.
git add README.md view.py view_optimize.py
git diff --cached
git commit -m "Describe the reviewed project update"
git push origin main
```

Do not upload virtual environments, runtimes, tools, datasets, model files, PID files, logs or local test artifacts; `.gitignore` excludes them.
