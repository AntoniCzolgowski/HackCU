from app.services.calculations import (
    edge,
    expected_value,
    fractional_kelly_fraction,
    implied_probability,
    normalize_probabilities,
)


def test_implied_probability():
    assert round(implied_probability(2.0), 4) == 0.5


def test_probability_normalization():
    normalized = normalize_probabilities([0.55, 0.52])
    assert round(sum(normalized), 6) == 1.0
    assert normalized[0] > normalized[1]


def test_expected_value_and_edge():
    model_prob = 0.58
    odds = 2.0
    implied = 0.5
    assert round(expected_value(model_prob, odds), 4) == 0.16
    assert round(edge(model_prob, implied), 4) == 0.08


def test_fractional_kelly_is_capped_to_non_negative():
    assert fractional_kelly_fraction(0.40, 2.0, factor=0.25) == 0.0
    assert fractional_kelly_fraction(0.60, 2.2, factor=0.25) > 0.0
