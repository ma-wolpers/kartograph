from __future__ import annotations

import json
from pathlib import Path


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
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._config_path.with_suffix(self._config_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._config_path)
