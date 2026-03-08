from __future__ import annotations

from datetime import datetime
import uuid

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.api import get, post

st.set_page_config(page_title="Bookie Buddy | World Cup Lab", page_icon="IQ", layout="wide")
MAX_MATCHES = 5

st.markdown(
    """
    <style>
    .stApp {
      background: radial-gradient(circle at 15% -10%, #1d3a5d 0%, #0c1624 40%, #050a12 100%);
      color: #ebf5ff;
    }
    .glow-card {
      background: linear-gradient(160deg, rgba(13,28,46,0.95), rgba(11,21,34,0.95));
      border: 1px solid rgba(55,123,192,0.45);
      box-shadow: 0 0 28px rgba(44, 146, 255, 0.16);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 10px;
    }
    .kpi-title {font-size: 12px; color: #87b8e8; text-transform: uppercase; letter-spacing: 1px;}
    .kpi-val {font-size: 28px; font-weight: 700; color: #f6fbff;}
    .badge {
      border-radius: 999px;
      padding: 2px 8px;
      border: 1px solid #356da7;
      color: #b8e2ff;
      font-size: 12px;
      margin-right: 8px;
    }
    .risk-high {color: #ff7f7f}
    .risk-med {color: #ffd166}
    .risk-low {color: #65fbd2}
    .market-shell {
      border: 1px solid rgba(69, 129, 193, 0.40);
      background: linear-gradient(155deg, rgba(8,19,33,0.95), rgba(5,11,18,0.95));
      border-radius: 14px;
      padding: 12px;
      margin-bottom: 10px;
    }
    .market-title {font-size: 15px; color: #b4d9ff; letter-spacing: .5px; margin-bottom: 8px;}
    .market-row {
      border: 1px solid rgba(59, 140, 213, 0.40);
      background: linear-gradient(160deg, rgba(14,31,52,0.90), rgba(12,20,34,0.92));
      border-radius: 12px;
      padding: 10px;
      min-height: 100px;
      margin-bottom: 8px;
    }
    .market-sel {font-size: 16px; font-weight: 700; color: #f1f7ff;}
    .market-odds {font-size: 26px; font-weight: 800; color: #3ef5cf;}
    .market-sub {font-size: 12px; color: #9ec6ec;}
    .pick-card {
      border: 1px solid rgba(95, 168, 240, 0.45);
      border-left: 4px solid #57e6be;
      background: linear-gradient(165deg, rgba(14,27,45,0.96), rgba(8,16,28,0.96));
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 10px;
      box-shadow: 0 0 24px rgba(66, 176, 255, 0.14);
    }
    .pick-head {display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;}
    .pick-label {font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #8ec6fb;}
    .pick-market {font-size: 11px; color: #8fead5; border: 1px solid rgba(68,187,154,.5); border-radius: 999px; padding: 1px 8px;}
    .pick-outcome {font-size: 19px; font-weight: 700; color: #f6fbff; margin-bottom: 3px;}
    .pick-metrics {font-size: 13px; color: #aad4ff;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Bookie Buddy: FIFA World Cup Edge Engine")
st.caption("Decision-support only. SIM mode default. Uses odds, player/team context, weather, and current news signals.")

with st.sidebar:
    st.header("World Cup Match Browser")
    all_events = get("/events", params={"limit": MAX_MATCHES})

    if st.button("Refresh Odds + Model", use_container_width=True):
        for ev in all_events:
            post(f"/events/{ev['id']}/recommendations/refresh")
        st.success("World Cup board refreshed")
        all_events = get("/events", params={"limit": MAX_MATCHES})

    live_state = st.selectbox("State", ["All", "Live", "Pre-match"])
    stage_set = sorted({e.get("competition_stage") or "Unknown" for e in all_events})
    stage_pick = st.selectbox("Stage", ["All"] + stage_set)

    filt = []
    for ev in all_events:
        if live_state == "Live" and not ev["is_live"]:
            continue
        if live_state == "Pre-match" and ev["is_live"]:
            continue
        if stage_pick != "All" and (ev.get("competition_stage") or "Unknown") != stage_pick:
            continue
        filt.append(ev)

    labels = [f"{e['away_team']} vs {e['home_team']}" for e in filt]
    if not labels:
        st.warning("No World Cup events yet.")
        st.stop()

    idx = 0
    if st.session_state.get("selected_event_id"):
        for i, ev in enumerate(filt):
            if ev["id"] == st.session_state["selected_event_id"]:
                idx = i
                break

    selected_label = st.radio("Matches", options=labels, index=idx)
    selected_event = filt[labels.index(selected_label)]
    st.session_state["selected_event_id"] = selected_event["id"]

    st.markdown("---")
    st.markdown("`SIM` active by default. `LIVE` requires explicit confirmation + feature flags.")

event_id = selected_event["id"]
recs = get(f"/events/{event_id}/recommendations")
markets = get(f"/events/{event_id}/markets")
history = get(f"/events/{event_id}/odds-history")
analysis = get(f"/events/{event_id}/analysis")
p_chart = get(f"/events/{event_id}/p-chart")
top_cards = get("/top-picks", params={"limit": 6})
bankroll = get("/bankroll")

weather = analysis.get("weather", {})
news_count = len(analysis.get("news_digest", []))
recommended = analysis.get("recommended_bet")

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"<div class='glow-card'><div class='kpi-title'>Bankroll</div><div class='kpi-val'>${bankroll['balance']:.2f}</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='glow-card'><div class='kpi-title'>Daily PnL</div><div class='kpi-val'>${bankroll['daily_pnl']:.2f}</div></div>", unsafe_allow_html=True)
k3.markdown(f"<div class='glow-card'><div class='kpi-title'>News Signals</div><div class='kpi-val'>{news_count}</div></div>", unsafe_allow_html=True)
k4.markdown(f"<div class='glow-card'><div class='kpi-title'>Weather Impact</div><div class='kpi-val'>{weather.get('impact', 0.0):+.2f}</div></div>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class='glow-card'>
      <span class='badge'>{selected_event.get('competition_stage') or 'Stage NA'}</span>
      <span class='badge'>{selected_event.get('venue_name') or analysis.get('ground', {}).get('venue') or 'Venue TBD'}</span>
      <span class='badge'>{selected_event.get('venue_city') or analysis.get('ground', {}).get('city') or ''}</span>
      <h3 style='margin:8px 0 0 0'>{selected_event['away_team']} vs {selected_event['home_team']}</h3>
      <p style='margin:3px 0 0 0'>Kickoff: {selected_event['start_time']} | Status: {'LIVE' if selected_event['is_live'] else 'PRE-MATCH'}</p>
      <p style='margin:4px 0 0 0'>Weather: {weather.get('summary', 'No data')}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Market Board (World Cup)")
if markets:
    rec_lookup = {r["outcome_id"]: r for r in recs}
    market_keys = [m["market_key"] for m in markets]
    tab_titles = [f"{m}" for m in market_keys]
    tabs = st.tabs(tab_titles)

    for idx, market in enumerate(markets):
        with tabs[idx]:
            st.markdown(f"<div class='market-shell'><div class='market-title'>{market['market_key'].upper()}</div></div>", unsafe_allow_html=True)
            outcomes = market["outcomes"]
            cols = st.columns(3)
            for j, o in enumerate(outcomes):
                card_col = cols[j % 3]
                linked = rec_lookup.get(o["outcome_id"], {})
                edge = linked.get("edge")
                ev = linked.get("expected_value")
                badge = linked.get("recommendation_label", "NO_SIGNAL")
                badge_color = "#57e6be" if badge == "TOP_PICK" else "#7fb3ff" if badge == "LEAN" else "#a0acbc"
                edge_txt = f"Edge {edge:+.2%}" if edge is not None else "Edge n/a"
                ev_txt = f"EV {ev:+.2%}" if ev is not None else "EV n/a"
                card_col.markdown(
                    f"""
                    <div class='market-row'>
                      <div class='market-sel'>{o['outcome_name']}</div>
                      <div class='market-odds'>{o['decimal_odds']:.2f}</div>
                      <div class='market-sub'>Implied {(o['implied_prob'] * 100):.1f}% • {edge_txt} • {ev_txt}</div>
                      <div style='margin-top:7px; font-size:11px; color:{badge_color}; font-weight:700;'>{badge}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.subheader("Recommendation Engine Output")
if recs:
    rec_df = pd.DataFrame(recs)
    ctl1, ctl2, ctl3, ctl4 = st.columns([1.2, 1, 1, 1.2])
    label_filter = ctl1.multiselect(
        "Label Filter",
        ["TOP_PICK", "LEAN", "BLOCKED_BY_RISK", "NO_BET"],
        default=["TOP_PICK", "LEAN", "BLOCKED_BY_RISK"],
    )
    market_filter = ctl2.multiselect("Market Filter", sorted(rec_df["model_components"].apply(lambda x: (x or {}).get("market_key", "unknown")).unique().tolist()))
    min_conf = ctl3.slider("Min Confidence", 0.0, 1.0, 0.30, 0.05)
    sort_key = ctl4.selectbox("Sort By", ["expected_value", "edge", "confidence"])

    rec_df["market_key"] = rec_df["model_components"].apply(lambda x: (x or {}).get("market_key", "unknown"))
    filt_df = rec_df[rec_df["recommendation_label"].isin(label_filter)]
    filt_df = filt_df[filt_df["confidence"] >= min_conf]
    if market_filter:
        filt_df = filt_df[filt_df["market_key"].isin(market_filter)]
    filt_df = filt_df.sort_values([sort_key, "edge"], ascending=False)

    card_cols = st.columns(2)
    for i, rec in enumerate(filt_df.to_dict(orient="records")):
        col = card_cols[i % 2]
        col.markdown(
            f"""
            <div class='pick-card'>
              <div class='pick-head'>
                <div class='pick-label'>{rec['recommendation_label']} • {rec['risk_tier']}</div>
                <div class='pick-market'>{rec['market_key']}</div>
              </div>
              <div class='pick-outcome'>{rec['outcome_name']}</div>
              <div class='pick-metrics'>Odds {(1 / rec['implied_prob']):.2f} • EV {rec['expected_value']:+.2%} • Edge {rec['edge']:+.2%} • Confidence {rec['confidence']:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with col.expander(f"Details • {rec['outcome_name']}", expanded=False):
            for reason in rec.get("rationale", [])[:6]:
                st.write(f"- {reason}")
            if rec["recommendation_label"] in {"TOP_PICK", "LEAN"}:
                if st.button(f"SIM {rec['outcome_name']}", key=f"home_sim_{rec['recommendation_id']}"):
                    post(
                        "/bets/simulate",
                        data={
                            "recommendation_id": rec["recommendation_id"],
                            "event_id": rec["event_id"],
                            "outcome_id": rec["outcome_id"],
                            "stake": 25.0,
                            "odds_requested": max(1.01, 1 / rec["implied_prob"]),
                            "idempotency_key": f"home-{uuid.uuid4()}",
                        },
                    )
                    st.success("SIM order submitted")

    if filt_df.empty:
        st.info("No picks match the current filters. Relax market/label/confidence filters.")
    else:
        prob_df = filt_df[["outcome_name", "implied_prob", "model_prob"]].melt(
            id_vars="outcome_name", var_name="source", value_name="probability"
        )
        fig_prob = px.bar(
            prob_df,
            x="outcome_name",
            y="probability",
            color="source",
            barmode="group",
            color_discrete_sequence=["#3f8cff", "#1effc7"],
            title="Implied vs Model Probability",
        )
        fig_prob.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_prob, use_container_width=True)

c1, c2 = st.columns(2)

with c1:
    st.subheader("Odds Movement")
    long_rows = []
    for outcome_name, points in history.items():
        for p in points:
            long_rows.append({"outcome": outcome_name, "timestamp": pd.to_datetime(p["timestamp"]), "odds": p["odds"]})
    if long_rows:
        h_df = pd.DataFrame(long_rows)
        fig_line = px.line(h_df, x="timestamp", y="odds", color="outcome", markers=True)
        fig_line.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.subheader("Probability Control (p-chart)")
    if p_chart:
        p_df = pd.DataFrame(p_chart)
        p_df["timestamp"] = pd.to_datetime(p_df["timestamp"])
        fig = go.Figure()
        for outcome in sorted(p_df["outcome"].unique()):
            sdf = p_df[p_df["outcome"] == outcome]
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["probability"], mode="lines+markers", name=f"{outcome} p"))
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["center_line"], mode="lines", name=f"{outcome} CL", line=dict(dash="dot")))
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["ucl"], mode="lines", name=f"{outcome} UCL", line=dict(dash="dash")))
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["lcl"], mode="lines", name=f"{outcome} LCL", line=dict(dash="dash")))
        fig.update_layout(yaxis=dict(range=[0, 1]), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Correct Score Matrix")
if recs:
    components = recs[0].get("model_components", {}) if isinstance(recs[0], dict) else {}
    matrix = components.get("score_matrix", {})
    if matrix:
        heat = []
        for score, prob in matrix.items():
            h, a = [int(x) for x in score.split("-")]
            heat.append({"home_goals": h, "away_goals": a, "probability": prob})
        heat_df = pd.DataFrame(heat)
        fig_heat = px.density_heatmap(
            heat_df,
            x="home_goals",
            y="away_goals",
            z="probability",
            color_continuous_scale="Blues",
            title="Poisson Score Probability Heatmap",
        )
        fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)

st.subheader("News and Team Notes")
left, right = st.columns(2)
with left:
    st.markdown("#### Latest Team News")
    news_rows = analysis.get("news_digest", [])
    if news_rows:
        for item in news_rows[:8]:
            st.markdown(f"- **{item.get('team','')}**: {item.get('title','')}  ")
    else:
        st.write("No news items captured in this cycle.")

with right:
    st.markdown("#### Recommended Bet Summary")
    if recommended:
        st.success(
            f"{recommended['label']} | EV={recommended['ev']:.2%} | Edge={recommended['edge']:.2%} | Confidence={recommended['confidence']:.2f}"
        )
        for reason in recommended.get("rationale", [])[:6]:
            st.write(f"- {reason}")
    else:
        st.info("No positive recommendation yet. Wait for next odds/news/weather cycle.")

st.subheader("Top Picks Across World Cup Board")
card_cols = st.columns(3)
for i, card in enumerate(top_cards[:6]):
    col = card_cols[i % 3]
    col.markdown(
        f"""
        <div class='glow-card'>
          <div style='font-size:12px;color:#8bc8ff'>{card['recommendation_label']} • {card['risk_tier']} • {card['market_key']}</div>
          <h4 style='margin:6px 0'>{card['event_label']}</h4>
          <p style='margin:0'>Selection: {card['outcome_name']}</p>
          <p style='margin:0'>Edge: {card['edge']:.2%} | EV: {card['expected_value']:.2%}</p>
          <p style='margin:0'>Odds: {card['odds']:.2f}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
