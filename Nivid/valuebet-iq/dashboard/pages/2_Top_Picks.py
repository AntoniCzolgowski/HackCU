from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.api import get

st.set_page_config(page_title="Top Picks", layout="wide")
st.title("Top Picks")
st.caption("Ranked opportunities sorted by EV and edge with risk-aware labels.")

cards = get("/top-picks", params={"limit": 100})
if not cards:
    st.info("No top picks available yet.")
    st.stop()

df = pd.DataFrame(cards)
df = df.sort_values(["expected_value", "edge"], ascending=False)

st.dataframe(df, use_container_width=True)

for _, row in df.head(8).iterrows():
    badge_color = {
        "TOP_PICK": "#16e0bd",
        "LEAN": "#3f8cff",
    }.get(row["recommendation_label"], "#8f9bb3")
    st.markdown(
        f"""
        <div style='padding:14px;border-radius:10px;background:#121c2b;border:1px solid #1f3652;margin-bottom:10px;'>
            <div style='color:{badge_color};font-weight:700'>{row['recommendation_label']} • {row['risk_tier']}</div>
            <div style='font-size:18px;font-weight:700'>{row['event_label']}</div>
            <div>Market: {row['market_key']} | Selection: {row['outcome_name']}</div>
            <div>Edge: {row['edge']:.2%} | EV: {row['expected_value']:.2%} | Odds: {row['odds']:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
