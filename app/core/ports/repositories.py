from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.domain.models import SeatingPlan


class SeatingPlanRepository(Protocol):
    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        ...

    def load_plan(self, plan_path: Path) -> SeatingPlan:
        ...

    def save_plan(self, plan: SeatingPlan, plan_path: Path) -> None:
        ...

    def create_new_plan(self, plans_dir: Path, plan_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        ...


class SettingsRepository(Protocol):
    def load_settings(self) -> dict:
        ...

    def save_settings(self, payload: dict) -> None:
        ...
