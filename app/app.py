from __future__ import annotations

import traceback
from pathlib import Path
from tkinter import Tk, messagebox

from app.adapters.gui.main_window import KartographMainWindow
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository
from app.infrastructure.repositories.settings_repository import JsonSettingsRepository


def _show_startup_error(exc: Exception) -> None:
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        root = Tk()
        root.withdraw()
        messagebox.showerror(
            "Kartograph-Start fehlgeschlagen",
            f"Kartograph konnte nicht gestartet werden.\n\n{exc}\n\nDetails:\n{detail[-2000:]}",
            parent=root,
        )
        root.destroy()
    except Exception:
        # If Tk itself is not available, fall back to stderr output.
        print("Kartograph startup failed:")
        print(detail)


def main() -> None:
    try:
        workspace_root = Path(__file__).resolve().parents[1]
        config_path = workspace_root / "config" / "kartograph_settings.json"
        symbols_path = workspace_root / "config" / "symbols.json"
        default_plans_dir = workspace_root / "plans"

        settings_repository = JsonSettingsRepository(config_path=config_path)
        plan_repository = JsonSeatingPlanRepository()

        app = KartographMainWindow(
            settings_repository=settings_repository,
            plan_repository=plan_repository,
            default_plans_dir=default_plans_dir,
            symbols_path=symbols_path,
        )
        app.mainloop()
    except Exception as exc:
        _show_startup_error(exc)
