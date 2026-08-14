"""Namenfit-kompatibler CSV-Export für Sitzpläne.

Erzeugt die Zeilen einer CSV-Datei im Sitzraster-Format, das Namenfit
(``A:\\Code\\namenfit``, ``app/core/layout.py::load_csv_layout``) beim Import
erwartet: Kopfzeile = Tischgruppen-Label (eine Leerzelle übernimmt das Label
der letzten nicht-leeren Zelle links davon), Datenzeilen = Schülernamen an
ihrer Sitzposition innerhalb der jeweiligen Tischgruppe. Reine Domain-Logik
ohne Datei-I/O — siehe ``app/infrastructure/exporters/namenfit_csv_exporter.py``
für den eigentlichen Dateischreib-Vorgang.

Zeilen-Konvention (siehe ``app/adapters/gui/_mixin_grid_render.py``, Zeile
``y1 = cy * self.cell_size``, keine Invertierung): Kartographs y-Achse wächst
mit dem Canvas-Pixel-y, also nach unten. Der Lehrertisch sitzt in Kartograph
standardmäßig am unteren Rand des Rasters — "unten" ist im Klassenraum-Sinn
also immer "vorne" (Richtung Lehrertisch), "oben" immer "hinten". Namenfits
eigene Richtungsdefinition (``directional_neighbors_of()`` in
``A:\\Code\\namenfit\\app\\core\\models.py``) sagt: "front" = größere Zeile,
"behind" = kleinere Zeile. Das deckt sich exakt mit steigendem Kartograph-y,
daher wird Kartograph-y unverändert (nur pro Tischgruppe auf 0 normalisiert)
als Namenfit-Zeile übernommen — keine Invertierung, keine Heuristik.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.models_v4 import SeatingPlan, Student
from app.core.domain.student_id import StudentId
from app.core.domain.student_naming import compute_display_names
from app.core.usecases.v4.tablegroup_usecases import normalize_tablegroups

_TABLE_LABEL_PREFIX = "Tisch "


class NamenfitExportError(Exception):
    """Basisklasse für alle Fehler, die einen Namenfit-CSV-Export verhindern."""


@dataclass(frozen=True)
class UngroupedStudent:
    """Ein benannter Schüler ohne auflösbare Tischgruppennummer."""

    display_name: str
    x: int
    y: int


class UngroupedStudentsError(NamenfitExportError):
    """Mindestens ein benannter Schüler gehört zu keiner nummerierten Tischgruppe.

    Nach ``normalize_tablegroups()`` sollte das im Normalbetrieb nie auftreten:
    jede Sitzplatz-Komponente mit mindestens einem benannten Schüler bekommt
    dort eine Nummer, auch ein einzeln sitzender Schüler ohne Nachbarn. Dieser
    Fehler ist eine bewusste Absicherung genau dieser Invariante statt eines
    stillschweigenden Überspringens, falls sie doch einmal verletzt wird
    (z. B. durch eine von Hand bearbeitete oder beschädigte Plandatei).
    """

    def __init__(self, offenders: list[UngroupedStudent]) -> None:
        self.offenders = offenders
        names = ", ".join(f"{o.display_name} ({o.x},{o.y})" for o in offenders)
        super().__init__(f"{len(offenders)} Schüler ohne Tischgruppen-Nummer, Export abgebrochen: {names}")


@dataclass(frozen=True)
class DuplicateDisplayName:
    """Zwei oder mehr Schüler, deren Anzeigename auch nach Eindeutigkeits-Auflösung identisch ist."""

    display_name: str
    count: int


class DuplicateDisplayNamesError(NamenfitExportError):
    """Namenfit verlangt eindeutige Namen pro Datei; Duplikate würden sich beim Import gegenseitig überschreiben."""

    def __init__(self, duplicates: list[DuplicateDisplayName]) -> None:
        self.duplicates = duplicates
        names = ", ".join(f"{d.display_name} ({d.count}x)" for d in duplicates)
        super().__init__(f"Anzeigenamen sind nicht eindeutig, Export abgebrochen: {names}")


def _resolve_group_numbers(export_plan: SeatingPlan, named_students: list[Student]) -> dict[StudentId, int]:
    """Ordnet jedem benannten Schüler seine Tischgruppen-Nummer zu.

    Args:
        export_plan: Bereits über ``normalize_tablegroups()`` normalisierter Plan.
        named_students: Vorab gefilterte Liste benannter Schüler.

    Returns:
        Dict von ``student_id`` auf Tischgruppen-Nummer.

    Raises:
        UngroupedStudentsError: Siehe Klassendokumentation.
    """
    offenders: list[UngroupedStudent] = []
    group_by_student_id: dict[StudentId, int] = {}
    for student in named_students:
        group = export_plan.tablegroup_for_seat(student.seat.x, student.seat.y)
        if group is None or group.group_id <= 0:
            offenders.append(
                UngroupedStudent(display_name=student.first_name.strip(), x=student.seat.x, y=student.seat.y)
            )
            continue
        group_by_student_id[student.student_id] = group.group_id
    if offenders:
        raise UngroupedStudentsError(offenders)
    return group_by_student_id


def _check_display_names_unique(display_names: dict) -> None:
    """Prüft, dass jeder Anzeigename in *display_names* nur einmal vorkommt.

    Raises:
        DuplicateDisplayNamesError: Siehe Klassendokumentation.
    """
    counts: dict[str, int] = {}
    for name in display_names.values():
        counts[name] = counts.get(name, 0) + 1
    duplicates = [DuplicateDisplayName(name, count) for name, count in sorted(counts.items()) if count > 1]
    if duplicates:
        raise DuplicateDisplayNamesError(duplicates)


def build_namenfit_rows(
    plan: SeatingPlan,
    name_format: str,
    disambiguate_colliding_names: bool = True,
) -> list[list[str]]:
    """Baut die vollständigen CSV-Zeilen für den Namenfit-Import.

    Jede Tischgruppe wird als eigener, in sich geschlossener Spaltenblock
    angelegt (lokale Zeile/Spalte = Kartograph-y/x minus dem Minimum
    innerhalb dieser Gruppe) und die Blöcke werden in aufsteigender
    Gruppennummer-Reihenfolge nebeneinandergelegt. Da Namenfits
    Nachbarschafts-Suche (``directional_neighbors_of()``) Kandidaten nur
    innerhalb derselben Tischgruppe vergleicht, ist es unerheblich, dass
    verschiedene Blöcke dieselben Zeilennummern der gemeinsamen CSV-Datei
    teilen — es entstehen dadurch keine falschen Nachbarschaften.

    Args:
        plan: Sitzplan, dessen benannte Schüler exportiert werden sollen.
            Wird intern über ``normalize_tablegroups()`` normalisiert; der
            übergebene Plan selbst bleibt unverändert.
        name_format: Eines der ``NAME_FORMAT_OPTIONS`` aus ``settings.py``.
        disambiguate_colliding_names: Nachname-Ergänzung bei gleichen
            Vornamen (siehe ``compute_display_names()``). Standardmäßig
            ``True`` für den CSV-Export — unabhängig von der App-weiten
            Grid-Einstellung —, da Namenfit eindeutige Namen voraussetzt.

    Returns:
        Liste von Zeilen (jede Zeile eine Liste von Zellen-Strings); Zeile 0
        ist die Kopfzeile. Direkt an ``csv.writer.writerows()`` übergebbar.

    Raises:
        UngroupedStudentsError: Wenn mindestens ein benannter Schüler zu
            keiner nummerierten Tischgruppe gehört.
        DuplicateDisplayNamesError: Wenn zwei oder mehr Schüler denselben
            Anzeigenamen hätten (auch nach Eindeutigkeits-Auflösung).
    """
    export_plan = normalize_tablegroups(plan)
    named_students = [s for s in export_plan.classroom.students if s.is_named()]

    group_number_by_student_id = _resolve_group_numbers(export_plan, named_students)
    display_names = compute_display_names(named_students, name_format, disambiguate_colliding_names)
    _check_display_names_unique(display_names)

    groups_sorted = sorted(export_plan.tablegroups, key=lambda g: g.group_id)

    total_rows = 0
    blocks: list[tuple[int, int, int, int, int]] = []  # (group_id, col_offset, width, min_x, min_y)
    col_offset = 0
    for group in groups_sorted:
        xs = [seat.x for seat in group.seats]
        ys = [seat.y for seat in group.seats]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        blocks.append((group.group_id, col_offset, width, min_x, min_y))
        total_rows = max(total_rows, height)
        col_offset += width
    total_cols = col_offset

    header = [""] * total_cols
    for group_id, block_col_offset, _width, _min_x, _min_y in blocks:
        header[block_col_offset] = f"{_TABLE_LABEL_PREFIX}{group_id}"

    data_rows = [["" for _ in range(total_cols)] for _ in range(total_rows)]
    block_by_group_id = {group_id: (block_col_offset, min_x, min_y) for group_id, block_col_offset, _w, min_x, min_y in blocks}
    for student in named_students:
        group_id = group_number_by_student_id[student.student_id]
        block_col_offset, min_x, min_y = block_by_group_id[group_id]
        local_col = student.seat.x - min_x
        local_row = student.seat.y - min_y
        data_rows[local_row][block_col_offset + local_col] = display_names[student.student_id]

    return [header, *data_rows]
