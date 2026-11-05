"""Docs-Edit-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Umschalten und Löschen von Dokumentationssymbolen sowie
den Inline-Noten-Editor der Dokutabelle bereit.
"""

from __future__ import annotations

from app.core.domain.grade_scale import scale_for
from app.core.domain.symbol_toggle import next_symbol_toggle_strength
from app.core.intents.grade_intents import RecordGradeIntent
from app.core.intents.session_intents import ClearDocEntryIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.adapters.gui._local_keys import ENTER, ESCAPE, widget_keys
from app.adapters.gui.doc_action_target import DocActionTarget
from app.adapters.gui.docs_table_model import GradeCellTarget, grade_column_id
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import on_focus_change, ui
from bw_gui.runtime import widgets as tui


class DocsEditMixin:
    """Mixin: Symbol-Umschalten, Symbol-Löschen und Inline-Noten-Editor in der Dokumentations-Ansicht (v4)."""

    def _open_docs_inline_grade_editor(self, row_id: str, grade_column_key: str) -> None:
        """Öffnet einen Entry-Inline-Editor in der Noten-Zelle (*row_id*, *grade_column_key*).

        Die Zellgeometrie liefert ``DataGrid.cell_bbox`` (scrollt die Zelle
        sichtbar und rendert vorher ausstehende Änderungen, damit die Position
        stimmt); der Editor liegt direkt auf dem Bereich, der die Spalte zeigt.

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            grade_column_key: Spaltenschlüssel einer Notenspalte, z. B. ``"grade_<id>"``.
        """
        if not self.current_plan:
            return
        if not self._doc_axis.is_grade(grade_column_key):
            return
        self._close_docs_inline_editor(apply_changes=False)
        box = self.docs_grid.cell_bbox(row_id, grade_column_key)
        if box is None:
            return
        host, x, y, width, height = box

        target = self._grade_edit_target(row_id, grade_column_key)
        if target is None:
            return
        doc = self.current_plan.documentation
        value = doc.grade_of(target.student_id, target.column_id)
        current_text = "" if value is None else scale_for(doc.grade_scale).format_input(value)

        editor = tui.Entry(host)
        editor.insert(0, current_text)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.selection_range(0, ui.END)
        keys = widget_keys(editor)
        keys.bind(ENTER, self._on_docs_inline_editor_return, binding_id="docs.inline.return", intent="docs.inline.return", allow_when_text_input=True)
        keys.bind(ESCAPE, self._on_docs_inline_editor_escape, binding_id="docs.inline.escape", intent="docs.inline.escape", allow_when_text_input=True)
        on_focus_change(editor, on_lost=lambda _change: self._close_docs_inline_editor(apply_changes=True))

        self._docs_inline_editor = editor
        self._docs_inline_editor_target = target

    def _grade_edit_target(self, row_id: str, grade_column_key: str) -> GradeCellTarget | None:
        """Einzige Regel, *welche* Note eine Notenzelle bearbeitet: Zeile und Spalte der Zelle.

        Nie die spätere Auswahl; ein Datum spielt keine Rolle (eine Note je Spalte).

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            grade_column_key: Spaltenschlüssel ``"grade_<id>"``.

        Returns:
            Das Ziel oder ``None`` (unbekannte Zeile, unbenannter Tisch, keine Notenspalte).
        """
        student = self._named_docs_student(self._doc_student_index_by_iid.get(row_id))
        column_id = grade_column_id(grade_column_key)
        if student is None or column_id is None:
            return None
        return GradeCellTarget(student.student_id, column_id)

    def _toggle_documentation_symbol_at(self, target: DocActionTarget, symbol: str) -> None:
        """Schaltet *symbol* im Tageseintrag von *target* um (v4).

        Diagnosesymbole zyklen 0→1→2→3→0, Doku-Symbole (eingebaut wie eigen)
        togglen binär 0↔1 (siehe ``next_symbol_toggle_strength``). Reiner
        Toggle-Kern ohne UI-Refresh und ohne eigene Zielauflösung; das Ziel
        kommt aus ``_doc_action_target()``.

        Args:
            target: Schüler und Datum des Tageseintrags.
            symbol: Bezeichner des umzuschaltenden Symbols (eingebauter
                Meaning-Text oder eigene Symbol-ID).
        """
        current_strength = 0
        session = self.current_plan.documentation.session_for_date(target.date)
        if session is not None:
            entry = session.entry_for(target.student_id)
            if entry is not None:
                current_strength = int(entry.symbols.get(symbol, 0))
        next_strength = next_symbol_toggle_strength(
            current_strength, is_diagnostic=symbol in self.diagnostic_symbol_catalog
        )
        self._controller.dispatch(
            RecordDocumentationSymbolIntent(
                student_id=target.student_id,
                date=target.date,
                symbol=symbol,
                strength=next_strength,
            )
        )

    def _toggle_documentation_symbol(self, symbol: str) -> None:
        """Schaltet ein Doku-Symbol für das Ziel der aktiven Oberfläche um.

        Dokuansicht: ausgewählte Zeile am Datumsanker; Raster: markierter
        Tisch heute (Regel allein in ``_doc_action_target()``).

        Args:
            symbol: Bezeichner des umzuschaltenden Symbols (eingebauter
                Meaning-Text oder eigene Symbol-ID).
        """
        target = self._doc_action_target("Symbole")
        if target is not None:
            self._toggle_documentation_symbol_at(target, symbol)

    def clear_selected_documentation_symbol(self) -> None:
        """Löscht genau die aktive Zelle der Doku-Tabelle.

        Notenspalte: nur diese Note. Datumsspalte: der Tageseintrag (Symbole,
        Mitarbeit, Notiz). Name, Zusammenfassung, Teil- und Gesamtnote sind nicht
        löschbar -- dort bleibt alles unverändert, die Statuszeile sagt es.
        """
        student, key = self._selected_docs_student(), self._doc_active_column_key()
        if student is None or key is None:
            return
        column_id = grade_column_id(key)
        if column_id is not None:
            self._controller.dispatch(RecordGradeIntent(student_id=student.student_id, column_id=column_id, grade=None))
            self.status_var.set("Note gelöscht")
        elif self._doc_axis.is_date(key):
            self._controller.dispatch(ClearDocEntryIntent(student_id=student.student_id, date=self._doc_anchor_date()))
        else:
            self.status_var.set("In dieser Spalte gibt es nichts zu löschen.")
