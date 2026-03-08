from __future__ import annotations

import streamlit as st

from utils.api import get, post, put

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings and Risk Controls")
st.caption("LIVE execution is optional and disabled by default. SIM mode is recommended for demos.")

settings = get("/settings/risk")

with st.form("risk_form"):
    c1, c2, c3 = st.columns(3)
    max_stake = c1.number_input("Max Stake", value=float(settings["max_stake"]), min_value=1.0)
    max_exposure = c2.number_input("Max Exposure / Event", value=float(settings["max_exposure_per_event"]), min_value=1.0)
    max_daily_loss = c3.number_input("Max Daily Loss", value=float(settings["max_daily_loss"]), min_value=1.0)

    c4, c5, c6 = st.columns(3)
    min_edge = c4.number_input("Min Edge", value=float(settings["min_edge"]), min_value=0.0, max_value=1.0, step=0.001)
    min_ev = c5.number_input("Min EV", value=float(settings["min_ev"]), min_value=-1.0, max_value=1.0, step=0.001)
    top_pick_edge = c6.number_input("Top Pick Edge", value=float(settings["top_pick_edge"]), min_value=0.0, max_value=1.0, step=0.001)

    c7, c8, c9 = st.columns(3)
    top_pick_ev = c7.number_input("Top Pick EV", value=float(settings["top_pick_ev"]), min_value=-1.0, max_value=2.0, step=0.001)
    freshness = c8.number_input("Data Freshness (s)", value=int(settings["data_freshness_seconds"]), min_value=5)
    drift = c9.number_input("Max Odds Drift", value=float(settings["max_odds_drift_pct"]), min_value=0.0, max_value=1.0, step=0.001)

    c10, c11, c12 = st.columns(3)
    flat_stake = c10.number_input("Default Flat Stake", value=float(settings["default_flat_stake"]), min_value=1.0)
    use_kelly = c11.toggle("Use Fractional Kelly", value=bool(settings["fractional_kelly_enabled"]))
    kelly_factor = c12.number_input("Kelly Factor", value=float(settings["fractional_kelly_factor"]), min_value=0.0, max_value=1.0, step=0.01)

    mode = st.selectbox("Execution Mode", options=["SIM", "LIVE"], index=0 if settings["execution_mode"] == "SIM" else 1)
    live_enabled = st.toggle("Enable LIVE endpoints", value=bool(settings["live_enabled"]))
    kill_switch = st.toggle("Kill Switch", value=bool(settings["kill_switch_enabled"]))

    submitted = st.form_submit_button("Save Controls")

if submitted:
    payload = {
        "max_stake": max_stake,
        "max_exposure_per_event": max_exposure,
        "max_daily_loss": max_daily_loss,
        "min_edge": min_edge,
        "min_ev": min_ev,
        "top_pick_edge": top_pick_edge,
        "top_pick_ev": top_pick_ev,
        "data_freshness_seconds": int(freshness),
        "max_odds_drift_pct": drift,
        "default_flat_stake": flat_stake,
        "fractional_kelly_enabled": use_kelly,
        "fractional_kelly_factor": kelly_factor,
        "execution_mode": mode,
        "live_enabled": live_enabled,
        "kill_switch_enabled": kill_switch,
    }
    try:
        put("/settings/risk", payload)
        st.success("Risk controls updated")
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))

st.divider()
st.subheader("LIVE Mode Confirmation Gate")
st.warning(
    "LIVE mode should only be used with official exchange APIs (Betfair/Matchbook) and remains disabled by default in this demo."
)

confirm_toggle = st.checkbox("I understand this app is decision-support only and not guaranteed profit prediction.")
phrase = st.text_input("Type exact phrase to acknowledge risk", placeholder="ENABLE LIVE EXECUTION")
if st.button("Arm LIVE Mode"):
    if not confirm_toggle or phrase.strip() != "ENABLE LIVE EXECUTION":
        st.error("Confirmation gate failed. LIVE mode not armed.")
    else:
        st.success("Confirmation accepted. LIVE can only work if backend feature flags and adapters are configured.")

if st.button("Emergency Kill Switch: ON"):
    try:
        post("/settings/kill-switch", params={"enabled": True})
        st.success("Kill switch enabled")
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))

if st.button("Kill Switch: OFF"):
    try:
        post("/settings/kill-switch", params={"enabled": False})
        st.success("Kill switch disabled")
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
