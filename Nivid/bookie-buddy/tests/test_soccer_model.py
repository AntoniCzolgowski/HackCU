from app.services.soccer_model import model_probs_for_market


def _base_context():
    return {
        "home_form": ["W", "W", "D", "W", "L"],
        "away_form": ["W", "D", "L", "W", "D"],
        "home_standing": {"group_rank": 1, "points": 6, "goal_diff": 3},
        "away_standing": {"group_rank": 2, "points": 4, "goal_diff": 1},
        "home_team_xg": 1.8,
        "away_team_xg": 1.2,
        "home_team_xga": 0.9,
        "away_team_xga": 1.1,
        "players": [
            {"name": "A Striker", "team": "Home", "status": "available", "impact": 0.7, "score_share": 0.22, "assist_share": 0.08},
            {"name": "B Striker", "team": "Away", "status": "available", "impact": 0.6, "score_share": 0.19, "assist_share": 0.05},
        ],
    }


def test_moneyline_probs_sum_to_one():
    probs, comps = model_probs_for_market(
        market_key="moneyline_3way",
        outcome_names=["Home", "Draw", "Away"],
        normalized_market_probs=[0.5, 0.25, 0.25],
        home_team="Home",
        away_team="Away",
        home_elo=1550,
        away_elo=1500,
        context=_base_context(),
        weather_impact=0.0,
        news_score=0.0,
    )
    assert round(sum(probs), 6) == 1.0
    assert 0.0 < comps["lambda_home"]


def test_btts_market_outputs_yes_no_pair():
    probs, _ = model_probs_for_market(
        market_key="btts",
        outcome_names=["Yes", "No"],
        normalized_market_probs=[0.5, 0.5],
        home_team="Home",
        away_team="Away",
        home_elo=1500,
        away_elo=1500,
        context=_base_context(),
        weather_impact=-0.05,
        news_score=0.1,
    )
    assert round(sum(probs), 6) == 1.0
    assert all(0 < p < 1 for p in probs)


def test_correct_score_distribution_normalized():
    probs, _ = model_probs_for_market(
        market_key="correct_score",
        outcome_names=["1-0", "1-1", "0-1", "2-1"],
        normalized_market_probs=[0.25, 0.25, 0.25, 0.25],
        home_team="Home",
        away_team="Away",
        home_elo=1540,
        away_elo=1530,
        context=_base_context(),
        weather_impact=0.0,
        news_score=0.0,
    )
    assert round(sum(probs), 6) == 1.0
