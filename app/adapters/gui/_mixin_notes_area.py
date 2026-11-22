"""Notizenbereich der Datenansicht: Spalten, Zellen, Titel, Ja/Nein umschalten (Mixin).

Der Bereich zeigt in dieser Reihenfolge:

1. "Notizen" -- die allgemeinen Notizen jeder Person (``DiagnosticProfile.notes``),
2. eine Ja/Nein-Spalte je Farbe bzw. farbloser Markierung (``flag_columns``:
   Paletteneinträge und getragene Markierungen; Titel = Bedeutung),
3. die eigenen Notizspalten (``SeatingPlan.note_columns``) in Anlagereihenfolge.

Die Tabelle (``DocsTableMixin``) fragt hier nur Spalten, Zellen und Titel ab;
die Regeln stehen in den Domänenmodulen (Zellinhalt: ``note_groups.note_entries``;
``_note_source_of`` übersetzt den Tabellenschlüssel in deren ``NoteSource``).
"""

from __future__ import annotations

from app.adapters.gui.docs_table_model import (
    NOTES_KEY,
    flag_column_key,
    flag_key_of,
    note_column_id,
    note_column_key,
    notes_area_kind,
)
from app.core.domain.color_order import palette_color
from app.core.domain.flag_columns import FLAG_KIND_LABEL, flag_column_keys, is_colorless_flag
from app.core.domain.models_v4 import Student
from app.core.domain.note_groups import NoteSource, note_entries
from app.core.domain.student_notes import notes_inline
from app.core.intents.color_intents import ToggleColorIntent
from app.core.usecases.v4.color_usecases import palette_meaning


class NotesAreaMixin:
    """Mixin: Inhalt des Notizenbereichs und das Umschalten von Ja/Nein-Zellen."""

    def _flag_keys_in_use(self) -> list[str]:
        """Vergebene Ja/Nein-Schlüssel: Paletteneinträge (Anlagereihenfolge), dann getragene Markierungen.

        Einzige Stelle für "welche Farben sind als Spalte vergeben" in der GUI
        (Spaltenliste und freie Farben im Anlegen-Dialog).
        """
        plan = self.current_plan
        return [*plan.color_palette, *(tag for s in plan.classroom.students for tag in s.diagnostic.color_tags)]

    def _flag_keys(self) -> list[str]:
        """Schlüssel aller Ja/Nein-Spalten des offenen Plans in Anzeigereihenfolge.

        Returns:
            Farben in Palettenreihenfolge, dann Fremdschlüssel, dann farblose.
        """
        return flag_column_keys(self._color_order, self._flag_keys_in_use())

    def _notes_area_columns(self) -> list[tuple[str, str]]:
        """Spalten des Notizenbereichs als ``(Schlüssel, Spaltenart)`` für ``DocColumnAxis``.

        Returns:
            Allgemeine Notizen, Ja/Nein-Spalten, eigene Notizspalten.
        """
        columns: list[tuple[str, str]] = [(NOTES_KEY, "notes")]
        columns.extend((flag_column_key(key), "flag") for key in self._flag_keys())
        columns.extend((note_column_key(c.column_id), notes_area_kind(c.kind)) for c in self.current_plan.note_columns)
        return columns

    def _notes_area_cells(self, student: Student, flag_keys: list[str]) -> dict[str, str]:
        """Zelltexte des Notizenbereichs für eine Person.

        Einträge aus ``note_groups.note_entries`` (dieselbe Regel wie der
        Gruppen-Export), Anzeigetexte mit " · " verbunden (``notes_inline``).

        Args:
            student: Person der Zeile.
            flag_keys: Ergebnis von ``_flag_keys`` (einmal je Tabellenaufbau berechnet).

        Returns:
            Spaltenschlüssel → Zelltext (leere Zellen fehlen).
        """
        sources = [(NOTES_KEY, NoteSource("notes"))]
        sources.extend((flag_column_key(key), NoteSource("flag", key)) for key in flag_keys)
        sources.extend((note_column_key(c.column_id), NoteSource("column", c.column_id)) for c in self.current_plan.note_columns)
        cells: dict[str, str] = {}
        for column_key, source in sources:
            entries = note_entries(self.current_plan, student, source)
            if entries:
                cells[column_key] = notes_inline(display for _stored, display in entries)
        return cells

    def _note_source_of(self, column_key: str) -> NoteSource | None:
        """Spalte des Notizenbereichs zum Tabellenschlüssel, ``None`` für andere Bereiche.

        Args:
            column_key: Spaltenschlüssel der Datenansicht.
        """
        if column_key == NOTES_KEY:
            return NoteSource("notes")
        flag_key = flag_key_of(column_key)
        if flag_key is not None:
            return NoteSource("flag", flag_key)
        column_id = note_column_id(column_key)
        return NoteSource("column", column_id) if column_id is not None else None

    def _notes_column_label(self, column_key: str) -> str | None:
        """Spaltentitel im Notizenbereich, ``None`` für Spalten anderer Bereiche.

        Ja/Nein: Bedeutung, bei farbigen mit der Farbe in Klammern
        ("Förderbedarf (Gelb)"); ohne Bedeutung nur die Farbe bzw. "Ja/Nein".

        Args:
            column_key: Spaltenschlüssel.
        """
        flag_key = flag_key_of(column_key)
        if flag_key is not None:
            meaning = palette_meaning(self.current_plan, flag_key)
            if is_colorless_flag(flag_key):
                return meaning or FLAG_KIND_LABEL
            color_label, _hex = palette_color(self._color_by_key, flag_key)
            return f"{meaning} ({color_label})" if meaning else color_label
        column_id = note_column_id(column_key)
        if column_id is not None:
            return next((c.title for c in self.current_plan.note_columns if c.column_id == column_id), column_key)
        return None

    def _toggle_docs_flag(self, row_id: str, flag_key: str | None) -> bool:
        """Schaltet die Ja/Nein-Markierung *flag_key* der Zeile *row_id* um (wie ein Farbpunkt).

        Dauerhaft Abwesende sind gesperrt (``_report_if_locked``, dieselbe Regel
        wie für Farbpunkte im Raster).

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            flag_key: Farb- oder ``flag_…``-Schlüssel.

        Returns:
            ``True``, wenn die Aktion behandelt wurde (auch gesperrt mit Hinweis).
        """
        student = self._named_docs_student(self._doc_student_index_by_iid.get(row_id))
        if student is None or flag_key is None:
            return False
        if not self._report_if_locked(student):
            self._controller.dispatch(ToggleColorIntent(student_id=student.student_id, color_key=flag_key))
        return True
