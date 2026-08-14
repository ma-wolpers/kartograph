"""Zentrale Namensanzeige-Logik für Schüler (v4-Modell).

Ersetzt die vormals zweimal unabhängig implementierte Formatierung in
``_mixin_grid_helpers.py`` (Grid-Canvas) und ``_sitzplan_popup.py``
(Sitzplan-Vorschau) sowie den hardcodierten Namens-Join im PDF-Export.
Reine Domain-Logik ohne GUI-Abhängigkeit — nutzt ausschließlich
``Student.first_name`` (spitznamen-bewusst) und ``Student.last_name``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from app.core.domain.models_v4 import Student
from app.core.domain.student_id import StudentId

_FIRST_LED_FORMATS = frozenset({"Vorname", "Vorname N", "Vorname Nachname"})
_LAST_LED_START_LENGTH = {"Nachname": 0, "V. Nachname": 1}


def _format_fixed(first: str, last: str, fmt: str) -> str:
    """Formatiert Vor- und Nachname gemäß *fmt*, ohne Kollisions-Berücksichtigung.

    Args:
        first: Effektiver Vorname (Spitzname falls vorhanden, sonst offizieller Vorname).
        last: Nachname.
        fmt: Eines der fünf ``NAME_FORMAT_OPTIONS``.
    """
    if not first and not last:
        return ""
    if fmt == "Vorname N":
        return f"{first} {last[0]}".strip() if (first and last) else (first or last)
    if fmt == "Vorname Nachname":
        return f"{first} {last}".strip() if (first and last) else (first or last)
    if fmt == "V. Nachname":
        return f"{first[0]}. {last}".strip() if (first and last) else (first or last)
    if fmt == "Nachname":
        return last or first
    return first or last


def _resolve_first_led_group(students: Sequence[Student], first: str) -> dict[StudentId, str]:
    """Löst eine Gruppe von Schülern mit identischem effektivem Vornamen auf.

    Zeigt den nackten Vornamen, sofern die Gruppe nur ein Mitglied hat.
    Bei mehreren Mitgliedern wird ein Nachname-Präfix Buchstabe für Buchstabe
    ergänzt, bis alle Labels innerhalb der Gruppe eindeutig sind (oder das
    volle Nachname-Präfix erreicht ist — verbleibende Duplikate werden dann
    akzeptiert).
    """
    if len(students) == 1:
        return {students[0].student_id: first}

    max_last_len = max((len(s.last_name.strip()) for s in students), default=0)
    length = 1
    labels: dict[StudentId, str] = {}
    while True:
        labels = {}
        for s in students:
            suffix = s.last_name.strip()[:length]
            labels[s.student_id] = f"{first} {suffix}".strip() if suffix else first
        if len(set(labels.values())) == len(students) or length >= max_last_len:
            return labels
        length += 1


def _resolve_last_led_group(students: Sequence[Student], last: str, start_length: int) -> dict[StudentId, str]:
    """Löst eine Gruppe von Schülern mit identischem Nachnamen auf.

    *start_length* ist die Ausgangslänge des Vorname-Präfixes (0 für
    ``"Nachname"``, 1 für ``"V. Nachname"``, deren jeweils eigene normale
    Baseline-Darstellung). Wächst bei Kollision innerhalb der Gruppe,
    genau wie ``_resolve_first_led_group``, nur mit vertauschten Rollen.
    """
    max_first_len = max((len(s.first_name.strip()) for s in students), default=0)
    length = start_length
    labels: dict[StudentId, str] = {}
    while True:
        labels = {}
        for s in students:
            prefix = s.first_name.strip()[:length]
            labels[s.student_id] = f"{prefix}. {last}".strip() if prefix else last
        if len(set(labels.values())) == len(students) or length >= max_first_len:
            return labels
        length += 1


def compute_display_names(
    students: Sequence[Student],
    name_format: str,
    disambiguate: bool,
) -> dict[StudentId, str]:
    """Berechnet den Anzeigenamen für jeden Schüler in *students*.

    Ohne Kollisions-Modus (*disambiguate* = ``False``) wird *name_format* fix
    auf jeden Schüler unabhängig angewendet — unverändertes Verhalten.

    Mit Kollisions-Modus wird pro Format nur so viel vom jeweils anderen
    Namensteil gezeigt, wie zur Eindeutigkeit innerhalb von Namensvettern
    nötig ist: bei vorname-geführten Formaten (``Vorname``, ``Vorname N``,
    ``Vorname Nachname``) wird nach effektivem Vornamen gruppiert und bei
    Kollision ein Nachname-Präfix ergänzt; bei nachname-geführten Formaten
    (``Nachname``, ``V. Nachname``) wird nach Nachname gruppiert und bei
    Kollision ein Vorname-Präfix ergänzt. ``Vorname Nachname`` zeigt immer
    den vollen Namen (bereits maximal, nichts zu ergänzen).

    Args:
        students: Alle Schüler, deren Namen im selben Renderdurchlauf gezeigt
            werden (Kollisionserkennung braucht diesen Gruppenkontext).
        name_format: Eines der fünf ``NAME_FORMAT_OPTIONS``.
        disambiguate: Ob der Eindeutigkeits-Modus aktiv ist.

    Returns:
        Dict von ``StudentId`` auf fertig formatierten Anzeigenamen.
    """
    if not disambiguate or name_format == "Vorname Nachname":
        return {
            s.student_id: _format_fixed(s.first_name.strip(), s.last_name.strip(), name_format)
            for s in students
        }

    result: dict[StudentId, str] = {}

    if name_format in _FIRST_LED_FORMATS:
        groups: dict[str, list[Student]] = defaultdict(list)
        for s in students:
            groups[s.first_name.strip()].append(s)
        for first, group in groups.items():
            if not first:
                for s in group:
                    result[s.student_id] = _format_fixed(s.first_name.strip(), s.last_name.strip(), name_format)
                continue
            result.update(_resolve_first_led_group(group, first))
        return result

    start_length = _LAST_LED_START_LENGTH.get(name_format, 0)
    groups = defaultdict(list)
    for s in students:
        groups[s.last_name.strip()].append(s)
    for last, group in groups.items():
        if not last:
            for s in group:
                result[s.student_id] = _format_fixed(s.first_name.strip(), s.last_name.strip(), name_format)
            continue
        result.update(_resolve_last_led_group(group, last, start_length))
    return result
