"""Docs-Navigation-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt den Abgleich Auswahl → Doku-Tabelle (``_sync_docs_cursor``), die aktive
logische Spalte (inkl. Datumsanker), Inline-Editor-Schließung und Wert-Anwendung
für die Dokumentations-Tabelle bereit.
"""

from __future__ import annotations

from app.core.domain.grade_scale import scale_for
from app.core.intents.grade_intents import RecordGradeIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult


class DocsNavMixin:
    """Mixin: Doku-Cursor-Abgleich, Spaltenauswahl und Inline-Editor-Verwaltung (v4)."""

    def _sync_docs_cursor(self) -> None:
        """Einziger Abgleich Auswahl → Doku-Tabelle: Zeile, aktive Spalte, Sichtbarkeit, Statuszeile.

        Ersetzt das frühere Zell-Overlay, das Neusetzen aller Spaltenköpfe und
        den Auswahl-Abgleich über drei Treeviews: das Grid verschiebt nur sein
        Auswahlband, den Zellcursor und die Spaltenmarke (wenige Tk-Aufrufe,
        unabhängig von der Spaltenzahl) und scrollt bei Bedarf.
        """
        row_id = None
        if self._doc_student_coords:
            index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
            row_id = self._doc_row_id_by_student_index.get(index)
        key = self._doc_active_column_key()
        self.docs_grid.set_cursor(row_id, key)
        if row_id is not None:
            self.docs_grid.see(row_id, key)
        self._refresh_doc_selection_status()

    def _close_docs_inline_editor(self, apply_changes: bool = False) -> None:
        """Schließt den Inline-Editor und wendet ggf. den eingegebenen Wert an.

        Args:
            apply_changes: Falls ``True``, wird ``_apply_docs_inline_editor_value`` aufgerufen.
        """
        editor = self._docs_inline_editor
        if editor is None:
            return
        if apply_changes:
            self._apply_docs_inline_editor_value()
        if editor.winfo_exists():
            editor.destroy()
        self._docs_inline_editor = None
        self._docs_inline_editor_row_id = None
        self._docs_inline_editor_kind = None
        self._docs_inline_editor_model_column = None

    def _apply_docs_inline_editor_value(self) -> None:
        """Übernimmt den Wert aus dem aktiven Inline-Editor als Noteneintrag (v4).

        Parst den Text als Dezimalzahl (Komma oder Punkt) und dispatcht
        ``RecordGradeIntent``. Bei leerem Text wird die Note gelöscht
        (``grade=None``). Werte außerhalb der Plan-Skala werden mit dem
        Hinweis der Skala abgelehnt statt still geclampt — sonst würde z. B.
        eine versehentlich eingetippte Punktzahl 12 in einem Notenplan
        unbemerkt als 6.0 gespeichert.
        """
        if not self.current_plan:
            return
        if self._docs_inline_editor is None or self._docs_inline_editor_kind != "grade":
            return

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        x, y, date_key = selected

        column_id = self._docs_inline_editor_model_column
        if not column_id:
            return
        raw_text = self._docs_inline_editor.get().strip()
        scale = scale_for(self.current_plan.documentation.grade_scale)
        grade_value: float | None
        if not raw_text:
            grade_value = None
        else:
            try:
                grade_value = float(raw_text.replace(",", "."))
            except ValueError:
                grade_value = None
            if grade_value is None or not scale.contains(grade_value):
                self.status_var.set(scale.input_hint)
                return

        student = self.current_plan.student_at(x, y)
        if not student:
            return
        self._controller.dispatch(
            RecordGradeIntent(
                student_id=student.student_id,
                date=date_key,
                column_id=column_id,
                grade=grade_value,
            )
        )
        status = "Note geloescht" if grade_value is None else "Note aktualisiert"
        self.status_var.set(status)

    def _on_docs_inline_editor_return(self, _event) -> EventResult:
        """Schließt den Inline-Editor mit Übernahme (Return/KP_Enter).

        Args:
            _event: bw-gui-``KeyEvent`` (Inhalt wird nicht ausgewertet).
        """
        self._close_docs_inline_editor(apply_changes=True)
        self.docs_grid.focus(self._doc_active_column_key())
        return EventResult.HANDLED

    def _on_docs_inline_editor_escape(self, _event) -> EventResult:
        """Bricht den Inline-Editor ohne Übernahme ab (Escape).

        Args:
            _event: bw-gui-``KeyEvent`` (Inhalt wird nicht ausgewertet).
        """
        self._close_docs_inline_editor(apply_changes=False)
        self.docs_grid.focus(self._doc_active_column_key())
        return EventResult.HANDLED

    def _open_selected_docs_grade_cell_editor(self) -> None:
        """Öffnet den Inline-Noten-Editor für die aktuell ausgewählte Doku-Zelle."""
        if not self._doc_selected_nondate_column_id or not self._doc_selected_nondate_column_id.startswith("grade_"):
            return
        selected_iid = self._doc_row_id_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is None:
            return
        self._open_docs_inline_grade_editor(selected_iid, self._doc_selected_nondate_column_id)

    def _doc_active_column_key(self) -> str | None:
        """Liefert die aktive logische Spalte der Dokutabelle.

        Returns:
            Die aktive Nicht-Datum-Spalte (Name/Fixspalte), sonst der Schlüssel
            des Datumsankers; ``None`` nur ohne Datumsspalten.
        """
        if self._doc_selected_nondate_column_id is not None:
            return self._doc_selected_nondate_column_id
        return self._doc_axis.date_key(self._doc_selected_date_index)

    def _set_doc_active_column(self, key: str) -> None:
        """Macht *key* zur aktiven logischen Spalte.

        Datumsspalte → Datumsanker auf diese Spalte, keine Nicht-Datum-Spalte
        aktiv. Andere Spalte (Name/Fixspalte) → als Nicht-Datum-Spalte aktiv;
        der Datumsanker bleibt als Ziel für Symbolaktionen und Rücksprung erhalten.

        Args:
            key: Existierender, auswählbarer Spaltenschlüssel.
        """
        date_index = self._doc_axis.date_index_of(key)
        if date_index is not None:
            self._select_doc_date_column(date_index)
        else:
            self._select_doc_nondate_column(key)

    def _is_valid_doc_nondate_column(self, key: str | None) -> bool:
        """Prüft, ob *key* als aktive Nicht-Datum-Spalte gültig ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True`` für existierende, auswählbare Namens- oder Fixspalten.
        """
        return self._doc_axis.is_selectable(key) and not self._doc_axis.is_date(key)

    def _select_doc_date_column(self, date_index: int) -> None:
        """Wählt eine Datumsspalte aus (setzt den Datumsanker); hebt eine aktive Nicht-Datum-Spalte auf.

        Args:
            date_index: Index der Zieldatumsspalte in ``self._doc_dates``.
        """
        self._doc_selected_date_index = date_index
        self._doc_selected_nondate_column_id = None

    def _select_doc_nondate_column(self, column_id: str | None) -> None:
        """Setzt die aktive Nicht-Datum-Spalte (Name/Fixspalte) oder ``None`` für den Datumsanker.

        Rührt bewusst nicht an ``_doc_selected_date_index`` — der Index
        bleibt als Rücksprungpunkt erhalten, falls der Nutzer zurück in den
        Datumsmodus wechselt.

        Args:
            column_id: Schlüssel der Namens-/Fixspalte oder ``None``.
        """
        self._doc_selected_nondate_column_id = column_id

    def _clamp_doc_column_selection_after_rebuild(self, date_count: int) -> None:
        """Hält Datumsanker und aktive Nicht-Datum-Spalte nach einem Rebuild gültig.

        Deterministische Regel (Invariante: aktive Spalte ist danach gültig):
        der Datumsanker wird auf ``[0, date_count - 1]`` geklemmt; eine nicht
        mehr existierende Nicht-Datum-Spalte (z. B. gelöschte Notenspalte)
        wird auf ``None`` gesetzt, womit der geklemmte Datumsanker aktiv wird.
        Namensspalten existieren immer und bleiben gültig. Keine
        Auswahl-Aktion, löscht insbesondere keine noch gültige Spalte.

        Args:
            date_count: Aktuelle Anzahl der Datumsspalten nach dem Rebuild.
        """
        self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, date_count - 1)))
        if not self._is_valid_doc_nondate_column(self._doc_selected_nondate_column_id):
            self._doc_selected_nondate_column_id = None
