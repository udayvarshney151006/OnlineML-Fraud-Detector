import json
import os
import socket
import subprocess
import sys
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Payment Edge Fraud Monitor - Advanced (PER & Noise Augmentation)",
    layout="wide",
    initial_sidebar_state="expanded",
)

NO_DIM_CSS = """
<style>
html, body, [class*="css"], [class*="st-"], .stApp,
.stApp *,
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"] *,
section.main,
section.main *,
div.block-container,
div.block-container *,
[data-testid="stFragment"],
[data-testid="stFragment"] *,
[data-st-fragment-id],
[data-st-fragment-id] *,
[data-test-fragment-state="running"],
[data-test-fragment-state="running"] *,
.stApp[data-test-script-state="running"],
.stApp[data-test-script-state="running"] *,
div[data-testid="stVerticalBlock"],
div[data-testid="stVerticalBlock"] *,
div[data-testid="stElementContainer"],
div[data-testid="stElementContainer"] *,
div[data-testid="stPlotlyChart"],
div[data-testid="stPlotlyChart"] * {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
    animation: none !important;
}

[data-testid="stStatusWidget"],
div[data-testid="stStatusWidget"],
div[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
}

.js-plotly-plot,
.js-plotly-plot .plotly,
.js-plotly-plot .plotly .main-svg {
    transition: none !important;
    opacity: 1 !important;
}
</style>
"""
st.markdown(NO_DIM_CSS, unsafe_allow_html=True)

SERVER = "http://localhost:8000"
SERVER_PID_FILE = "server.pid"
BOOST_PID_FILE = "boost.pid"
BOOST_STATUS_FILE = "boost_status.json"


def get_python_exe() -> str:
    local_venv = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    if os.path.exists(local_venv):
        return local_venv
    local_venv_unix = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
    if os.path.exists(local_venv_unix):
        return local_venv_unix
    return sys.executable


