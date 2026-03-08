from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from utils.api import get, post

st.set_page_config(page_title="Match Detail", layout="wide")
st.title("Deep Match Detail")

if "selected_event_id" not in st.session_state:
    st.info("Select a World Cup event from Dashboard first.")
    st.stop()

event_id = st.session_state["selected_event_id"]
event = get(f"/events/{event_id}")
markets = get(f"/events/{event_id}/markets")
recs = get(f"/events/{event_id}/recommendations")
analysis = get(f"/events/{event_id}/analysis")

st.markdown(
    f"""
    ### {event['away_team']} vs {event['home_team']}
    {event.get('competition_stage') or 'Stage NA'} • {event.get('venue_name') or analysis.get('ground', {}).get('venue') or 'Venue TBD'}
    """
)

left, right = st.columns([1.3, 1])

with left:
    st.markdown("#### Markets")
    rows = []
    for market in markets:
        for outcome in market["outcomes"]:
            rows.append(
                {
                    "market": market["market_key"],
                    "selection": outcome["outcome_name"],
                    "odds": outcome["decimal_odds"],
                    "implied_prob": outcome["implied_prob"],
                }
            )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("#### Player Availability")
    players = analysis.get("player_availability", [])
    if players:
        st.dataframe(pd.DataFrame(players), use_container_width=True)

with right:
    st.markdown("#### Recommendation Cards")
    if recs:
        for rec in sorted(recs, key=lambda x: x["expected_value"], reverse=True):
            with st.container(border=True):
                st.markdown(
                    f"**{rec['outcome_name']}**  \
                    `{rec['recommendation_label']}` | EV `{rec['expected_value']:.2%}` | Edge `{rec['edge']:.2%}`"
                )
                for reason in rec.get("rationale", [])[:4]:
                    st.write(f"- {reason}")

                if rec["recommendation_label"] in {"TOP_PICK", "LEAN"}:
                    if st.button(f"SIM Bet: {rec['outcome_name']}", key=f"sim_{rec['recommendation_id']}"):
                        payload = {
                            "recommendation_id": rec["recommendation_id"],
                            "event_id": rec["event_id"],
                            "outcome_id": rec["outcome_id"],
                            "stake": 25.0,
                            "odds_requested": max(1.01, 1 / rec["implied_prob"]),
                            "idempotency_key": f"detail-{uuid.uuid4()}",
                        }
                        post("/bets/simulate", data=payload)
                        st.success("SIM order submitted")

st.markdown("#### Weather + News Impact")
st.write(analysis.get("weather", {}))
for item in analysis.get("news_digest", [])[:10]:
    st.markdown(f"- **{item.get('team', '')}**: {item.get('title', '')}")
