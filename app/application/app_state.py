"""AppState — zentraler, unveränderlicher GUI-Zustand von Kartograph.

Die GUI liest ausschließlich aus ``AppState``; sie schreibt nie direkt in
den Zustand. Jede Benutzeraktion erzeugt via ``KartographAppController``
einen neuen ``AppState``, der dann per ``apply_state(state)``-Callback
an alle Mixins weitergereicht wird.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.plan_selection import RectSelection
from app.core.domain.settings import KartographSettings
from app.core.domain.student_id import StudentId
from app.infrastructure.symbol_config_loader import SymbolDefinition


class InteractionMode(Enum):
    """Grobe GUI-Betriebsart: welcher Bereich aktuell die Tastatureingabe besitzt."""

    LIST = auto()       # Plan-Listenansicht aktiv
    GRID = auto()       # Rasteransicht, Zelle ausgewählt
    NAME_EDIT = auto()  # In-Place-Namenseingabe aktiv


class EditorSurface(Enum):
    """Welche der beiden Editor-Oberflächen (Raster oder Dokumentation) sichtbar ist."""

    GRID = "grid"
    DOCUMENTATION = "documentation"


@dataclass(frozen=True)
class DocSortState:
    """Aktuelle Sortierung der Dokumentations-Tabelle (Spalte + Richtung)."""

    column_id: str | None = None
    ascending: bool = True


@dataclass(frozen=True)
class PlanListEntry:
    """Ein Eintrag der Planliste, wie er in der Listbox angezeigt wird."""

    path: Path
    name: str
    student_count: int
    is_archived: bool = False


@dataclass(frozen=True)
class AppState:
    """Unveränderlicher Gesamtzustand der Anwendung; einzige Quelle der Wahrheit für die GUI."""

    # --- Plan -----------------------------------------------------------------
    current_plan: SeatingPlan | None = None
    current_plan_path: Path | None = None
    plan_list: list[PlanListEntry] = field(default_factory=list)

    # --- Selektion & Modus ---------------------------------------------------
    selection: RectSelection = field(default_factory=RectSelection)
    interaction_mode: InteractionMode = InteractionMode.LIST
    editor_surface: EditorSurface = EditorSurface.GRID

    # --- Viewport --------------------------------------------------------------
    # Default/Grenzen als Literale dupliziert statt aus main_window_constants.py
    # importiert (Core/Application darf nicht von der GUI abhaengen, s. settings.py).
    cell_size: int = 92

    # --- Docs-Ansicht --------------------------------------------------------
    doc_selected_student_id: StudentId | None = None
    doc_selected_date: str | None = None
    doc_selected_column_id: str | None = None
    doc_sort: DocSortState = field(default_factory=DocSortState)

    # --- Status --------------------------------------------------------------
    status_message: str = ""
    can_undo: bool = False
    can_redo: bool = False

    # --- Konfiguration (Phase D) ----------------------------------------------
    settings: KartographSettings = field(default_factory=KartographSettings)
    symbol_catalog: tuple[SymbolDefinition, ...] = field(default_factory=tuple)
