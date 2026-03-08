from __future__ import annotations

import math
from typing import Any

from app.services.model_prob import blend_market_and_strength


def poisson_pmf(lmbda: float, k: int) -> float:
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lmbda) * (lmbda**k) / math.factorial(k)


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 5) -> dict[str, float]:
    matrix: dict[str, float] = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            matrix[f"{h}-{a}"] = poisson_pmf(lambda_home, h) * poisson_pmf(lambda_away, a)
    return matrix


def form_index(form: list[str]) -> float:
    points = 0
    for ch in form:
        if ch.upper() == "W":
            points += 3
        elif ch.upper() == "D":
            points += 1
    return points / max(1, len(form) * 3)


def standing_index(standing: dict[str, Any]) -> float:
    points = float(standing.get("points", 0))
    gd = float(standing.get("goal_diff", 0))
    rank = float(standing.get("group_rank", 4))
    return points * 0.06 + gd * 0.01 - rank * 0.02


def player_impact_index(players: list[dict[str, Any]], team_name: str) -> float:
    impact = 0.0
    for player in players:
        if player.get("team") != team_name:
            continue
        base = float(player.get("impact", 0.0))
        status = str(player.get("status", "available")).lower()
        fitness = float(player.get("fitness", 1.0))
        if status in {"injured", "suspended", "out", "doubtful"}:
            impact -= abs(base) * 0.05
        else:
            impact += abs(base) * 0.02 * max(0.0, min(1.0, fitness))
    return impact


def lambdas_from_context(event_context: dict[str, Any], weather_impact: float, news_impact: float) -> tuple[float, float]:
    home_attack = float(event_context.get("home_team_xg", 1.4))
    away_attack = float(event_context.get("away_team_xg", 1.2))
    home_def = float(event_context.get("home_team_xga", 1.1))
    away_def = float(event_context.get("away_team_xga", 1.2))

    lambda_home = max(0.35, home_attack * (1.35 - away_def * 0.25))
    lambda_away = max(0.30, away_attack * (1.35 - home_def * 0.25))

    # News and weather are small but meaningful perturbations.
    lambda_home = max(0.25, lambda_home * (1.0 + weather_impact + news_impact * 0.5))
    lambda_away = max(0.25, lambda_away * (1.0 + weather_impact - news_impact * 0.5))
    return lambda_home, lambda_away


