"""Echtes Kartograph-Hauptfenster in einem isolierten Workspace (Tests und Benchmarks).

Einzige Stelle, die ein vollständiges Hauptfenster ohne Zugriff auf echte
Nutzerdaten aufbaut: eigener ``APPDATA``-Ordner, nur die Standardsymbole,
leerer Plan-Ordner, ein vom Aufrufer übergebener (synthetischer) Plan. Tk-
Integrationstests und ``perf_bench_gui_nav`` nutzen dieselbe Funktion, damit
gemessen wird, was auch getestet wird.
"""

from __future__ import annotations

import json
import os
import shutil
import tkinter
from pathlib import Path
from typing import Callable

from app.adapters.bootstrap.wiring import build_gui_dependencies
from app.adapters.gui.main_window import KartographMainWindow
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from app.infrastructure.symbol_config_loader import DEFAULT_SYMBOLS_PATH

_TCL_INIT_RACE_MARKERS = ("usable", "tcl_findLibrary", "init.tcl", "auto.tcl")


def open_isolated_window(workspace: Path, plan) -> tuple[KartographMainWindow, Callable[[], None]]:
    """Baut ein echtes Hauptfenster in *workspace* und öffnet *plan*.

    Args:
        workspace: Leeres, existierendes Verzeichnis.
        plan: Synthetischer Plan (erfundene Namen).

    Returns:
        ``(Hauptfenster, close)``; ``close()`` zerstört die Tk-Wurzel und stellt
        die vorige ``APPDATA``-Umgebungsvariable wieder her.
    """
    previous_appdata = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(workspace / "appdata")
    (workspace / "config").mkdir()
    shutil.copy(DEFAULT_SYMBOLS_PATH, workspace / "config" / "symbols.json")
    plans_dir = workspace / "plans"
    plans_dir.mkdir()
    (workspace / "config" / "kartograph_settings.json").write_text(
        json.dumps({"plans_dir": str(plans_dir)}), encoding="utf-8"
    )
    plan_path = plans_dir / "synthetisch.json"
    JsonSeatingPlanRepositoryV4().save_plan(plan, plan_path)

    app = _create_window_with_retry(workspace)
    app.tk_root.update()
    app.open_plan(plan_path)
    app.tk_root.update()

    def close() -> None:
        app.tk_root.destroy()
        if previous_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = previous_appdata

    return app, close


def _create_window_with_retry(workspace: Path, attempts: int = 3) -> KartographMainWindow:
    """Baut das Hauptfenster; wiederholt nur bei der bekannten Tcl-Init-Race unter Windows.

    Mehrere nacheinander erzeugte Tk-Interpreter in einem Prozess scheitern auf
    diesem Windows-Setup sporadisch beim Lesen der Tcl-Bibliotheksdateien
    (s. bw-gui ``tests/conftest.py``) -- kein Fehler im getesteten Code. Andere
    ``TclError`` werden sofort weitergereicht.

    Args:
        workspace: Workspace mit ``config/``.
        attempts: Höchstzahl der Versuche.
    """
    for attempt in range(attempts):
        try:
            deps = build_gui_dependencies(workspace)
            return KartographMainWindow(controller=deps.controller, shell_config=deps.shell_config)
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in _TCL_INIT_RACE_MARKERS) or attempt == attempts - 1:
                raise
    raise AssertionError("unreachable")
