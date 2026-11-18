"""Gemeinsame Bausteine der Symbol-Formulare (programmweiter Dialog und Plan-Anpassung).

Einzige Stelle, die die Kompetenzauswahl baut: bw-gui ``CheckList``, nach
``Competence.group`` gruppiert (Reihenfolge des ersten Auftretens), in einem
höhenbegrenzten ``ScrollableFrame``. Beide Formulare nutzen dieselbe Funktion,
damit Auswahl und Darstellung überall gleich sind.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.core.domain.symbol_catalog import Competence
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import CheckList, ScrollableFrame

COMPETENCE_PICKER_MAX_HEIGHT = 240
"""Höchste Höhe der Kompetenzauswahl in px; darüber scrollt sie."""

FORM_HINT_WRAP = 420
"""Umbruchbreite für Hinweise und Fehlermeldungen in den Formularen (px)."""


def competence_groups(competences: Iterable[Competence]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Gruppiert Kompetenzen für die ``CheckList`` (Gruppen in Reihenfolge des ersten Auftretens).

    Args:
        competences: Alle Kompetenzen in Katalogreihenfolge.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for competence in competences:
        groups.setdefault(competence.group, []).append((competence.id, competence.name))
    return list(groups.items())


def build_competence_picker(parent, competences: Iterable[Competence], selected: Iterable[str]) -> CheckList:
    """Baut die scrollende Kompetenzauswahl in *parent* und gibt die ``CheckList`` zurück.

    Args:
        parent: Eltern-Widget (wird mit ``pack`` befüllt).
        competences: Alle Kompetenzen.
        selected: Vorausgewählte IDs.
    """
    tui.Label(parent, text="Kompetenzen (in der Legende in dieser Reihenfolge)").pack(anchor="w", pady=(8, 4))
    scroll = ScrollableFrame(parent)
    scroll.pack(fill="both", expand=True)
    picker = CheckList(scroll.content, groups=competence_groups(competences), selected=selected)
    picker.pack(fill="x", anchor="w")
    scroll.set_height_cap(COMPETENCE_PICKER_MAX_HEIGHT)
    return picker
