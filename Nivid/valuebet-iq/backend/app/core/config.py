from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ValueBet IQ API"
    app_env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg2://valuebet:valuebet@db:5432/valuebet_iq"

    odds_provider_mode: str = "mock"  # mock | odds_api
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_poll_interval_seconds: int = 60
    odds_provider_region: str = "us"
    odds_provider_market_types: str = "h2h,totals,btts"
    odds_api_sports: str = "soccer_fifa_world_cup"
    world_cup_only: bool = True
    world_cup_league_name: str = "FIFA World Cup"
    news_enabled: bool = True
    weather_enabled: bool = True
    news_lookback_days: int = 7

    data_freshness_seconds: int = 180
    max_odds_drift_pct: float = 0.03

    min_edge: float = 0.015
    top_pick_edge: float = 0.04
    min_ev: float = 0.02
    top_pick_ev: float = 0.06

    bankroll_start: float = 1000.0
    default_flat_stake: float = 25.0
    max_stake: float = 100.0
    max_exposure_per_event: float = 200.0
    max_daily_loss: float = 250.0

    sim_slippage_bps: float = 30.0
    sim_delay_ms: int = 250

    enable_live_execution: bool = False
    live_betfair_enabled: bool = False
    live_matchbook_enabled: bool = False

    metrics_enabled: bool = True

    mock_seed_path: str = "data/mock/mock_odds.json"

    @property
    def market_types(self) -> list[str]:
        return [item.strip() for item in self.odds_provider_market_types.split(",") if item.strip()]


@lru_cache

def get_settings() -> Settings:
    return Settings()
