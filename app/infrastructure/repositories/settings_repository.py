from __future__ import annotations

import json
from pathlib import Path

from bw_libs.app_paths import atomic_write_json


class JsonSettingsRepository:
    def __init__(self, config_path: Path):
        self._config_path = config_path

    def load_settings(self) -> dict:
        if not self._config_path.exists():
            return {}
        try:
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
            return {}
        except Exception:
            return {}

    def save_settings(self, payload: dict) -> None:
        atomic_write_json(self._config_path, payload)