def is_server_alive(host="127.0.0.1", port=8000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def start_uvicorn_server() -> tuple[bool, str]:
    if is_server_alive():
        return True, "The server is already running on port 8000."
    try:
        py_exe = get_python_exe()
        flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
        log_f = open("uvicorn_server.log", "w", encoding="utf-8")
        p = subprocess.Popen(
            [py_exe, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000"],
            creationflags=flags,
            stdout=log_f,
            stderr=log_f
        )
        with open(SERVER_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(p.pid))
        for _ in range(24):
            time.sleep(0.5)
            if is_server_alive():
                return True, f"Server started successfully (PID {p.pid})!"
            if p.poll() is not None:
                log_f.close()
                err_msg = ""
                if os.path.exists("uvicorn_server.log"):
                    with open("uvicorn_server.log", "r", encoding="utf-8", errors="ignore") as lf:
                        err_msg = lf.read()[-300:]
                return False, f"The server exited early with code {p.returncode}: {err_msg}"
        return False, "Server startup timed out after 12 seconds."
    except Exception as e:
        return False, str(e)


def stop_uvicorn_server() -> bool:
    if os.path.exists(SERVER_PID_FILE):
        try:
            with open(SERVER_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True)
        except Exception:
            pass
        try:
            os.remove(SERVER_PID_FILE)
        except Exception:
            pass
    cmd = "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    time.sleep(0.5)
    return True


def is_pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in res.stdout
    except Exception:
        return False


def get_boost_status() -> dict:
    status = {"running": False, "count": 0, "total": 0, "fraud_count": 0, "speed": 0.0}
    if os.path.exists(BOOST_STATUS_FILE):
        try:
            with open(BOOST_STATUS_FILE, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            pass
    if status.get("running"):
        pid = None
        if os.path.exists(BOOST_PID_FILE):
            try:
                with open(BOOST_PID_FILE, "r") as f:
                    pid = int(f.read().strip())
            except Exception:
                pass
        if not pid or not is_pid_alive(pid):
            status["running"] = False
            if os.path.exists(BOOST_PID_FILE):
                try:
                    os.remove(BOOST_PID_FILE)
                except Exception:
                    pass
            try:
                with open(BOOST_STATUS_FILE, "w", encoding="utf-8") as f:
                    json.dump(status, f)
            except Exception:
                pass
    return status


def start_boost_simulation(rows: int, drift: bool, drift_start: int, drift_len: int) -> tuple[bool, str]:
    try:
        py_exe = get_python_exe()
        flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
        cmd = [py_exe, "boost.py", "--rows", str(rows), "--server", SERVER]
        if drift:
            cmd.extend(["--drift", "--drift-start", str(drift_start), "--drift-len", str(drift_len)])
        p = subprocess.Popen(cmd, creationflags=flags)
        with open(BOOST_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(p.pid))
        return True, f"Boost transaction streaming started (PID {p.pid})!"
    except Exception as e:
        return False, str(e)


def stop_boost_simulation() -> bool:
    if os.path.exists(BOOST_PID_FILE):
        try:
            with open(BOOST_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True)
        except Exception:
            pass
        try:
            os.remove(BOOST_PID_FILE)
        except Exception:
            pass
    if os.path.exists(BOOST_STATUS_FILE):
        try:
            with open(BOOST_STATUS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            d["running"] = False
            with open(BOOST_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f)
        except Exception:
            pass
    return True


def fetch_stats() -> dict:
    try:
        r = requests.get(f"{SERVER}/stats", timeout=2)
        return r.json()
    except Exception:
        return None


def fetch_logs(limit: int = 100) -> list:
    try:
        r = requests.get(f"{SERVER}/logs?limit={limit}", timeout=2)
        return r.json().get("transactions", [])
    except Exception:
        return []


def fetch_prauc_history(limit: int = None) -> list:
    try:
        url = f"{SERVER}/prauc_history" if limit is None else f"{SERVER}/prauc_history?limit={limit}"
        r = requests.get(url, timeout=3)
        return r.json().get("history", [])
    except Exception:
        return []


def fetch_drift_info() -> dict:
    try:
        r = requests.get(f"{SERVER}/drift_info", timeout=2)
        return r.json()
    except Exception:
        return {"drift_count": 0, "last_drift_step": None, "drift_points": []}


def fetch_replay_info() -> dict:
    try:
        r = requests.get(f"{SERVER}/replay_info", timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {
        "config": {"enable_per": True, "enable_noise_aug": True, "noise_std": 0.02, "replay_interval": 10},
        "buffer_size": 0,
        "buffer_max": 100,
        "total_replays": 0,
        "top_hardest": [],
        "last_replay": None,
    }


def update_server_config(threshold: float, alpha: float, window_size: int):
    try:
        requests.post(
            f"{SERVER}/config",
            json={"block_threshold": threshold, "alert_budget_alpha": alpha, "window_size": window_size},
            timeout=2
        )
    except Exception:
        pass


def update_replay_config(enable_per: bool, enable_noise_aug: bool, noise_std: float, replay_interval: int) -> bool:
    try:
        r = requests.post(
            f"{SERVER}/config",
            json={
                "enable_per": enable_per,
                "enable_noise_aug": enable_noise_aug,
                "noise_std": noise_std,
                "replay_interval": replay_interval,
            },
            timeout=2
        )
        return r.status_code == 200
    except Exception:
        return False


def check_models_status() -> dict:
    try:
        r = requests.get(f"{SERVER}/models_status", timeout=1)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    hat_ready = os.path.exists("model_hat.pkl") or os.path.exists("model_sgd.pkl")
    arf_ready = os.path.exists("model_arf.pkl") or os.path.exists("model_adam.pkl")
    rf_ready = os.path.exists("model_rf.pkl")
    return {
        "pretrained_ready": hat_ready and arf_ready and rf_ready,
        "hat_ready": hat_ready,
        "arf_ready": arf_ready,
        "rf_ready": rf_ready,
    }


def trigger_warmup() -> tuple[bool, str]:
    if not os.path.isfile("data/creditcard_prefix.csv"):
        return False, "Training data not found: data/creditcard_prefix.csv. Prepare and split the dataset first."
    try:
        res = subprocess.run([get_python_exe(), "pretrain.py"], capture_output=True, text=True)
        if res.returncode == 0:
            if not all(os.path.isfile(path) for path in ("model_hat.pkl", "model_arf.pkl", "model_rf.pkl")):
                return False, "Training finished without the required model files. Check the training data and pretrain.py output."
            try:
                requests.post(f"{SERVER}/reload_models", timeout=3)
            except Exception:
                pass
            return True, res.stdout
        return False, res.stderr
    except Exception as e:
        return False, str(e)


# -------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------
server_cfg = {}
try:
    cfg_resp = requests.get(f"{SERVER}/config", timeout=1)
    if cfg_resp.status_code == 200:
        server_cfg = cfg_resp.json()
except Exception:
    pass

initial_thresh = server_cfg.get("block_threshold", 0.70)
initial_alpha = server_cfg.get("alert_budget_alpha", 1.0)
initial_win = server_cfg.get("window_size", 500)

with st.sidebar:
    st.header("Server & Transaction Stream Management")

    srv_alive = is_server_alive()
    if srv_alive:
        st.success("**Uvicorn Server: ONLINE** (Port 8000)")
        if st.button("Stop Server", key="btn_stop_srv", width="stretch"):
            stop_uvicorn_server()
            st.info("Server stop command sent.")
            time.sleep(1)
            st.rerun()
    else:
        st.error("**Uvicorn Server: OFFLINE**")
        if st.button("Start Server", type="primary", key="btn_start_srv", width="stretch"):
            with st.spinner("Starting the Uvicorn server..."):
                ok, msg = start_uvicorn_server()
                if ok:
                    st.success(f" {msg}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {msg}")

    st.divider()
    st.subheader("Transaction Streaming (Turbo Boost)")
    b_stat = get_boost_status()
    b_running = b_stat.get("running", False)

    with st.expander("Transaction Stream Options", expanded=not b_running):
        b_rows = st.number_input("Transactions (Rows)", min_value=100, max_value=25000, value=5000, step=500)
        b_drift = st.checkbox("Enable Concept Drift", value=False, help="Shift fraud feature distributions to demonstrate model adaptation.")
        if b_drift:
            b_dstart = st.number_input("Drift Start Step", min_value=100, max_value=10000, value=1500, step=100)
            b_dlen = st.number_input("Drift Duration (Transactions)", min_value=100, max_value=5000, value=800, step=100)
        else:
            b_dstart, b_dlen = 1500, 800

    if b_running:
        st.info(f"**Streaming transactions...** ({b_stat.get('count', 0):,}/{b_stat.get('total', 0):,} txs)")
        pct = min(1.0, max(0.0, b_stat.get("count", 0) / max(1, b_stat.get("total", 1))))
        st.progress(pct)
        st.caption(f"Speed: **{b_stat.get('speed', 0):.0f} tx/s** | Confirmed frauds: **{b_stat.get('fraud_count', 0)}**")
        if st.button("Stop Streaming", key="btn_stop_boost", width="stretch"):
            stop_boost_simulation()
            st.warning("Transaction streaming stopped.")
            time.sleep(0.5)
            st.rerun()
    else:
        if srv_alive:
            if st.button("Start Streaming", type="primary", key="btn_start_boost", width="stretch"):
                ok, msg = start_boost_simulation(b_rows, b_drift, b_dstart, b_dlen)
                if ok:
                    st.success(f" {msg}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"Error: {msg}")
        else:
            st.button("Start Streaming (Server Required)", disabled=True, width="stretch")

    st.divider()
    st.subheader("Edge Gateway Settings")
    threshold = st.slider(
        "Fraud Blocking Threshold", min_value=0.10, max_value=0.95,
        value=float(initial_thresh), step=0.05,
        help="Transactions with fraud probability above this threshold are blocked at the gateway."
    )
    alpha = st.slider(
        "Alert Budget Multiplier (α)", min_value=0.5, max_value=5.0,
        value=float(initial_alpha), step=0.5,
        help="Alert budget: k = max(1, round(alpha * fraud_rate * W))."
    )
    window_size = st.slider(
        "Rolling Evaluation Window (W)", min_value=100, max_value=2000,
        value=int(initial_win), step=100,
        help="The most recent transactions used for Average Precision, Precision@k and PR curves. Rolling PR-AUC uses a fixed 1,000-transaction window."
    )
    refresh_interval = st.slider(
        "Refresh Interval (seconds)", min_value=1, max_value=10, value=2, step=1
    )

    if threshold != initial_thresh or alpha != initial_alpha or window_size != initial_win:
        update_server_config(threshold, alpha, window_size)

    st.divider()
    st.subheader("Pretraining Status")
    m_stat = check_models_status()
    if m_stat.get("pretrained_ready", False):
        st.success("Models: Pretrained (.pkl)")
        if st.button("Retrain Models", key="btn_rewarmup_side", width="stretch"):
            with st.spinner("Training with pretrain.py..."):
                ok, msg = trigger_warmup()
                if ok:
                    st.success("Models retrained successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {msg}")
    else:
        st.error("Models: Not Pretrained")
        if st.button("Train Models", type="primary", key="btn_warmup_side", width="stretch"):
            with st.spinner("Training with pretrain.py..."):
                ok, msg = trigger_warmup()
                if ok:
                    st.success("Model training completed!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {msg}")


# -------------------------------------------------------------
# MAIN DASHBOARD FRAGMENT
# -------------------------------------------------------------
st.title("Real-Time Fraud Monitoring - Advanced (PER & Augmentation)")
st.caption(f"Engine: `{SERVER}` | Block threshold: `{threshold:.2f}` | Alert budget α: `{alpha:.1f}` | Window W: `{window_size}` | Refresh: `{refresh_interval}s`")


@st.fragment(run_every=refresh_interval)
def render_dashboard():
    st.markdown(NO_DIM_CSS, unsafe_allow_html=True)
    stats = fetch_stats()

    if stats is None:
        st.error("The ML server is offline. Click 'Start Server' in the sidebar.")
        return

    drift_info = fetch_drift_info()

    # Top KPI Cards
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Transactions", f"{stats.get('total', 0):,}")
    col2.metric("Confirmed Frauds", stats.get("fraud_detected", 0), help="Ground-truth fraud labels received through transaction feedback.")
    col3.metric("Blocked Transactions", stats.get("blocked", 0))

    prauc_hat_val = stats.get("prauc_hat", stats.get("prauc_sgd", 0.0))
    sk_ap_hat_val = stats.get("sk_ap_hat", stats.get("sk_ap_sgd", 0.0))
    prauc_arf_val = stats.get("prauc_arf", stats.get("prauc_adam", 0.0))
    sk_ap_arf_val = stats.get("sk_ap_arf", stats.get("sk_ap_adam", 0.0))
    prauc_rf_val  = stats.get("prauc_rf", 0.0)
    sk_ap_rf_val  = stats.get("sk_ap_rf", 0.0)

    pr_k_hat_pct = stats.get("pr_at_k_hat", stats.get("pr_at_k_sgd", 0.0)) * 100
    pr_k_arf_pct = stats.get("pr_at_k_arf", stats.get("pr_at_k_adam", 0.0)) * 100
    pr_k_rf_pct  = stats.get("pr_at_k_rf", 0.0) * 100

    col4.metric("PR-AUC (HAT)", f"{prauc_hat_val:.4f}", help=f"Rolling PR-AUC: {prauc_hat_val:.4f} | Scikit-learn AP: {sk_ap_hat_val:.4f}")
    col5.metric("PR-AUC (ARF)", f"{prauc_arf_val:.4f}", help=f"Rolling PR-AUC: {prauc_arf_val:.4f} | Scikit-learn AP: {sk_ap_arf_val:.4f}")
    col6.metric("PR-AUC (Static RF)", f"{prauc_rf_val:.4f}", help=f"Rolling PR-AUC: {prauc_rf_val:.4f} | Scikit-learn AP: {sk_ap_rf_val:.4f}")

    tot_frauds = int(stats.get("fraud_detected", 0))
    cm_h_d = stats.get("cm_hat", stats.get("cm_sgd", {}))
    cm_a_d = stats.get("cm_arf", stats.get("cm_adam", {}))
    cm_r_d = stats.get("cm_rf", {})

    tp_h = int(cm_h_d.get("tp", stats.get("global_tp_hat", 0)))
    tp_a = int(cm_a_d.get("tp", stats.get("global_tp_arf", 0)))
    tp_r = int(cm_r_d.get("tp", stats.get("global_tp_rf", 0)))

    g_acc_h = (tp_h / tot_frauds * 100) if tot_frauds > 0 else 0.0
    g_acc_a = (tp_a / tot_frauds * 100) if tot_frauds > 0 else 0.0
    g_acc_r = (tp_r / tot_frauds * 100) if tot_frauds > 0 else 0.0

    st.markdown("##### Overall Fraud Recall (True Positives / Confirmed Frauds)")
    gcol1, gcol2, gcol3 = st.columns(3)
    gcol1.metric("Recall (HAT)", f"{tp_h:,} / {tot_frauds:,}", f"{g_acc_h:.1f}% recall")
    gcol2.metric("Recall (ARF)", f"{tp_a:,} / {tot_frauds:,}", f"{g_acc_a:.1f}% recall")
    gcol3.metric("Recall (Static RF)", f"{tp_r:,} / {tot_frauds:,}", f"{g_acc_r:.1f}% recall")
    st.divider()

    # Dải trạng thái Optimize
    rep_info = fetch_replay_info()
    rep_cfg = rep_info.get("config", {})
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("Fraud Replay Buffer", f"{rep_info.get('buffer_size', 0)} / {rep_info.get('buffer_max', 100)}")
    r_col2.metric("Total Replays", f"{rep_info.get('total_replays', 0):,}")
    r_col3.metric("Replay Sampling Strategy", "PER (Prediction Error)" if rep_cfg.get("enable_per") else "Uniform Sampling")
    r_col4.metric("Noise Augmentation", f"ON (σ={rep_cfg.get('noise_std', 0.02):.3f})" if rep_cfg.get("enable_noise_aug") else "OFF")
    st.divider()

    logs = fetch_logs(limit=100)
    if logs:
        df = pd.DataFrame(logs)
        df["index"] = range(len(df))
        if "prob_hat" not in df.columns and "prob_sgd" in df.columns:
            df["prob_hat"] = df["prob_sgd"]
        if "prob_arf" not in df.columns and "prob_adam" in df.columns:
            df["prob_arf"] = df["prob_adam"]

        col_chart1, col_chart2 = st.columns([2, 1])

        with col_chart1:
            st.subheader("Fraud Probability over Time")
            fig_line = px.line(
                df.rename(columns={"prob_hat": "HAT", "prob_arf": "ARF", "prob_rf": "Static RF"}),
                x="index", y=["HAT", "ARF", "Static RF"],
                labels={"index": "Transaction Order", "value": "Fraud Probability", "variable": "Model"},
                template="plotly_dark", height=320,
            )
            fig_line.add_hline(
                y=threshold, line_dash="dash", line_color="#facc15",
                annotation_text=f"Block Threshold {threshold:.2f}"
            )
            fig_line.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                uirevision="fixed_view",
            )
            st.plotly_chart(fig_line, width="stretch", key="h3_chart_line")

        with col_chart2:
            st.subheader("Gateway Decisions (ALLOW / BLOCK)")
            action_counts = df["action"].value_counts().reset_index()
            action_counts.columns = ["action", "count"]
            fig_pie = px.pie(
                action_counts, names="action", values="count", color="action",
                labels={"action": "Decision", "count": "Transactions"},
                color_discrete_map={"BLOCK": "#ef4444", "ALLOW": "#22c55e"},
                template="plotly_dark", height=320, hole=0.5,
            )
            fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=0), uirevision="fixed_view")
            st.plotly_chart(fig_pie, width="stretch", key="h3_chart_pie")

        st.divider()
        st.subheader("Model Performance (Online vs Static Baseline)")
        bench_df = pd.DataFrame({
            "Model": [
                "Hoeffding Adaptive Tree (HAT)",
                "Adaptive Random Forest (ARF)",
                "Static Random Forest (Scikit-learn)"
            ],
            "Model Family": [
                "Online Streaming (Single Tree + ADWIN)",
                "Online Streaming (Ensemble + PER + Noise)",
                "Static Batch Baseline (No Online Updates)"
            ],
            "Rolling PR-AUC": [
                f"{prauc_hat_val:.4f}",
                f"{prauc_arf_val:.4f}",
                f"{prauc_rf_val:.4f}"
            ],
            "Precision@k (Alert Budget)": [
                f"{pr_k_hat_pct:.2f}%",
                f"{pr_k_arf_pct:.2f}%",
                f"{pr_k_rf_pct:.2f}%"
            ]
        })
        st.dataframe(bench_df, width="stretch")
        st.divider()

        # Biểu đồ biến thiên PR-AUC
        st.subheader("Rolling PR-AUC & ADWIN Concept Drift")
        st.caption("ADWIN monitors 1 - ARF rolling PR-AUC. Drift markers show detected changes in this signal.")
        prauc_hist = fetch_prauc_history()
        if prauc_hist:
            hist_df = pd.DataFrame(prauc_hist)
            if "prauc_hat" not in hist_df.columns and "prauc_sgd" in hist_df.columns:
                hist_df["prauc_hat"] = hist_df["prauc_sgd"]
            if "prauc_arf" not in hist_df.columns and "prauc_adam" in hist_df.columns:
                hist_df["prauc_arf"] = hist_df["prauc_adam"]

            fig_drift = go.Figure()
            fig_drift.add_trace(go.Scatter(
                x=hist_df["step"], y=hist_df["prauc_hat"],
                mode="lines", name=f"HAT (Current: {prauc_hat_val:.4f})",
                line=dict(color="#3b82f6", width=2.5)
            ))
            fig_drift.add_trace(go.Scatter(
                x=hist_df["step"], y=hist_df["prauc_arf"],
                mode="lines", name=f"ARF (Current: {prauc_arf_val:.4f})",
                line=dict(color="#10b981", width=2.5, dash="dash")
            ))
            fig_drift.add_trace(go.Scatter(
                x=hist_df["step"], y=hist_df["prauc_rf"],
                mode="lines", name=f"Static RF (Current: {prauc_rf_val:.4f})",
                line=dict(color="#ef4444", width=2.5, dash="dot")
            ))

            all_drift_steps = {p["step"] for p in prauc_hist if p.get("drift")}
            for dp in drift_info.get("drift_points", []):
                if isinstance(dp, dict) and "step" in dp:
                    all_drift_steps.add(dp["step"])

            drift_x = [p["step"] for p in prauc_hist if p.get("step") in all_drift_steps]
            drift_y = [p.get("prauc_arf", 0.5) for p in prauc_hist if p.get("step") in all_drift_steps]

            if drift_x:
                fig_drift.add_trace(go.Scatter(
                    x=drift_x, y=drift_y, mode="markers",
                    name=f"Drift Events ({len(drift_x)} events)",
                    marker=dict(symbol="diamond", size=10, color="#facc15", line=dict(width=1.5, color="#000")),
                ))

            for s in sorted(all_drift_steps):
                fig_drift.add_vline(
                    x=s, line_dash="dash", line_color="#eab308", line_width=2,
                    annotation_text=f"Drift #{s}", annotation_position="top left",
                    annotation_font_color="#eab308", annotation_font_size=11,
                )

            fig_drift.update_layout(
                title="Rolling PR-AUC over the Transaction Stream",
                xaxis_title="Transaction Step",
                yaxis_title="Rolling PR-AUC",
                template="plotly_dark", height=340,
                margin=dict(l=0, r=0, t=30, b=0),
                yaxis=dict(range=[0, 1.05]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                uirevision="fixed_view",
            )
            st.plotly_chart(fig_drift, width="stretch", key="h3_chart_prauc")
        else:
            st.info("No PR-AUC history yet. Stream transactions to populate this chart.")

        st.divider()
        k_val = stats.get("k_eval", 1)
        win_size = stats.get("window_size", window_size)
        frauds_in_win = stats.get("frauds_in_window", 0)

        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            st.markdown(f"""
**HAT Pr@{k_val}**: `{pr_k_hat_pct:.2f}%`
* **Rolling PR-AUC**: `{prauc_hat_val:.4f}` | **Scikit-learn AP**: `{sk_ap_hat_val:.4f}`
* **Overall fraud recall**: **`{tp_h:,} / {tot_frauds:,} ({g_acc_h:.1f}%)`**
* **Window**: `{win_size}` transactions (`{frauds_in_win}` frauds)
```text
HAT Confusion Matrix ({stats.get('total', 0):,} txs):
TP: {cm_h_d.get('tp', 0):<6} | FP: {cm_h_d.get('fp', 0):<6}
FN: {cm_h_d.get('fn', 0):<6} | TN: {cm_h_d.get('tn', 0):<6}
```
""")
        with pcol2:
            st.markdown(f"""
**ARF Pr@{k_val}**: `{pr_k_arf_pct:.2f}%`
* **Rolling PR-AUC**: `{prauc_arf_val:.4f}` | **Scikit-learn AP**: `{sk_ap_arf_val:.4f}`
* **Overall fraud recall**: **`{tp_a:,} / {tot_frauds:,} ({g_acc_a:.1f}%)`**
* **Window**: `{win_size}` transactions (`{frauds_in_win}` frauds)
```text
ARF Confusion Matrix ({stats.get('total', 0):,} txs):
TP: {cm_a_d.get('tp', 0):<6} | FP: {cm_a_d.get('fp', 0):<6}
FN: {cm_a_d.get('fn', 0):<6} | TN: {cm_a_d.get('tn', 0):<6}
```
""")
        with pcol3:
            st.markdown(f"""
**Static RF Pr@{k_val}**: `{pr_k_rf_pct:.2f}%`
* **Rolling PR-AUC**: `{prauc_rf_val:.4f}` | **Scikit-learn AP**: `{sk_ap_rf_val:.4f}`
* **Overall fraud recall**: **`{tp_r:,} / {tot_frauds:,} ({g_acc_r:.1f}%)`**
* **Window**: `{win_size}` transactions (`{frauds_in_win}` frauds)
```text
Static RF Confusion Matrix ({stats.get('total', 0):,} txs):
TP: {cm_r_d.get('tp', 0):<6} | FP: {cm_r_d.get('fp', 0):<6}
FN: {cm_r_d.get('fn', 0):<6} | TN: {cm_r_d.get('tn', 0):<6}
```
""")
        st.divider()
        st.subheader("Recent Transactions (Audit Log)")
        disp_cols = ["transaction_id", "prob_hat", "prob_arf", "prob_rf", "action", "timestamp"]
        avail_cols = [c for c in disp_cols if c in df.columns]
        disp_df = df[avail_cols].copy()
        disp_df["timestamp"] = pd.to_datetime(disp_df["timestamp"], unit="s").dt.strftime("%H:%M:%S")
        disp_df = disp_df.iloc[::-1].reset_index(drop=True)
        st.dataframe(
            disp_df, width="stretch", hide_index=True,
            column_config={
                "transaction_id": st.column_config.TextColumn("Transaction ID"),
                "prob_hat": st.column_config.ProgressColumn("Fraud Probability (HAT)", min_value=0, max_value=1, format="%.4f"),
                "prob_arf": st.column_config.ProgressColumn("Fraud Probability (ARF)", min_value=0, max_value=1, format="%.4f"),
                "prob_rf": st.column_config.ProgressColumn("Fraud Probability (Static RF)", min_value=0, max_value=1, format="%.4f"),
                "action": st.column_config.TextColumn("Decision"),
                "timestamp": st.column_config.TextColumn("Time"),
            }
        )
    else:
        st.info("No transactions yet. Click 'Start Streaming' in the sidebar to begin.")

    # -------------------------------------------------------------
    # OPTIMIZE DEEP-DIVE PANEL
    # -------------------------------------------------------------
    st.divider()
    st.subheader("Optimization Details (Prioritized Replay & Augmentation)")
    col_cfg, col_aug = st.columns([1, 1])

    with col_cfg:
        st.markdown("#### Replay & Augmentation Settings")
        with st.form("form_optimize_cfg"):
            c_per = st.checkbox("Enable Prioritized Experience Replay (PER)", value=rep_cfg.get("enable_per", True), help="Prioritize replay samples in proportion to prediction error (Error = 1 - Fraud Probability). When unchecked, replay continues with uniform sampling.")
            c_noise = st.checkbox("Enable Gaussian Noise Augmentation", value=rep_cfg.get("enable_noise_aug", True), help="Add random Gaussian noise to features to generate variants during replay.")
            s_std = st.slider("Noise Standard Deviation", min_value=0.005, max_value=0.10, value=float(rep_cfg.get("noise_std", 0.02)), step=0.005)
            s_int = st.slider("Replay Interval (Every N Legitimate Transactions)", min_value=2, max_value=50, value=int(rep_cfg.get("replay_interval", 10)), step=1)

            submitted = st.form_submit_button("Apply Settings", type="primary", width="stretch")
            if submitted:
                ok = update_replay_config(c_per, c_noise, s_std, s_int)
                if ok:
                    st.success("Replay and augmentation settings updated successfully!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Could not connect to the server to update settings.")

    with col_aug:
        st.markdown("#### Augmented Fraud Sample Comparison")
        last_rep = rep_info.get("last_replay")
        if last_rep and last_rep.get("original") and last_rep.get("augmented"):
            orig = last_rep["original"]
            aug = last_rep["augmented"]
            target_keys = [k for k in ["V10", "V12", "V14", "V17", "Amount"] if k in orig] or list(orig.keys())[:5]

            comp_df = pd.DataFrame({
                "Feature": target_keys,
                "Original (Historical)": [orig[k] for k in target_keys],
                "Augmented": [aug[k] for k in target_keys]
            })

            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(x=comp_df["Feature"], y=comp_df["Original (Historical)"], name="Original (Historical)", marker_color="#3b82f6"))
            fig_comp.add_trace(go.Bar(x=comp_df["Feature"], y=comp_df["Augmented"], name="Augmented", marker_color="#f59e0b"))
            fig_comp.update_layout(
                barmode="group", template="plotly_dark", height=280,
                xaxis_title="Feature", yaxis_title="Feature Value",
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_comp, width="stretch", key="h3_chart_aug_comp")
            st.caption(f"Replay priority: **{last_rep.get('priority', 1.0):.4f}** | Prediction error: **{last_rep.get('error', 1.0):.4f}**")
        else:
            st.info("No samples have been replayed in this session. Stream transactions to see augmented variants.")

    st.divider()
    st.markdown("#### Hardest Fraud Samples in Memory (Hard Positives)")
    top_hardest = rep_info.get("top_hardest", [])
    if top_hardest:
        st.dataframe(
            pd.DataFrame(top_hardest), width="stretch",
            column_config={
                "error": st.column_config.NumberColumn("Prediction Error", format="%.4f"),
                "priority": st.column_config.NumberColumn("Replay Priority", format="%.4f"),
                "timestamp": st.column_config.NumberColumn("Timestamp (Unix seconds)", format="%.2f"),
            },
        )
        st.caption("Fraud samples with the highest prediction error (Error close to 1.0) receive the highest replay priority.")


render_dashboard()
