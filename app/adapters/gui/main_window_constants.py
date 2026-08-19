"""Modulkonstanten und -funktionen des Kartograph-Hauptfensters.

Enthält alle unveränderlichen Konfigurationswerte, Paletten, Intent-Mengen
sowie die Hilfsfunktionen zur Prozessidentität und zum Fenster-Icon, die
vor der Klassendefinition benötigt werden.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

from app.adapters.gui.ui_intents import UiIntent

MIN_WINDOW_WIDTH = 600
MIN_WINDOW_HEIGHT = 400
MAX_CANVAS_RADIUS = 50
MIN_CANVAS_RADIUS = 1
DEFAULT_CANVAS_RADIUS = 50
DEFAULT_CELL_SIZE = 92
DEFAULT_SYMBOL_STRENGTH = 1
DEFAULT_VIEWPORT_FOLLOW_BUFFER = 0
DEFAULT_PERIODIC_BACKUP_INTERVAL_MS = 5 * 60 * 1000
DEFAULT_UI_WATCHDOG_INTERVAL_MS = 1000
UI_WATCHDOG_WARN_DRIFT_SECONDS = 2.5
DOCS_HORIZONTAL_WHEEL_UNITS = 8
DOCS_HORIZONTAL_SCROLLBAR_UNITS = 4
DEFAULT_DETAILS_OVERLAY_POSITION = "bottom"
DEFAULT_TABLEGROUP_OVERLAY_POSITION = "right"
NAME_FORMAT_OPTIONS = ("Vorname", "Vorname N", "Vorname Nachname", "V. Nachname", "Nachname")
DEFAULT_NAME_FORMAT = "Vorname Nachname"
DEFAULT_SITZPLAN_POPUP_DELAY = 3
MIN_SITZPLAN_POPUP_DELAY = 1
MAX_SITZPLAN_POPUP_DELAY = 30
DEFAULT_NAME_SAVE_DELAY = 2
MIN_NAME_SAVE_DELAY = 0
MAX_NAME_SAVE_DELAY = 15
LIST_ACTIVE = "list_active"
GRID_SELECTED = "grid_selected"
NAME_EDITING = "name_editing"
ATTENDANCE_SYMBOL_NAME = "Abwesend"

DeskDetailMode = Literal["desk_detail_revealed", "desk_detail_editing"]
DESK_DETAIL_REVEALED: DeskDetailMode = "desk_detail_revealed"
DESK_DETAIL_EDITING: DeskDetailMode = "desk_detail_editing"

COLOR_MARKER_PALETTE: list[tuple[str, str, str, str]] = [
    ("1", "gelb", "Gelb", "#f4d35e"),
    ("2", "orange", "Orange", "#ee964b"),
    ("3", "rot", "Rot", "#f95738"),
    ("4", "magenta", "Magenta", "#d81159"),
    ("5", "lila", "Lila", "#7b2cbf"),
    ("6", "marine", "Marine", "#1d3557"),
    ("7", "cyan", "Cyan", "#4cc9f0"),
    ("8", "tuerkis", "Tuerkis", "#2a9d8f"),
    ("9", "gruen", "Gruen", "#6a994e"),
]

APP_USER_MODEL_ID = "7thCloud.Kartograph"
ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "kartograph.ico"
LOGGER = logging.getLogger("kartograph.ui")

GRID_ONLY_INTENTS = {
    UiIntent.DELETE_DESK,
    UiIntent.SET_TEACHER_DESK,
    UiIntent.ADD_SYMBOL,
    UiIntent.OPEN_TABLEGROUP_SETTINGS,
    UiIntent.GRID_SYMBOL_FILTER,
    UiIntent.MOVE_UP,
    UiIntent.MOVE_DOWN,
    UiIntent.MOVE_LEFT,
    UiIntent.MOVE_RIGHT,
    UiIntent.EXPAND_UP,
    UiIntent.EXPAND_DOWN,
    UiIntent.EXPAND_LEFT,
    UiIntent.EXPAND_RIGHT,
    UiIntent.ZOOM_IN,
    UiIntent.ZOOM_OUT,
    UiIntent.RESET_VIEW,
    UiIntent.COPY,
    UiIntent.CUT,
    UiIntent.PASTE,
}

DOCS_ONLY_INTENTS = {
    UiIntent.RENAME_DOCUMENTATION_DATE,
    UiIntent.DELETE_DOCUMENTATION_DATE,
    UiIntent.ADD_GRADE_COLUMN,
    UiIntent.DELETE_GRADE_COLUMN,
}


def _known_ui_intents() -> tuple[str, ...]:
    """Gibt alle deklarierten UiIntent-Stringwerte zurück."""
    values: list[str] = []
    for key, value in UiIntent.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, str):
            values.append(value)
    return tuple(sorted(set(values)))


def configure_windows_process_identity() -> None:
    """Setzt die Windows AppUserModelID für korrekte Taskleisten-Zuordnung."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        return


def apply_window_icon(window) -> None:
    """Setzt das Fenster-Icon, sofern die Plattform und Datei vorhanden sind.

    Args:
        window: Das Tk-Root-Fenster.
    """
    if not sys.platform.startswith("win") or not ICON_PATH.exists():
        return
    try:
        window.iconbitmap(default=str(ICON_PATH))
    except Exception:
        return
