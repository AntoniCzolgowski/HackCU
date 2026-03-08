from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import recommendation_counter
from app.db.models import Event, Market, OddsSnapshot, Outcome, Recommendation, TeamRating
from app.services.calculations import edge as calc_edge
from app.services.calculations import expected_value, implied_probability, normalize_probabilities
from app.services.external_context import fetch_team_news, fetch_weather_context
from app.services.providers import ProviderEvent
from app.services.risk import classify_risk_tier, evaluate_risk
from app.services.soccer_model import model_probs_for_market
from app.services.storage import add_audit_log, get_risk_control


def _get_or_create_team_rating(db: Session, team_name: str) -> TeamRating:
    rating = db.execute(select(TeamRating).where(TeamRating.team_name == team_name)).scalar_one_or_none()
    if rating:
        return rating
    rating = TeamRating(team_name=team_name, elo_rating=1500.0)
    db.add(rating)
    db.flush()
    return rating


def upsert_provider_events(db: Session, provider_name: str, events: list[ProviderEvent]) -> list[Event]:
    persisted: list[Event] = []
    for p_event in events:
        event = db.execute(
            select(Event).where(Event.provider_event_id == p_event.provider_event_id)
        ).scalar_one_or_none()

        if not event:
            event = Event(
                provider_event_id=p_event.provider_event_id,
                sport=p_event.sport,
                league=p_event.league,
                home_team=p_event.home_team,
                away_team=p_event.away_team,
                competition_stage=p_event.competition_stage,
                venue_name=p_event.venue_name,
                venue_city=p_event.venue_city,
                venue_country=p_event.venue_country,
                venue_lat=p_event.venue_lat,
                venue_lon=p_event.venue_lon,
                context_payload=p_event.context_payload or {},
                start_time=p_event.start_time,
                is_live=p_event.is_live,
                status=p_event.status,
            )
            db.add(event)
            db.flush()
        else:
            event.sport = p_event.sport
            event.league = p_event.league
            event.home_team = p_event.home_team
            event.away_team = p_event.away_team
            event.competition_stage = p_event.competition_stage
            event.venue_name = p_event.venue_name
            event.venue_city = p_event.venue_city
            event.venue_country = p_event.venue_country
            event.venue_lat = p_event.venue_lat
            event.venue_lon = p_event.venue_lon
            event.context_payload = p_event.context_payload or {}
            event.start_time = p_event.start_time
            event.is_live = p_event.is_live
            event.status = p_event.status

        _get_or_create_team_rating(db, event.home_team)
        _get_or_create_team_rating(db, event.away_team)

        for p_market in p_event.markets:
            market = db.execute(
                select(Market)
                .where(Market.event_id == event.id)
                .where(Market.market_key == p_market.key)
            ).scalar_one_or_none()
            if not market:
                market = Market(event_id=event.id, market_key=p_market.key, last_updated=p_market.last_updated)
                db.add(market)
                db.flush()
            else:
                market.last_updated = p_market.last_updated

            for p_outcome in p_market.outcomes:
                outcome = db.execute(
                    select(Outcome)
                    .where(Outcome.market_id == market.id)
                    .where(Outcome.name == p_outcome.name)
                ).scalar_one_or_none()
                if not outcome:
                    outcome = Outcome(market_id=market.id, name=p_outcome.name)
                    db.add(outcome)
                    db.flush()

                snapshot = OddsSnapshot(
                    event_id=event.id,
                    market_id=market.id,
                    outcome_id=outcome.id,
                    provider=provider_name,
                    timestamp=p_market.last_updated,
                    decimal_odds=p_outcome.decimal_odds,
                    implied_prob=implied_probability(p_outcome.decimal_odds),
                    raw_payload=p_outcome.raw,
                )
                db.add(snapshot)

        persisted.append(event)

    db.flush()
    return persisted


def _latest_snapshot(db: Session, outcome_id: str) -> OddsSnapshot | None:
    return db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.outcome_id == outcome_id)
        .order_by(OddsSnapshot.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()


def _previous_snapshot(db: Session, outcome_id: str) -> OddsSnapshot | None:
    rows = db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.outcome_id == outcome_id)
        .order_by(OddsSnapshot.timestamp.desc())
        .limit(2)
    ).scalars().all()
    if len(rows) < 2:
        return None
    return rows[1]


