from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bw_libs.app_shell import AppShellConfig

from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository
from app.infrastructure.repositories.settings_repository import JsonSettingsRepository


@dataclass(frozen=True)
class AppDependencies:
    """Composition-root payload for Kartograph GUI startup."""

    shell_config: AppShellConfig
    settings_repository: JsonSettingsRepository
    plan_repository: JsonSeatingPlanRepository
    default_plans_dir: Path
    symbols_path: Path


def build_gui_dependencies(workspace_root: Path) -> AppDependencies:
    """Build all GUI dependencies for Kartograph from workspace root."""

    config_path = workspace_root / "config" / "kartograph_settings.json"
    symbols_path = workspace_root / "config" / "symbols.json"
    default_plans_dir = workspace_root / "plans"

    return AppDependencies(
        shell_config=AppShellConfig(
            title="Kartograph",
            geometry="1320x860",
            min_width=1000,
            min_height=680,
        ),
        settings_repository=JsonSettingsRepository(config_path=config_path),
        plan_repository=JsonSeatingPlanRepository(),
        default_plans_dir=default_plans_dir,
        symbols_path=symbols_path,
    )
