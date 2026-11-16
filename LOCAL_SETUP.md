# Run this project on Windows

This folder contains a local copy of [OnlineML-Fraud-Detector](https://github.com/Membau/OnlineML-Fraud-Detector). The setup uses the private Python environment in `.venv` and a Python runtime in `.runtime`.

Setup completed on 16 November 2026 with Python 3.12.16. The full public dataset is downloaded and split, and the HAT, ARF, and Random Forest models are trained on all 142,403 prefix transactions. The API, dashboard, prediction/feedback flow for 1,000 transactions, and launcher restart were verified locally. No environment activation or system Python installation is needed to use the launchers.

## Start and stop

Double-click **Start-Project.cmd**. It starts the API and the standard dashboard in the background and opens the dashboard once both respond:

- Dashboard: <http://127.0.0.1:8501>
- API documentation: <http://127.0.0.1:8000/docs>

Double-click **Stop-Project.cmd** to stop the processes started by this launcher. Logs are saved in `.local-run`. An occupied port produces an error; close the application using that port before trying again.

## Send transactions

Double-click **Stream-Transactions.cmd** after starting the project to send 1,000 transactions. To change the count or pacing, open PowerShell in this folder and run:

```powershell
.\.venv\Scripts\python.exe payment_edge.py --rows 1000 --delay 0.01 --feedback-delay 0
```

This reads `data/creditcard_suffix.csv`. Watch the dashboard while transactions are sent. The stream ends after the requested rows; the API and dashboard remain running.

Dashboard counters reset when the server restarts. Both dashboards use English text and identify HAT, ARF and the static Random Forest correctly. The original command-line simulation messages are retained.

## Prepare or train models

If the split dataset files are missing, place the ULB credit-card dataset at `data/creditcard.csv` and run:

```powershell
.\.venv\Scripts\python.exe split_data.py
```

Train the models from `data/creditcard_prefix.csv`:

```powershell
.\.venv\Scripts\python.exe pretrain.py
```

Training can take time. Check that `model_hat.pkl`, `model_arf.pkl`, and `model_rf.pkl` were created. Restart the project after training so the server loads them. Without these files, the server initializes fresh streaming models and has no trained static Random Forest baseline.

The exact installed package versions are recorded in `requirements-local.lock`. Keep this folder at its current location: the virtual environment refers to the Python runtime here by its absolute path.

The original dataset is published by the [ULB Machine Learning Group on Kaggle](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud). The [official TensorFlow tutorial](https://www.tensorflow.org/tutorials/structured_data/imbalanced_data) also links its public CSV download at `https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv`.

To start from PowerShell without opening a browser:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Project.ps1 -NoBrowser
```

For the advanced dashboard, keep the API running and use another VS Code terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run view_optimize.py --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false
```

In a separate terminal, demonstrate the original drift simulation:

```powershell
.\.venv\Scripts\python.exe boost.py --rows 10000 --drift --drift-start 1500 --drift-len 800
```

The advanced dashboard is at <http://127.0.0.1:8502>. See [README.md](README.md) for architecture, metric interpretation, attribution and permission requirements before GitHub publication.
