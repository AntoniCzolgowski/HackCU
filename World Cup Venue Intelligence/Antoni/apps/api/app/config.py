from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
CITY_DATA_DIR = DATA_DIR / "cities"
SEED_DIR = DATA_DIR / "seed"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
DOCS_DIR = ROOT_DIR / "docs"
REPORTS_DIR = PROCESSED_DIR / "reports"

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    api_host: str = os.getenv("MATCHFLOW_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("MATCHFLOW_API_PORT", "8000"))
    web_port: int = int(os.getenv("MATCHFLOW_WEB_PORT", "5173"))
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


settings = Settings()
