from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.api import get, post

st.set_page_config(page_title="Bankroll & Simulation", layout="wide")
st.title("Bankroll and Simulation")

summary = get("/bankroll")
ledger = get("/bankroll/curve")
exposure = get("/exposure")
bets = get("/bets")

k1, k2, k3 = st.columns(3)
k1.metric("Balance", f"${summary['balance']:.2f}")
k2.metric("Daily PnL", f"${summary['daily_pnl']:.2f}")
k3.metric("Open Exposure", f"${summary['open_exposure']:.2f}")

left, right = st.columns(2)

with left:
    st.subheader("Bankroll Curve")
    if ledger:
        df = pd.DataFrame(ledger)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        fig = px.line(df, x="timestamp", y="balance_after", title="Balance Over Time", markers=True)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Risk Exposure")
    if exposure:
        exp_df = pd.DataFrame(exposure)
        fig = px.pie(exp_df, values="exposure", names="event", hole=0.5, title="Exposure by Event")
        st.plotly_chart(fig, use_container_width=True)

st.subheader("SIM Broker")
if "selected_event_id" in st.session_state:
    event_id = st.session_state["selected_event_id"]
    recs = get(f"/events/{event_id}/recommendations")
    candidate = [r for r in recs if r["recommendation_label"] in {"TOP_PICK", "LEAN", "BLOCKED_BY_RISK"}]
    if candidate:
        labels = [f"{r['outcome_name']} ({r['recommendation_label']}) EV={r['expected_value']:.2%}" for r in candidate]
        selected = st.selectbox("Recommendation", options=labels)
        rec = candidate[labels.index(selected)]
        stake = st.number_input("Stake", min_value=1.0, max_value=500.0, value=25.0, step=1.0)

        if st.button("Submit SIM Bet"):
            try:
                response = post(
                    "/bets/simulate",
                    data={
                        "recommendation_id": rec["recommendation_id"],
                        "event_id": rec["event_id"],
                        "outcome_id": rec["outcome_id"],
                        "stake": stake,
                        "odds_requested": max(1.01, 1 / rec["implied_prob"]),
                        "idempotency_key": f"manual-{uuid.uuid4()}",
                    },
                )
                st.success(f"SIM order placed: {response['id']}")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

st.subheader("Settle SIM Bets")
open_bets = [b for b in bets if b["status"] in {"PLACED", "PENDING"} and b["mode"] == "SIM"]
if open_bets:
    bet_labels = [f"{b['id']} | stake={b['stake']} | odds={b['odds_executed'] or b['odds_requested']}" for b in open_bets]
    chosen = st.selectbox("Open Bet", options=bet_labels)
    bet = open_bets[bet_labels.index(chosen)]
    won = st.toggle("Mark as Win", value=False)
    if st.button("Settle Selected Bet"):
        try:
            post("/bets/settle", data={"bet_id": bet["id"], "won": won})
            st.success("Bet settled")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

st.subheader("Bet Tickets")
if bets:
    st.dataframe(pd.DataFrame(bets), use_container_width=True)
