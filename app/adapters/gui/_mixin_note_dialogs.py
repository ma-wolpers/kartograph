"""Dialoge des Notizenbereichs: allgemeine Notizen, Notizspalte anlegen und löschen (Mixin).

- ``edit_docs_general_notes_dialog``: die allgemeinen Notizen einer Person
  mehrzeilig bearbeiten (Lesen/Schreiben über ``docs_cell_editing``; OK = ein Undo-Schritt).
- ``add_note_column_dialog``: Titel und Typ (Text, Zahl, Datum, Ja/Nein). Bei
  Ja/Nein erscheint die Auswahl der freien Farben; ist keine frei, wird die
  Spalte farblos (Entscheidung der Nutzerin 2026-11-17).
- ``delete_note_column_dialog``: löscht die aktive Ja/Nein- oder Notizspalte nach Rückfrage.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, bind_action, dialog_keys
from app.adapters.gui.dialog_services import messagebox
from app.adapters.gui.docs_cell_editing import CellEditTarget, cell_text, commit_cell_text
from app.adapters.gui.docs_table_model import NOTES_KEY, flag_column_key, flag_key_of, note_column_id, note_column_key
from app.core.domain.color_order import palette_color
from app.core.domain.flag_columns import FLAG_KIND_LABEL, free_color_keys
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS
from app.core.domain.student_notes import NOTES_LABEL
from app.core.intents.color_intents import AddFlagColumnIntent, DeleteFlagColumnIntent
from app.core.intents.note_intents import AddNoteColumnIntent, DeleteNoteColumnIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import RadioGroup, WrappedTextField

_FLAG_TYPE = "flag"
"""Wert der Ja/Nein-Option im Typauswahlfeld (kein Typ von ``NOTE_VALUE_KINDS``)."""


class NoteDialogsMixin:
    """Mixin: Dialoge für allgemeine Notizen und eigene Notizspalten."""

    def edit_docs_general_notes_dialog(self, row_id: str) -> bool:
        """Öffnet die allgemeinen Notizen der Zeile *row_id* zum Bearbeiten (eine Zeile je Notiz).

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).

        Returns:
            ``True``, wenn der Dialog geöffnet wurde.
        """
        student = self._named_docs_student(self._doc_student_index_by_iid.get(row_id))
        if student is None:
            return False
        name = " ".join(part for part in (student.first_name, student.last_name) if part.strip())
        dialog = self._create_overlay_dialog(f"{NOTES_LABEL}: {name}", "420x300")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        field = WrappedTextField(frame, height=8)
        field.pack(fill="both", expand=True)
        target = CellEditTarget(student.student_id, NOTES_KEY)
        field.set(cell_text(self.current_plan, target))

        def confirm() -> None:
            commit = commit_cell_text(self.current_plan, target, field.get())
            dialog.destroy()
            self._controller.dispatch(commit.intent)

        self._build_grade_dialog_buttons(frame, dialog, confirm)
        self._focus_overlay_widget(dialog, field.text)
        return True

    def add_note_column_dialog(self) -> None:
        """Dialog "Notizspalte hinzufügen": Titel, Typ und bei Ja/Nein die Farbe.

        OK legt die Spalte als einen Undo-Schritt an und macht sie zur aktiven Spalte.
        """
        if not self.current_plan:
            return
        free = free_color_keys(self._color_order, self._flag_keys_in_use())
        dialog = self._create_overlay_dialog("Notizspalte hinzufügen", "380x380")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(frame, text="Titel").pack(anchor="w")
        title_var = ui.StringVar()
        title_entry = tui.Entry(frame, textvariable=title_var)
        title_entry.pack(fill="x", pady=(2, 10))
        type_var = ui.StringVar(value="text")
        type_options = [(key, spec.label) for key, spec in NOTE_VALUE_KINDS.items()] + [(_FLAG_TYPE, FLAG_KIND_LABEL)]
        RadioGroup(frame, title="Typ", variable=type_var, options=type_options).pack(anchor="w", pady=(0, 10))
        color_var = ui.StringVar(value=free[0] if free else "")
        color_frame = tui.Frame(frame)
        if free:
            options = [(key, palette_color(self._color_by_key, key)[0]) for key in free]
            RadioGroup(color_frame, title="Farbe", variable=color_var, options=options).pack(anchor="w")
        else:
            tui.Label(color_frame, text="Keine Farbe mehr frei – die Spalte wird farblos.").pack(anchor="w")
        type_var.trace_add("write", lambda *_: color_frame.pack(anchor="w") if type_var.get() == _FLAG_TYPE else color_frame.pack_forget())

        def confirm() -> None:
            dialog.destroy()
            self._add_note_column(title_var.get(), type_var.get(), color_var.get() or None)

        bind_action(dialog_keys(dialog), ENTER, confirm, binding_id="dialog.confirm")
        self._build_grade_dialog_buttons(frame, dialog, confirm)
        self._focus_overlay_widget(dialog, title_entry)

    def _add_note_column(self, title: str, type_key: str, color_key: str | None) -> None:
        """Legt die Spalte an und macht sie zur aktiven Spalte der Datenansicht.

        Args:
            title: Spaltentitel.
            type_key: Typschlüssel oder ``_FLAG_TYPE``.
            color_key: Gewählte freie Farbe (nur Ja/Nein; ``None`` = farblos).
        """
        before = set(self.current_plan.color_palette)
        if type_key == _FLAG_TYPE:
            self._controller.dispatch(AddFlagColumnIntent(title=title, color_key=color_key))
            added = [key for key in self.current_plan.color_palette if key not in before]
            new_key = flag_column_key(added[0]) if added else None
        else:
            self._controller.dispatch(AddNoteColumnIntent(title=title, kind=type_key))
            columns = self.current_plan.note_columns
            new_key = note_column_key(columns[-1].column_id) if columns else None
        if new_key is not None and self._doc_axis.has(new_key):
            self._select_doc_nondate_column(new_key)
            self._sync_docs_cursor()

    def delete_note_column_dialog(self) -> None:
        """Löscht die aktive Ja/Nein- oder Notizspalte nach Rückfrage (samt allen Einträgen)."""
        key = self._doc_active_column_key()
        flag_key, column_id = flag_key_of(key), note_column_id(key)
        if self.current_plan is None or (flag_key is None and column_id is None):
            self.status_var.set("Bitte zuerst eine Ja/Nein- oder Notizspalte auswählen")
            return
        title = self._doc_column_label(key)
        if not messagebox.askyesno("Spalte löschen", f"Spalte '{title}' inkl. aller Einträge löschen?", parent=self):
            return
        intent = DeleteFlagColumnIntent(key=flag_key) if flag_key is not None else DeleteNoteColumnIntent(column_id=column_id)
        self._controller.dispatch(intent)
        self.status_var.set(f"Spalte '{title}' gelöscht")
