from __future__ import annotations

from pathlib import Path

from app.adapters.gui.main_window import KartographMainWindow
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository
from app.infrastructure.repositories.settings_repository import JsonSettingsRepository


def main() -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    config_path = workspace_root / "config" / "kartograph_settings.json"
    default_plans_dir = workspace_root / "plans"
    symbols_path = workspace_root / "app" / "resources" / "symbols.json"

    settings_repository = JsonSettingsRepository(config_path=config_path)
    plan_repository = JsonSeatingPlanRepository()

    app = KartographMainWindow(
        settings_repository=settings_repository,
        plan_repository=plan_repository,
        default_plans_dir=default_plans_dir,
        symbols_path=symbols_path,
    )
    app.mainloop()
