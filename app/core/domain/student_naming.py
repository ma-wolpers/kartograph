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

NameParts = tuple[str, str]
"""Anzeigename in zwei Teilen: ``(vorderer Teil, hinterer Teil)``.

Der vordere Teil ist der (Spitz-)Vorname bzw. dessen Kürzel ("V."), der
hintere der Nachname bzw. dessen Kürzel. Ein Teil kann leer sein (z. B.
Format "Vorname" ohne Namensvetter). Zusammengesetzt mit ``join_name_parts``
ergibt sich exakt der einzeilige Anzeigename; getrennt erlaubt er einen
Zeilenumbruch genau zwischen den Namensteilen, auch wenn ein Teil selbst
Leerzeichen enthält ("Anna Lena", "von Berg").
"""


def join_name_parts(parts: NameParts) -> str:
    """Setzt die Namensteile zum einzeiligen Anzeigenamen zusammen.

    Args:
        parts: ``(vorderer Teil, hinterer Teil)``.

    Returns:
        Die nicht leeren Teile, durch ein Leerzeichen getrennt.
    """
    return " ".join(part for part in parts if part)


def fit_name_to_width(parts: NameParts, max_width: float, measure) -> str:
    """Gibt den Anzeigenamen ein- oder zweizeilig zurück, je nachdem, was in *max_width* passt.

    Zweizeilig (hinterer Teil in der zweiten Zeile) wird nur, wenn die
    einzeilige Fassung zu breit ist und beide Teile vorhanden sind. Passt
    auch die zweizeilige Fassung nicht, bleibt sie trotzdem die schmalere.

    Args:
        parts: Namensteile aus ``compute_display_name_parts``.
        max_width: Verfügbare Breite in derselben Einheit wie *measure*.
        measure: Funktion ``str -> Breite`` (z. B. ``Font.measure`` der GUI).

    Returns:
        Den einzeiligen Namen oder ``"vorne\nhinten"``.
    """
    single_line = join_name_parts(parts)
    front, back = parts
    if not (front and back) or measure(single_line) <= max_width:
        return single_line
    return f"{front}\n{back}"


def _format_fixed(first: str, last: str, fmt: str) -> NameParts:
    """Formatiert Vor- und Nachname gemäß *fmt*, ohne Kollisions-Berücksichtigung.

    Args:
        first: Effektiver Vorname (Spitzname falls vorhanden, sonst offizieller Vorname).
        last: Nachname.
        fmt: Eines der fünf ``NAME_FORMAT_OPTIONS``.

    Returns:
        Namensteile; fehlt einer der beiden Namen, steht der andere vorne.
    """
    if not first and not last:
        return ("", "")
    if not (first and last):
        return (first or last, "")
    if fmt == "Vorname N":
        return (first, last[0])
    if fmt == "Vorname Nachname":
        return (first, last)
    if fmt == "V. Nachname":
        return (f"{first[0]}.", last)
    if fmt == "Nachname":
        return (last, "")
    return (first, "")


def _all_distinct(labels: dict[StudentId, NameParts]) -> bool:
    """Prüft, ob die zusammengesetzten Anzeigenamen paarweise verschieden sind.

    Verglichen wird bewusst der einzeilige Name (nicht die Teile), denn
    eindeutig sein muss, was man liest.

    Args:
        labels: Namensteile je Schüler einer Gruppe.
    """
    return len({join_name_parts(parts) for parts in labels.values()}) == len(labels)


def _resolve_first_led_group(students: Sequence[Student], first: str) -> dict[StudentId, NameParts]:
    """Löst eine Gruppe von Schülern mit identischem effektivem Vornamen auf.

    Zeigt den nackten Vornamen, sofern die Gruppe nur ein Mitglied hat.
    Bei mehreren Mitgliedern wird ein Nachname-Präfix Buchstabe für Buchstabe
    ergänzt, bis alle Labels innerhalb der Gruppe eindeutig sind (oder das
    volle Nachname-Präfix erreicht ist — verbleibende Duplikate werden dann
    akzeptiert).

    Args:
        students: Schüler mit demselben effektiven Vornamen.
        first: Dieser gemeinsame Vorname.

    Returns:
        Namensteile ``(Vorname, Nachname-Präfix)`` je Schüler.
    """
    if len(students) == 1:
        return {students[0].student_id: (first, "")}

    max_last_len = max((len(s.last_name.strip()) for s in students), default=0)
    length = 1
    labels: dict[StudentId, NameParts] = {}
    while True:
        labels = {s.student_id: (first, s.last_name.strip()[:length]) for s in students}
        if _all_distinct(labels) or length >= max_last_len:
            return labels
        length += 1


def _resolve_last_led_group(students: Sequence[Student], last: str, start_length: int) -> dict[StudentId, NameParts]:
    """Löst eine Gruppe von Schülern mit identischem Nachnamen auf.

    *start_length* ist die Ausgangslänge des Vorname-Präfixes (0 für
    ``"Nachname"``, 1 für ``"V. Nachname"``, deren jeweils eigene normale
    Baseline-Darstellung). Wächst bei Kollision innerhalb der Gruppe,
    genau wie ``_resolve_first_led_group``, nur mit vertauschten Rollen.

    Args:
        students: Schüler mit demselben Nachnamen.
        last: Dieser gemeinsame Nachname.
        start_length: Ausgangslänge des Vorname-Präfixes.

    Returns:
        Namensteile ``("V.", Nachname)`` bzw. ``(Nachname, "")`` ohne Präfix.
    """
    max_first_len = max((len(s.first_name.strip()) for s in students), default=0)
    length = start_length
    labels: dict[StudentId, NameParts] = {}
    while True:
        labels = {}
        for s in students:
            prefix = s.first_name.strip()[:length]
            labels[s.student_id] = (f"{prefix}.", last) if prefix else (last, "")
        if _all_distinct(labels) or length >= max_first_len:
            return labels
        length += 1


def compute_display_name_parts(
    students: Sequence[Student],
    name_format: str,
    disambiguate: bool,
) -> dict[StudentId, NameParts]:
    """Berechnet den Anzeigenamen jedes Schülers in *students* als Namensteile.

    Einzige Implementierung der Namensanzeige; ``compute_display_names`` setzt
    nur die Teile zusammen. Ansichten mit wenig Platz (Sitzplan-Vorschau)
    brechen über ``fit_name_to_width`` zwischen den Teilen um.

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
        Dict von ``StudentId`` auf ``NameParts``.
    """
    if not disambiguate or name_format == "Vorname Nachname":
        return {
            s.student_id: _format_fixed(s.first_name.strip(), s.last_name.strip(), name_format)
            for s in students
        }

    result: dict[StudentId, NameParts] = {}

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


def compute_display_names(
    students: Sequence[Student],
    name_format: str,
    disambiguate: bool,
) -> dict[StudentId, str]:
    """Berechnet den einzeiligen Anzeigenamen für jeden Schüler in *students*.

    Dünner Adapter auf ``compute_display_name_parts`` (Regeln siehe dort).

    Args:
        students: Alle Schüler, deren Namen im selben Renderdurchlauf gezeigt werden.
        name_format: Eines der fünf ``NAME_FORMAT_OPTIONS``.
        disambiguate: Ob der Eindeutigkeits-Modus aktiv ist.

    Returns:
        Dict von ``StudentId`` auf fertig formatierten Anzeigenamen.
    """
    return {
        student_id: join_name_parts(parts)
        for student_id, parts in compute_display_name_parts(students, name_format, disambiguate).items()
    }
