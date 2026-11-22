"""Was „Spalte hinzufügen / umbenennen / löschen“ in der Datenansicht gerade bedeutet (reines Python, kein Tk).

Ein Knopf je Aktion statt je Bereich (Wunsch der Nutzerin 2026-11-22): die
ausgewählte Zelle entscheidet. Einzige Regel dafür ist ``column_target``:

- **Hinzufügen** braucht nur den Bereich der Zelle (Doku → Datum, Noten →
  Notenspalte, Notizen → Notiz- oder Ja/Nein-Spalte), geht also auch von
  Zusammenfassung, Gesamtnote oder allgemeinen Notizen aus.
- **Umbenennen** und **Löschen** brauchen eine eigene Spalte (``ColumnKind``):
  Datum, Notenspalte, Notizspalte oder Ja/Nein-Spalte.
- **Gruppen exportieren** geht in jeder Spalte des Notizenbereichs (auch
  allgemeine Notizen und Ja/Nein; Entscheidung der Nutzerin 2026-11-22).
- Eine Namenszelle gehört zu keinem Bereich: alle Spaltenknöpfe sind ausgegraut.

``action_label`` liefert den Hover-Text, der genau sagt, was passieren wird.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.adapters.gui.docs_table_model import DocColumnAxis
from app.core.domain.data_view_areas import DataArea

ColumnAction = Literal["add", "rename", "delete", "groups"]
ColumnKind = Literal["date", "grade", "note", "flag"]

_KIND_BY_AXIS_KIND: dict[str, ColumnKind] = {
    "date": "date",
    "grade": "grade",
    "text": "note",
    "number": "note",
    "date_value": "note",
    "flag": "flag",
}
_ADD_LABELS: dict[DataArea, str] = {
    DataArea.DOKU: "Datum hinzufügen",
    DataArea.NOTEN: "Notenspalte hinzufügen",
    DataArea.NOTIZEN: "Notiz- oder Ja/Nein-Spalte hinzufügen",
}
_KIND_LABELS: dict[tuple[ColumnAction, ColumnKind], str] = {
    ("rename", "date"): "Datum ändern",
    ("rename", "grade"): "Notenspalte umbenennen",
    ("rename", "note"): "Notizspalte umbenennen",
    ("rename", "flag"): "Ja/Nein-Spalte umbenennen (Bedeutung der Farbe)",
    ("delete", "date"): "Datum samt Einträgen löschen",
    ("delete", "grade"): "Notenspalte samt Noten löschen",
    ("delete", "note"): "Notizspalte samt Werten löschen",
    ("delete", "flag"): "Ja/Nein-Spalte samt Markierungen löschen",
}
_GENERIC: dict[ColumnAction, str] = {
    "add": "Spalte hinzufügen",
    "rename": "Spalte umbenennen",
    "delete": "Spalte löschen",
    "groups": "Gruppen exportieren",
}


@dataclass(frozen=True)
class ColumnTarget:
    """Spalte der ausgewählten Zelle, soweit sie für Spaltenaktionen zählt.

    Attributes:
        area: Bereich der Zelle (nie ``NAMEN``).
        kind: Eigene Spalte oder ``None`` (allgemeine Notizen, Zusammenfassung, Teil-/Gesamtnoten).
        key: Spaltenschlüssel der Tabelle.
    """

    area: DataArea
    kind: ColumnKind | None
    key: str


def column_target(axis: DocColumnAxis, key: str | None) -> ColumnTarget | None:
    """Ziel der Spaltenaktionen für die aktive Spalte *key*; ``None`` für Namen und Unbekanntes.

    Args:
        axis: Spaltenachse der Datenansicht.
        key: Aktiver Spaltenschlüssel.
    """
    if key is None or not axis.has(key):
        return None
    area = axis.area_of(key)
    if not area.toggleable:
        return None
    return ColumnTarget(area, _KIND_BY_AXIS_KIND.get(axis.kind_of(key) or ""), key)


def can_run(action: ColumnAction, target: ColumnTarget | None) -> bool:
    """Lässt sich *action* für *target* ausführen? (Grundlage fürs Ausgrauen.)

    Args:
        action: ``"add"``, ``"rename"``, ``"delete"`` oder ``"groups"``.
        target: Ergebnis von ``column_target``.
    """
    if target is None:
        return False
    if action == "groups":
        return target.area is DataArea.NOTIZEN
    return action == "add" or target.kind is not None


def action_label(action: ColumnAction, target: ColumnTarget | None) -> str:
    """Hover-Text: was der Knopf für *target* tut, oder warum er ausgegraut ist.

    Args:
        action: ``"add"``, ``"rename"``, ``"delete"`` oder ``"groups"``.
        target: Ergebnis von ``column_target``.

    Returns:
        z. B. ``"Notenspalte umbenennen"`` oder
        ``"Spalte löschen – wähle eine Zelle in Doku, Notizen oder Noten"``.
    """
    if action == "groups":
        if can_run(action, target):
            return "Gruppen dieser Spalte als PDF exportieren"
        return f"{_GENERIC[action]} – wähle eine Zelle im Notizenbereich"
    if target is None:
        return f"{_GENERIC[action]} – wähle eine Zelle in Doku, Notizen oder Noten"
    if action == "add":
        return _ADD_LABELS[target.area]
    if target.kind is None:
        return f"{_GENERIC[action]} – diese Spalte lässt sich nicht {'umbenennen' if action == 'rename' else 'löschen'}"
    return _KIND_LABELS[(action, target.kind)]
