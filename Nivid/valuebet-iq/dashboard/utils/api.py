from __future__ import annotations

import os
from typing import Any

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")


def _url(path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    return f"{API_BASE_URL}{path}"


def get(path: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(_url(path), params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def post(path: str, data: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
    response = requests.post(_url(path), json=data, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def put(path: str, data: dict[str, Any]) -> Any:
    response = requests.put(_url(path), json=data, timeout=20)
    response.raise_for_status()
    return response.json()
