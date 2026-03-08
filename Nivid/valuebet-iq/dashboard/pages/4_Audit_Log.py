from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.api import get

st.set_page_config(page_title="Audit Log", layout="wide")
st.title("Audit Timeline")
st.caption("Structured trace of recommendation decisions, risk checks, and order actions.")

rows = get("/audit", params={"limit": 500})
if not rows:
    st.info("No audit records yet.")
    st.stop()

df = pd.DataFrame(rows)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp", ascending=False)

st.dataframe(df, use_container_width=True)

for _, row in df.head(40).iterrows():
    st.markdown(
        f"""
        <div style='padding:10px;border-left:3px solid #16e0bd;background:#121c2b;margin-bottom:8px;'>
            <b>{row['timestamp']}</b> • {row['action']} • {row['entity_type']} ({row['entity_id']})<br>
            <small>Actor: {row['actor']}</small><br>
            <small>{row['details']}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )
