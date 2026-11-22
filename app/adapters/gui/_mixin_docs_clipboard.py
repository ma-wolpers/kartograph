"""Kopieren, Ausschneiden und Einfügen in der Datenansicht (Mixin, Strg+C/X/V).

Wirkt auf die ausgewählte Zelle; ``copy_selection``/``cut_selection``/
``paste_selection`` leiten in der Datenansicht hierher. Regeln:

- **Kopieren** geht in jeder Zelle: in die System-Zwischenablage kommt der Wert
  in Eingabeform (Zellen mit Textwert, ``docs_cell_editing.cell_text``) bzw. der
  angezeigte Text. Eine Doku-Zelle merkt sich zusätzlich ihren Tageseintrag
  (``docs_clipboard``).
- **Einfügen** in eine Zelle mit Textwert prüft den Text wie eine Eingabe im
  Editor (``commit_cell_text``); in eine Doku-Zelle kommt der kopierte
  Tageseintrag (``SetDocEntryIntent``, ersetzt den Eintrag dort).
- **Ausschneiden** = Kopieren + Löschen über dieselben Wege wie Entf.

Jede Änderung ist genau ein Intent und damit ein Undo-Schritt; die
Zwischenablage selbst gehört nicht zum Plan. Gesperrte Ziele (dauerhaft
Abwesende) meldet ``_report_if_locked``.
"""

from __future__ import annotations

from copy import deepcopy

from app.adapters.gui.docs_cell_editing import CellEditTarget, cell_text, commit_cell_text
from app.adapters.gui.docs_clipboard import CopiedDocEntry, entry_to_paste
from app.core.domain.models_v4 import SessionEntry, Student
from app.core.intents.session_intents import ClearDocEntryIntent, SetDocEntryIntent

_NOT_WRITABLE = "Ausschneiden und Einfügen gehen nur in Noten-, Notiz- und Doku-Zellen."
_NO_TEXT = "Die Zwischenablage enthält keinen Text."
_NO_DOC_ENTRY = "In eine Doku-Zelle lässt sich nur eine kopierte Doku-Zelle aus diesem Sitzplan einfügen."


class DocsClipboardMixin:
    """Mixin: Zwischenablage für die ausgewählte Zelle der Datenansicht."""

    def _docs_clipboard_cell(self) -> tuple[Student, str, str] | None:
        """Person, Zeilen-ID und Spaltenschlüssel der ausgewählten Zelle, sonst ``None``."""
        student, key = self._selected_docs_student(), self._doc_active_column_key()
        row_id = self._doc_row_id_by_student_index.get(self._doc_selected_student_index)
        if student is None or key is None or row_id not in self._doc_rows:
            return None
        return student, row_id, key

    def _doc_entry_of(self, student: Student) -> SessionEntry:
        """Tageseintrag der Person am Datumsanker (leer, wenn es keinen gibt)."""
        session = self.current_plan.documentation.session_for_date(self._doc_anchor_date())
        entry = session.entry_for(student.student_id) if session is not None else None
        return deepcopy(entry) if entry is not None else SessionEntry()

    def _copy_docs_cell_to_clipboard(self, student: Student, row_id: str, key: str) -> None:
        """Legt den Wert der Zelle in die Zwischenablage (Doku-Zelle: auch den Eintrag merken)."""
        self._docs_copied_entry = None
        if self._doc_axis.holds_text(key):
            text = cell_text(self.current_plan, CellEditTarget(student.student_id, key))
        else:
            text = self._doc_axis.value_of(self._doc_rows[row_id], key)
            if self._doc_axis.is_date(key):
                self._docs_copied_entry = CopiedDocEntry(self.current_plan.plan_id, text, self._doc_entry_of(student))
        self._text_clipboard.write_text(text)

    def copy_docs_cell(self) -> None:
        """Kopiert die ausgewählte Zelle in die Zwischenablage (Plan bleibt unverändert)."""
        cell = self._docs_clipboard_cell()
        if cell is None:
            return
        self._copy_docs_cell_to_clipboard(*cell)
        self.status_var.set("Kopiert")

    def cut_docs_cell(self) -> None:
        """Kopiert die ausgewählte Zelle und löscht ihren Wert (ein Undo-Schritt)."""
        cell = self._docs_clipboard_cell()
        if cell is None:
            return
        student, row_id, key = cell
        if self._doc_axis.is_date(key):
            if self._report_if_locked(student):
                return
            intent = ClearDocEntryIntent(student_id=student.student_id, date=self._doc_anchor_date())
        elif self._doc_axis.holds_text(key):
            target = self._cell_edit_target(row_id, key)
            if target is None:
                return
            intent = commit_cell_text(self.current_plan, target, "").intent
        else:
            self.status_var.set(_NOT_WRITABLE)
            return
        self._copy_docs_cell_to_clipboard(student, row_id, key)
        self._controller.dispatch(intent)
        self.status_var.set("Ausgeschnitten")

    def paste_docs_cell(self) -> None:
        """Fügt die Zwischenablage in die ausgewählte Zelle ein (ein Undo-Schritt)."""
        cell = self._docs_clipboard_cell()
        if cell is None:
            return
        student, row_id, key = cell
        clipboard_text = self._text_clipboard.read_text()
        if self._doc_axis.is_date(key):
            if self._report_if_locked(student):
                return
            entry = entry_to_paste(self._docs_copied_entry, self.current_plan.plan_id, clipboard_text)
            if entry is None:
                self.status_var.set(_NO_DOC_ENTRY)
                return
            intent = SetDocEntryIntent(student_id=student.student_id, date=self._doc_anchor_date(), entry=deepcopy(entry))
        elif self._doc_axis.holds_text(key):
            if clipboard_text is None:
                self.status_var.set(_NO_TEXT)
                return
            target = self._cell_edit_target(row_id, key)
            if target is None:
                return
            commit = commit_cell_text(self.current_plan, target, clipboard_text)
            if commit.intent is None:
                self.status_var.set(commit.message)
                return
            intent = commit.intent
        else:
            self.status_var.set(_NOT_WRITABLE)
            return
        self._controller.dispatch(intent)
        self.status_var.set("Eingefügt")