def generate_recommendations_for_event(db: Session, event_id: str) -> list[Recommendation]:
    settings = get_settings()
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one()
    control = get_risk_control(db)
    now = datetime.now(timezone.utc)

    recs: list[Recommendation] = []
    markets = db.execute(select(Market).where(Market.event_id == event_id)).scalars().all()

    home_rating = _get_or_create_team_rating(db, event.home_team)
    away_rating = _get_or_create_team_rating(db, event.away_team)

    weather = (
        fetch_weather_context(event.venue_lat, event.venue_lon, event.start_time)
        if settings.weather_enabled
        else {"available": False, "impact": 0.0, "summary": "Weather source disabled."}
    )
    news = (
        fetch_team_news([event.home_team, event.away_team], lookback_days=settings.news_lookback_days)
        if settings.news_enabled
        else {"sentiment_score": 0.0, "items": []}
    )
    news_score = float(news.get("sentiment_score", 0.0))

    event_context = event.context_payload or {}

    for market in markets:
        outcomes = db.execute(select(Outcome).where(Outcome.market_id == market.id)).scalars().all()

        latest_snapshots = []
        for outcome in outcomes:
            snap = _latest_snapshot(db, outcome.id)
            if snap:
                latest_snapshots.append((outcome, snap))

        if not latest_snapshots:
            continue

        outcome_names = [outcome.name for outcome, _ in latest_snapshots]
        implieds = [snap.implied_prob for _, snap in latest_snapshots]
        normalized = normalize_probabilities(implieds)

        model_probs, model_components = model_probs_for_market(
            market_key=market.market_key,
            outcome_names=outcome_names,
            normalized_market_probs=normalized,
            home_team=event.home_team,
            away_team=event.away_team,
            home_elo=home_rating.elo_rating,
            away_elo=away_rating.elo_rating,
            context=event_context,
            weather_impact=float(weather.get("impact", 0.0)),
            news_score=news_score,
        )

        for idx, (outcome, snap) in enumerate(latest_snapshots):
            normalized_prob = normalized[idx]
            model_prob = max(0.001, min(0.995, model_probs[idx]))

            rec_edge = calc_edge(model_prob, snap.implied_prob)
            ev = expected_value(model_prob, snap.decimal_odds)
            confidence = max(0.05, min(0.99, abs(rec_edge) * 9 + max(0.0, ev) * 1.4 + 0.28))

            reasons = [
                f"Market={market.market_key}. Implied={snap.implied_prob:.3f}, normalized={normalized_prob:.3f}, model={model_prob:.3f}.",
                f"Edge={rec_edge:.3f}, EV={ev:.3f}, confidence={confidence:.2f}.",
                f"Weather: {weather.get('summary', 'n/a')}",
                f"News sentiment score={news_score:.2f} from {len(news.get('items', []))} headlines.",
            ]

            snap_ts = snap.timestamp
            if snap_ts.tzinfo is None:
                snap_ts = snap_ts.replace(tzinfo=timezone.utc)
            fresh_seconds = (now - snap_ts).total_seconds()
            is_fresh = fresh_seconds <= control.data_freshness_seconds
            if not is_fresh:
                reasons.append(f"Odds stale: {int(fresh_seconds)}s old (limit {control.data_freshness_seconds}s).")

            prev = _previous_snapshot(db, outcome.id)
            drift = 0.0
            if prev and prev.decimal_odds > 0:
                drift = abs(snap.decimal_odds - prev.decimal_odds) / prev.decimal_odds
            if drift > control.max_odds_drift_pct:
                reasons.append(f"Odds drift {drift:.2%} exceeds tolerance {control.max_odds_drift_pct:.2%}.")

            label = "NO_BET"
            if is_fresh and drift <= control.max_odds_drift_pct and rec_edge >= control.min_edge and ev >= control.min_ev:
                risk_result = evaluate_risk(
                    db=db,
                    event_id=event_id,
                    control=control,
                    model_prob=model_prob,
                    odds=snap.decimal_odds,
                )
                if not risk_result.passed:
                    label = "BLOCKED_BY_RISK"
                    reasons.extend(risk_result.reasons)
                elif rec_edge >= control.top_pick_edge and ev >= control.top_pick_ev and confidence >= 0.55:
                    label = "TOP_PICK"
                    reasons.append("Qualified as TOP_PICK: edge, EV and confidence all strong.")
                else:
                    label = "LEAN"
                    reasons.append("Qualified as LEAN: positive edge and EV with acceptable confidence.")
            else:
                if rec_edge < control.min_edge:
                    reasons.append(f"Edge below threshold ({rec_edge:.3f} < {control.min_edge:.3f}).")
                if ev < control.min_ev:
                    reasons.append(f"EV below threshold ({ev:.3f} < {control.min_ev:.3f}).")

            # Volatile niche markets are intentionally constrained for safety.
            if market.market_key == "correct_score" and label in {"TOP_PICK", "LEAN"}:
                if model_prob < 0.12 or confidence < 0.65:
                    label = "NO_BET"
                    reasons.append("Correct score market blocked: probability/confidence not robust enough.")
                else:
                    label = "LEAN"
                    reasons.append("Correct score market capped to LEAN due volatility.")
            if market.market_key in {"player_goal_or_assist", "player_anytime_scorer"} and label == "TOP_PICK":
                label = "LEAN"
                reasons.append("Player prop capped to LEAN to control volatility.")

            risk_tier = classify_risk_tier(snap.decimal_odds, rec_edge, label)

            recommendation = Recommendation(
                event_id=event_id,
                market_id=market.id,
                outcome_id=outcome.id,
                implied_prob=snap.implied_prob,
                normalized_implied_prob=normalized_prob,
                model_prob=model_prob,
                edge=rec_edge,
                expected_value=ev,
                confidence=confidence,
                recommendation_label=label,
                risk_tier=risk_tier,
                rationale=reasons,
                model_components={
                    **model_components,
                    "market_key": market.market_key,
                    "outcome": outcome.name,
                    "weather": weather,
                    "news_sample": news.get("items", [])[:8],
                },
            )
            db.add(recommendation)
            db.flush()

            add_audit_log(
                db,
                action="RECOMMENDATION_GENERATED",
                entity_type="recommendation",
                entity_id=recommendation.id,
                details={
                    "event_id": event_id,
                    "market": market.market_key,
                    "outcome": outcome.name,
                    "label": label,
                    "risk_tier": risk_tier,
                    "edge": rec_edge,
                    "ev": ev,
                },
            )
            recommendation_counter.labels(label=label, risk_tier=risk_tier).inc()
            recs.append(recommendation)

    return recs


