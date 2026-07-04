"""Shared helpers for the eval harness (dataset loading, result persistence)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_dataset(limit: int | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Return (tenant, items). `limit` truncates for quick smoke runs."""
    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    items = data["items"][:limit] if limit else data["items"]
    return data["tenant"], items


def save_result(name: str, payload: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"{stamp}_{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
