"""Spaltenknöpfe der Datenansicht: hinzufügen / umbenennen / löschen nach ausgewählter Zelle (Mixin).

Was gemeint ist, entscheidet allein ``docs_column_actions`` (``column_target``,
``can_run``, ``action_label``); hier steht nur, welcher vorhandene Dialog bzw.
Intent dazu gehört:

========== ============================ ========================= =========================
Aktion     Doku (Datum)                 Noten                     Notizen
========== ============================ ========================= =========================
add        ``add_documentation_date``   ``add_grade_column``      ``add_note_column``
rename     Datum ändern                 ``RenameGradeColumn``     Notiz: ``RenameNoteColumn``,
                                                                  Ja/Nein: ``SetPaletteMeaning``
delete     Datum löschen                Notenspalte löschen       ``delete_note_column``
groups     --                           --                        ``export_note_groups_dialog``
========== ============================ ========================= =========================

Knöpfe, die für die Auswahl nichts tun können, sind ausgegraut
(``_sync_docs_column_buttons``); ihr Hover-Text sagt warum.
"""

from __future__ import annotations

from collections.abc import Callable

from app.adapters.gui.dialog_services import simpledialog
from app.adapters.gui.docs_column_actions import ColumnAction, ColumnTarget, action_label, can_run, column_target
from app.adapters.gui.docs_table_model import flag_key_of, grade_column_id, note_column_id
from app.core.domain.data_view_areas import DataArea
from app.core.intents.base import Intent
from app.core.intents.color_intents import SetPaletteMeaningIntent
from app.core.intents.grade_intents import RenameGradeColumnIntent
from app.core.intents.note_intents import RenameNoteColumnIntent
from app.core.usecases.v4.color_usecases import palette_meaning


def _title_problem(text: str) -> str | None:
    """Eingabehinweis für einen leeren Titel, sonst ``None`` (Validator des Umbenennen-Dialogs)."""
    return None if text.strip() else "Der Titel darf nicht leer sein."


class DocsColumnActionsMixin:
    """Mixin: Spaltenaktionen der Datenansicht, abhängig von der ausgewählten Zelle."""

    def _docs_column_target(self) -> ColumnTarget | None:
        """Ziel der Spaltenaktionen: die aktive Spalte (``None`` für Namen)."""
        return column_target(self._doc_axis, self._doc_active_column_key())

    def _docs_column_action_label(self, action: ColumnAction) -> str:
        """Hover-Text des Knopfs *action* für die aktuelle Auswahl.

        Args:
            action: ``"add"``, ``"rename"``, ``"delete"`` oder ``"groups"``.
        """
        return action_label(action, self._docs_column_target())

    def _sync_docs_column_buttons(self) -> None:
        """Graut Spaltenknöpfe aus, die für die aktuelle Auswahl nichts tun können."""
        target = self._docs_column_target()
        for action, button in getattr(self, "_docs_column_buttons", {}).items():
            button.state(["!disabled"] if can_run(action, target) else ["disabled"])

    def _run_docs_column_action(self, action: ColumnAction) -> None:
        """Führt *action* für die Spalte der ausgewählten Zelle aus (Knopf und Tastenkürzel).

        Args:
            action: ``"add"``, ``"rename"``, ``"delete"`` oder ``"groups"``.
        """
        target = self._docs_column_target()
        if not self.current_plan or not can_run(action, target):
            self.status_var.set(action_label(action, target))
            return
        if action == "add":
            adders = {
                DataArea.DOKU: self.add_documentation_date_dialog,
                DataArea.NOTEN: self.add_grade_column_dialog,
                DataArea.NOTIZEN: self.add_note_column_dialog,
            }
            adders[target.area]()
        elif action == "rename":
            self._rename_docs_column(target)
        elif action == "groups":
            self.export_note_groups_dialog(target.key)
        else:
            self._delete_docs_column(target)

    def _rename_docs_column(self, target: ColumnTarget) -> None:
        """Umbenennen: Datum über den Datumsdialog, sonst Titel bzw. Bedeutung per Textdialog.

        Args:
            target: Spalte mit Art (``can_run`` geprüft).
        """
        if target.kind == "date":
            self.rename_selected_documentation_date_dialog()
            return
        current, make_intent = self._column_title_and_intent(target)
        title = simpledialog.askstring(
            action_label("rename", target), "Neuer Titel:", parent=self, initialvalue=current, validate=_title_problem
        )
        if title is not None and title.strip() != current:
            self._controller.dispatch(make_intent(title.strip()))

    def _column_title_and_intent(self, target: ColumnTarget) -> tuple[str, Callable[[str], Intent]]:
        """Bisheriger Titel und Intent-Fabrik für Noten-, Notiz- und Ja/Nein-Spalten.

        Args:
            target: Spalte der Art ``grade``, ``note`` oder ``flag``.
        """
        plan = self.current_plan
        if target.kind == "grade":
            column_id = grade_column_id(target.key)
            title = next(c.title for c in plan.documentation.grade_columns if c.column_id == column_id)
            return title, lambda text: RenameGradeColumnIntent(column_id=column_id, title=text)
        if target.kind == "note":
            column_id = note_column_id(target.key)
            title = next(c.title for c in plan.note_columns if c.column_id == column_id)
            return title, lambda text: RenameNoteColumnIntent(column_id=column_id, title=text)
        color_key = flag_key_of(target.key)
        return palette_meaning(plan, color_key), lambda text: SetPaletteMeaningIntent(color_key=color_key, meaning=text)

    def _delete_docs_column(self, target: ColumnTarget) -> None:
        """Löschen nach Rückfrage über den vorhandenen Dialog der Spaltenart.

        Args:
            target: Spalte mit Art (``can_run`` geprüft).
        """
        if target.kind == "date":
            self.delete_selected_documentation_date_dialog()
        elif target.kind == "grade":
            column_id = grade_column_id(target.key)
            column = next(c for c in self.current_plan.documentation.grade_columns if c.column_id == column_id)
            self._confirm_and_delete_grade_column(column)
        else:
            self.delete_note_column_dialog()
