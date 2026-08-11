from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.app_info import APP_INFO, AppInfo
from bw_libs.app_shell import AppShellConfig

from app.application.app_controller import KartographAppController
from app.infrastructure.repositories.settings_repository import JsonSettingsRepository
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4


@dataclass(frozen=True)
class AppDependencies:
    """Composition-root payload for Kartograph GUI startup."""

    app_info: AppInfo
    shell_config: AppShellConfig
    settings_repository: JsonSettingsRepository
    controller: KartographAppController
    symbols_path: Path


def build_gui_dependencies(workspace_root: Path) -> AppDependencies:
    """Build all GUI dependencies for Kartograph from workspace root.

    Args:
        workspace_root: Root directory containing the ``config`` and
            ``plans`` subdirectories.
    """

    config_path = workspace_root / "config" / "kartograph_settings.json"
    symbols_path = workspace_root / "config" / "symbols.json"
    default_plans_dir = workspace_root / "plans"

    settings_repository = JsonSettingsRepository(config_path=config_path)
    plan_repository = JsonSeatingPlanRepositoryV4()

    controller = KartographAppController(
        plan_repository=plan_repository,
        settings_repository=settings_repository,
        default_plans_dir=default_plans_dir,
        symbols_path=symbols_path,
        on_state_changed=lambda _state: None,  # replaced by main_window after init
    )

    return AppDependencies(
        app_info=APP_INFO,
        shell_config=AppShellConfig(
            title=APP_INFO.window_title,
            geometry="1320x860",
            min_width=1000,
            min_height=680,
        ),
        settings_repository=settings_repository,
        controller=controller,
        symbols_path=symbols_path,
    )
