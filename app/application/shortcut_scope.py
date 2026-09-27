"""Fachlicher Shortcut-Scope: welcher Tastaturkürzel-Bereich gerade aktiv ist.

Einzige Quelle dafür, ob Kartograph sich im Editor-Shortcut-Scope (bw-gui
``UI_MODE_PREVIEW``) oder im globalen/Planlisten-Scope befindet. Wird vom
``WindowShortcutBinder``-``mode_provider`` und von ``_shortcut_scope_allows()``
gelesen -- bewusst aus ``AppState`` abgeleitet und nicht aus der Tk-Sichtbarkeit
(``winfo_ismapped()``) eines Widgets, damit Shortcut-Gating und Fachzustand
nicht auseinanderlaufen können.

Jeder ``InteractionMode`` ist genau einer der beiden expliziten Mengen
zugeordnet; ein neuer Modus muss bewusst eingeordnet werden
(``tests/test_shortcut_scope.py`` schlägt sonst fehl) statt implizit als
"alles außer LIST ist Editor" mitzulaufen.
"""

from __future__ import annotations

from typing import Final

from app.application.app_state import AppState, InteractionMode

PREVIEW_SHORTCUT_MODES: Final = frozenset({InteractionMode.GRID, InteractionMode.NAME_EDIT})
"""Interaktionsmodi, in denen die Editor-Kürzel (Raster/Doku) gelten."""

NON_PREVIEW_SHORTCUT_MODES: Final = frozenset({InteractionMode.LIST})
"""Interaktionsmodi, in denen nur globale/Planlisten-Kürzel gelten."""


def is_preview_shortcut_scope(state: AppState) -> bool:
    """True, wenn ein Plan offen ist und der Interaktionsmodus zum Editor-Scope gehört.

    Invariante (durch Handler garantiert, getestet): ``current_plan is None``
    genau dann, wenn ``interaction_mode == LIST``; ``apply_state()`` zeigt die
    Editor-Ansicht genau dann, wenn ein Plan offen ist. Die Plan-Prüfung ist
    trotzdem explizit, damit ein inkonsistenter Zwischenzustand nie
    Editor-Kürzel ohne Plan freischaltet.

    Args:
        state: Aktueller AppState.
    """
    return state.current_plan is not None and state.interaction_mode in PREVIEW_SHORTCUT_MODES