def latest_recommendations_for_event(db: Session, event_id: str) -> list[Recommendation]:
    rows = db.execute(
        select(Recommendation)
        .where(Recommendation.event_id == event_id)
        .order_by(Recommendation.created_at.desc())
    ).scalars().all()

    by_key: dict[tuple[str, str], Recommendation] = {}
    for row in rows:
        key = (row.market_id, row.outcome_id)
        if key not in by_key:
            by_key[key] = row
    return sorted(by_key.values(), key=lambda r: (r.expected_value, r.edge), reverse=True)


def latest_recommendations_all_events(db: Session) -> list[Recommendation]:
    rows = db.execute(select(Recommendation).order_by(Recommendation.created_at.desc())).scalars().all()
    by_key: dict[tuple[str, str, str], Recommendation] = {}
    for row in rows:
        key = (row.event_id, row.market_id, row.outcome_id)
        if key not in by_key:
            by_key[key] = row
    return list(by_key.values())


def odds_history_for_event(db: Session, event_id: str) -> dict[str, list[dict]]:
    rows = db.execute(
        select(Outcome.name, OddsSnapshot.timestamp, OddsSnapshot.decimal_odds)
        .join(OddsSnapshot, OddsSnapshot.outcome_id == Outcome.id)
        .where(OddsSnapshot.event_id == event_id)
        .order_by(OddsSnapshot.timestamp.asc())
    ).all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for name, ts, odds in rows:
        grouped[name].append({"timestamp": ts, "odds": odds})
    return grouped


def probability_p_chart(db: Session, event_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Recommendation.created_at, Outcome.name, Recommendation.model_prob)
        .join(Outcome, Outcome.id == Recommendation.outcome_id)
        .where(Recommendation.event_id == event_id)
        .order_by(Recommendation.created_at.asc())
    ).all()

    by_outcome: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for ts, outcome, p in rows:
        by_outcome[outcome].append((ts, float(p)))

    output: list[dict[str, Any]] = []
    for outcome, points in by_outcome.items():
        vals = [p for _, p in points]
        if len(vals) < 2:
            continue
        p_bar = mean(vals)
        sigma = (p_bar * (1 - p_bar) / max(1, len(vals))) ** 0.5
        ucl = min(1.0, p_bar + 3 * sigma)
        lcl = max(0.0, p_bar - 3 * sigma)
        for ts, p in points:
            output.append(
                {
                    "timestamp": ts,
                    "outcome": outcome,
                    "probability": p,
                    "center_line": p_bar,
                    "ucl": ucl,
                    "lcl": lcl,
                }
            )
    return output


def event_analysis_snapshot(db: Session, event_id: str) -> dict[str, Any]:
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        return {}

    recs = latest_recommendations_for_event(db, event_id)
    best = next((r for r in recs if r.recommendation_label in {"TOP_PICK", "LEAN"}), None)

    components = (best.model_components or {}) if best else {}
    return {
        "event_id": event_id,
        "weather": components.get("weather", {}),
        "ground": {
            "venue": event.venue_name,
            "city": event.venue_city,
            "country": event.venue_country,
            "stage": event.competition_stage,
            "pitch_type": (event.context_payload or {}).get("pitch_type"),
            "altitude_m": (event.context_payload or {}).get("altitude_m"),
        },
        "team_standings": {
            "home": (event.context_payload or {}).get("home_standing", {}),
            "away": (event.context_payload or {}).get("away_standing", {}),
        },
        "player_availability": (event.context_payload or {}).get("players", []),
        "news_digest": components.get("news_sample", []),
        "risk_flags": [r for r in (best.rationale if best else []) if "Odds stale" in r or "drift" in r.lower()],
        "recommended_bet": {
            "outcome_id": best.outcome_id,
            "market_id": best.market_id,
            "label": best.recommendation_label,
            "edge": best.edge,
            "ev": best.expected_value,
            "confidence": best.confidence,
            "rationale": best.rationale,
        }
        if best
        else None,
    }