def model_probs_for_market(
    market_key: str,
    outcome_names: list[str],
    normalized_market_probs: list[float],
    home_team: str,
    away_team: str,
    home_elo: float,
    away_elo: float,
    context: dict[str, Any],
    weather_impact: float,
    news_score: float,
) -> tuple[list[float], dict[str, Any]]:
    home_form = form_index(context.get("home_form", []))
    away_form = form_index(context.get("away_form", []))
    home_standing = standing_index(context.get("home_standing", {}))
    away_standing = standing_index(context.get("away_standing", {}))
    player_data = context.get("players", [])

    home_player_impact = player_impact_index(player_data, home_team)
    away_player_impact = player_impact_index(player_data, away_team)

    lambda_home, lambda_away = lambdas_from_context(context, weather_impact, news_score)
    matrix = score_matrix(lambda_home, lambda_away, max_goals=5)

    components = {
        "home_form_index": home_form,
        "away_form_index": away_form,
        "home_standing_index": home_standing,
        "away_standing_index": away_standing,
        "home_player_impact": home_player_impact,
        "away_player_impact": away_player_impact,
        "weather_impact": weather_impact,
        "news_sentiment": news_score,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "score_matrix": matrix,
    }

    if market_key in {"h2h", "moneyline_3way"}:
        probs = []
        for idx, outcome in enumerate(outcome_names):
            base = normalized_market_probs[idx]
            if outcome == home_team:
                shift = (home_form - away_form) * 0.08 + (home_standing - away_standing) * 0.06 + home_player_impact
                p = blend_market_and_strength(base, home_elo, away_elo, market_weight=0.58) + shift
            elif outcome == away_team:
                shift = (away_form - home_form) * 0.08 + (away_standing - home_standing) * 0.06 + away_player_impact
                p = blend_market_and_strength(base, away_elo, home_elo, market_weight=0.58) + shift
            else:
                draw_rate = sum(v for k, v in matrix.items() if k.split("-")[0] == k.split("-")[1])
                p = 0.6 * base + 0.4 * draw_rate + (-weather_impact * 0.2)
            probs.append(max(0.01, min(0.96, p)))
        total = sum(probs)
        return [p / total for p in probs], components

    if market_key in {"totals_2_5", "totals"}:
        under = 0.0
        for h in range(6):
            for a in range(6):
                if h + a <= 2:
                    under += matrix[f"{h}-{a}"]
        over = max(0.0, 1.0 - under)
        mapping = {}
        for name in outcome_names:
            low = name.lower()
            if "over" in low:
                mapping[name] = over
            elif "under" in low:
                mapping[name] = under
            else:
                mapping[name] = 0.5
        probs = [mapping[n] for n in outcome_names]
        total = sum(probs)
        return [p / total for p in probs], components

    if market_key in {"btts", "both_teams_to_score"}:
        p_home_0 = sum(matrix[f"0-{a}"] for a in range(6))
        p_away_0 = sum(matrix[f"{h}-0"] for h in range(6))
        p_both_0 = matrix.get("0-0", 0.0)
        yes = max(0.0, 1.0 - p_home_0 - p_away_0 + p_both_0)
        no = max(0.0, 1.0 - yes)

        mapping = {}
        for name in outcome_names:
            low = name.lower()
            mapping[name] = yes if low in {"yes", "y"} else no
        probs = [mapping[n] for n in outcome_names]
        total = sum(probs)
        return [p / total for p in probs], components

    if market_key == "result_btts":
        yes_map = {}
        no_map = {}
        for h in range(6):
            for a in range(6):
                p = matrix[f"{h}-{a}"]
                if h > a:
                    result = home_team
                elif a > h:
                    result = away_team
                else:
                    result = "Draw"
                both = h > 0 and a > 0
                if both:
                    yes_map[result] = yes_map.get(result, 0.0) + p
                else:
                    no_map[result] = no_map.get(result, 0.0) + p

        resolved = []
        for name in outcome_names:
            if "&" in name:
                left, right = [p.strip() for p in name.split("&", 1)]
                key_team = left
                value = yes_map.get(key_team, 0.0) if right.lower().startswith("yes") else no_map.get(key_team, 0.0)
            else:
                value = normalized_market_probs[outcome_names.index(name)]
            resolved.append(max(0.001, value))
        total = sum(resolved)
        return [p / total for p in resolved], components

    if market_key == "correct_score":
        resolved = []
        for name in outcome_names:
            key = name.replace(" ", "")
            resolved.append(max(0.0005, matrix.get(key, 0.0005)))
        total = sum(resolved)
        return [p / total for p in resolved], components

    if market_key in {"player_goal_or_assist", "player_anytime_scorer"}:
        resolved = []
        players = context.get("players", [])
        for name in outcome_names:
            row = next((p for p in players if p.get("name") == name), None)
            if not row:
                resolved.append(0.01)
                continue
            team = row.get("team")
            share = float(row.get("score_share", 0.08))
            if market_key == "player_goal_or_assist":
                share += float(row.get("assist_share", 0.04)) * 0.6
            team_lambda = lambda_home if team == home_team else lambda_away
            p_any = max(0.01, min(0.95, 1.0 - math.exp(-team_lambda * share)))
            status = str(row.get("status", "available")).lower()
            if status in {"injured", "suspended", "out"}:
                p_any *= 0.05
            elif status in {"doubtful"}:
                p_any *= 0.45
            resolved.append(max(0.001, p_any))
        total = sum(resolved)
        return [p / total for p in resolved], components

    # Default fallback uses blended market prior on winners and plain normalized otherwise.
    return normalized_market_probs, components
