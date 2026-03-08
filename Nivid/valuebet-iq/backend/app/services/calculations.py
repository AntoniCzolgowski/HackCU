from __future__ import annotations

from typing import Iterable


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must be greater than 1.0")
    return 1.0 / decimal_odds


def normalize_probabilities(implied_probs: Iterable[float]) -> list[float]:
    probs = list(implied_probs)
    total = sum(probs)
    if total <= 0:
        raise ValueError("Sum of implied probabilities must be positive")
    return [p / total for p in probs]


def expected_value(model_prob: float, decimal_odds: float) -> float:
    return model_prob * decimal_odds - 1.0


def edge(model_prob: float, implied_prob: float) -> float:
    return model_prob - implied_prob


def fractional_kelly_fraction(model_prob: float, decimal_odds: float, factor: float = 0.25) -> float:
    b = decimal_odds - 1.0
    q = 1.0 - model_prob
    if b <= 0:
        return 0.0
    kelly = (b * model_prob - q) / b
    return max(0.0, kelly * factor)
