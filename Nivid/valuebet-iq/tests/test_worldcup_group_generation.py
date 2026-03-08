from pathlib import Path

from app.core.config import Settings
from app.services.providers import MockOddsProvider


def test_group_based_match_generation_count():
    seed_path = Path(__file__).resolve().parents[1] / "backend" / "data" / "mock" / "mock_odds.json"
    settings = Settings(
        mock_seed_path=str(seed_path),
        world_cup_only=True,
        world_cup_league_name="FIFA World Cup",
    )
    provider = MockOddsProvider(settings)
    events = provider.fetch_events()

    assert len(events) == 72
    assert all(e.league == "FIFA World Cup 2026" for e in events)
    assert all((e.competition_stage or "").startswith("Group ") for e in events)
