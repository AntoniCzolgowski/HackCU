from __future__ import annotations

from math import pow


def elo_win_probability(team_rating: float, opponent_rating: float) -> float:
    exponent = (opponent_rating - team_rating) / 400.0
    return 1.0 / (1.0 + pow(10.0, exponent))


def blend_market_and_strength(
    normalized_market_prob: float,
    team_rating: float,
    opponent_rating: float,
    market_weight: float = 0.7,
) -> float:
    strength_prob = elo_win_probability(team_rating, opponent_rating)
    blended = market_weight * normalized_market_prob + (1 - market_weight) * strength_prob
    return min(0.99, max(0.01, blended))
