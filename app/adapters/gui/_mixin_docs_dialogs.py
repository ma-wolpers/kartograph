"""Docs-Dialog-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Dialoge für Datum umbenennen, Notenspalte hinzufügen, Notenerfassung,
Symbol-Auswahl und Gewichtungskonfiguration bereit.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.core.domain.effective_symbol import resolve_symbol_display
from app.core.domain.models_v4 import GradeColumn
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    UpdateGradeWeightingIntent,
)
from app.core.intents.session_intents import AddSessionIntent, DeleteSessionIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.core.usecases.v4.session_usecases import rename_session_date
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class DocsDialogsMixin:
    """Mixin: Dokumentations-Dialoge (Datum, Noten, Symbole, Gewichtung) (v4)."""

    def rename_selected_documentation_date_dialog(self) -> None:
        """Öffnet einen Dialog zum Umbenennen des aktuell ausgewählten Dokumentations-Datums (v4).

        Es gibt kein eigenes Intent für das Umbenennen eines Session-Datums, daher
        wird der v4-Usecase direkt aufgerufen und das Ergebnis per
        ``replace_plan_in_state`` in den AppState übernommen (kein History-Eintrag,
        analog zur Farbpaletten-Bedeutung vor einem Toggle). Das anschliessende
        Sicherstellen der Session für das neue Datum läuft dagegen über
        ``AddSessionIntent``/``handle_add_session`` — dafür existiert bereits ein
        Intent, daher kein direkter Usecase-Aufruf (s. ``ensure_session`` in
        ``session_usecases.py``).
        """
        if not self.current_plan or not self.current_plan_path or not self._doc_dates:
            return
        old_date = self._doc_dates[self._doc_selected_date_index]
        new_date = simpledialog.askstring("Datum umbenennen", "Neues Datum (YYYY-MM-DD):", parent=self, initialvalue=old_date)
        if new_date is None:
            return
        renamed_plan = rename_session_date(self.current_plan, old_date, new_date)
        self._replace_current_plan(renamed_plan)
        self._controller.dispatch(AddSessionIntent(date=new_date))
        self.status_var.set("Dokudatum umbenannt")
        self._refresh_documentation_table()

    def delete_selected_documentation_date_dialog(self) -> None:
        """Löscht den aktuell ausgewählten Dokumentations-Termin (Session) nach Bestätigung (v4).

        Schließt die in Architekturplan v2, Abschnitt 13.2 (T7) dokumentierte
        Lücke: ``DeleteSessionIntent``/``handle_delete_session`` waren bereits
        vollständig implementiert (inkl. Entfernen aller Symbol-/Noten-Einträge
        und Notizen dieses Datums aus ``plan.documentation.sessions``), hatten
        aber bislang keinen Auslöser in der GUI — es gab nur "Datum umbenennen"
        (``rename_selected_documentation_date_dialog``), keinen Löschen-Pfad.

        Anders als ``rename_selected_documentation_date_dialog`` (das den
        v4-Usecase direkt aufruft, weil es dafür kein eigenes Intent gibt, s.
        dortiger Docstring) geht diese Methode über den regulären
        Intent/Handler-Pfad (``self._controller.dispatch(DeleteSessionIntent)``),
        da Intent und Handler hierfür bereits existieren. Folgt damit demselben
        Bestätigungs-Muster wie ``_confirm_and_delete_grade_column`` (T6):
        erst eine explizite Ja/Nein-Sicherheitsabfrage, da der Vorgang
        unwiderruflich ist, dann Dispatch.

        Ermittelt das Zieldatum identisch zu
        ``rename_selected_documentation_date_dialog`` über
        ``self._doc_dates[self._doc_selected_date_index]`` (die aktuell in der
        linken Dokumentationstabelle markierte Datumsspalte). Bricht
        folgenlos ab, wenn kein Plan geladen ist, der Plan noch nicht
        gespeichert wurde, keine Datumsspalten existieren, oder die
        Sicherheitsabfrage verneint wird.

        Das heutige Datum erscheint in ``_doc_dates`` immer als virtuelle
        Spalte (s. ``_refresh_documentation_table``), auch ohne gespeicherte
        Session — das Löschen einer (noch) inhaltsleeren heutigen Spalte ist
        daher ein No-Op auf Modellebene, aber unschädlich.

        Returns:
            None. Bei Erfolg wird der Plan über den Controller persistiert,
            die Dokumentationstabelle neu aufgebaut (sowohl implizit über
            ``apply_state`` nach dem Dispatch als auch explizit hier, analog
            zu ``_confirm_and_delete_grade_column``) und eine Statusmeldung
            gesetzt.
        """
        if not self.current_plan or not self.current_plan_path or not self._doc_dates:
            return
        target_date = self._doc_dates[self._doc_selected_date_index]
        confirmed = messagebox.askyesno(
            "Dokumentationstermin löschen",
            f"Datum '{target_date}' inkl. aller darin erfassten Symbole, Noten und "
            "Notizen unwiderruflich löschen?",
            parent=self,
        )
        if not confirmed:
            return
        self._controller.dispatch(DeleteSessionIntent(date=target_date))
        self.status_var.set(f"Dokumentationstermin '{target_date}' gelöscht")
        self._refresh_documentation_table()

    def add_grade_column_dialog(self) -> None:
        """Öffnet einen Dialog zum Hinzufügen einer neuen Notenspalte (schriftlich/sonstig) (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return
        category = simpledialog.askstring("Notenspalte", "Typ eingeben: schriftlich oder sonstig", parent=self)
        if category is None:
            return
        clean_category = category.strip().lower()
        if clean_category not in {"schriftlich", "sonstig"}:
            messagebox.showerror("Ungueltige Eingabe", "Typ muss 'schriftlich' oder 'sonstig' sein.", parent=self)
            return
        title = simpledialog.askstring("Notenspalte", "Kurzer Titel:", parent=self)
        if title is None:
            return
        self._controller.dispatch(AddGradeColumnIntent(category=clean_category, title=title or ""))
        new_column_id = self._controller.state.doc_selected_column_id
        if new_column_id:
            self._select_doc_fixed_column(f"grade_{new_column_id}")
        self._refresh_documentation_table()

    def delete_grade_column_dialog(self) -> None:
        """Löscht eine Notenspalte nach Bestätigung (v4).

        Bestimmt die Zielspalte in derselben Reihenfolge wie
        ``set_selected_documentation_grade_dialog``: zuerst die aktuell
        markierte feste Spalte (``_doc_selected_fixed_column_id``), sonst —
        falls genau eine Notenspalte existiert — diese. Gibt es mehrere
        Notenspalten ohne eindeutige Markierung, öffnet sich eine
        Auswahlliste; die Bestätigung erfolgt erst danach in
        ``_confirm_and_delete_grade_column``. Das Löschen selbst entfernt via
        ``DeleteGradeColumnIntent`` auch alle bereits erfassten Noten dieser
        Spalte aus allen Sessions (s. ``_delete_grade_column`` in
        ``grade_handlers.py``).
        """
        if not self.current_plan or not self.current_plan_path:
            return
        grade_columns = self.current_plan.documentation.grade_columns
        if not grade_columns:
            messagebox.showinfo("Keine Notenspalten", "Es gibt keine Notenspalte zum Löschen.", parent=self)
            return

        column: GradeColumn | None = None
        if self._doc_selected_fixed_column_id and self._doc_selected_fixed_column_id.startswith("grade_"):
            raw_id = self._doc_selected_fixed_column_id[len("grade_"):]
            for item in grade_columns:
                if item.column_id == raw_id:
                    column = item
                    break
        if column is None and len(grade_columns) == 1:
            column = grade_columns[0]

        if column is not None:
            self._confirm_and_delete_grade_column(column)
            return

        self._open_grade_column_picker_dialog(grade_columns)

    def _open_grade_column_picker_dialog(self, grade_columns: list[GradeColumn]) -> None:
        """Öffnet eine Auswahlliste, wenn keine Notenspalte eindeutig vorausgewählt ist.

        Args:
            grade_columns: Alle Notenspalten des aktuellen Plans (mindestens zwei).
        """
        dialog = self._create_overlay_dialog("Notenspalte löschen", "320x320")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(frame, text="Zu löschende Notenspalte auswählen").pack(anchor="w", pady=(0, 6))

        listbox = ui.Listbox(frame, selectmode="browse", exportselection=False)
        listbox.pack(fill="both", expand=True)
        for col in grade_columns:
            listbox.insert(ui.END, f"{col.title} ({col.category})")
        listbox.selection_set(0)
        self._focus_overlay_widget(dialog, listbox)

        def confirm() -> None:
            selected = listbox.curselection()
            if not selected:
                return
            chosen = grade_columns[int(selected[0])]
            dialog.destroy()
            self._confirm_and_delete_grade_column(chosen)

        listbox.bind("<Double-Button-1>", lambda _event: confirm())
        listbox.bind("<Return>", lambda _event: confirm())
        button_row = tui.Frame(frame)
        button_row.pack(fill="x", pady=(8, 0))
        tui.Button(button_row, text="Weiter", command=confirm).pack(side="right")
        tui.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(0, 8))

    def _confirm_and_delete_grade_column(self, column: GradeColumn) -> None:
        """Fragt vor dem Löschen einer Notenspalte explizit nach Bestätigung.

        Löscht bei Zustimmung über ``DeleteGradeColumnIntent`` und baut die
        Dokumentationstabelle neu auf.

        Args:
            column: Die zu löschende Notenspalte.
        """
        confirmed = messagebox.askyesno(
            "Notenspalte löschen",
            f"Notenspalte '{column.title}' inkl. aller darin erfassten Noten unwiderruflich löschen?",
            parent=self,
        )
        if not confirmed:
            return
        self._controller.dispatch(DeleteGradeColumnIntent(column_id=column.column_id))
        self.status_var.set(f"Notenspalte '{column.title}' gelöscht")
        self._refresh_documentation_table()

    def set_selected_documentation_grade_dialog(self, selected_column_id: str | None = None) -> None:
        """Öffnet den Inline-Editor für die ausgewählte Noten-Spalte.

        Args:
            selected_column_id: Wenn angegeben, wird diese Spalte bevorzugt; sonst
                wird die aktuell ausgewählte feste Spalte oder die erste Notenspalte genommen.
        """
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        grade_columns = self.current_plan.documentation.grade_columns
        if not grade_columns:
            messagebox.showinfo("Keine Notenspalten", "Bitte zuerst eine Notenspalte hinzufügen.", parent=self)
            return
        column = None
        if selected_column_id:
            for item in grade_columns:
                if item.column_id == selected_column_id:
                    column = item
                    break
        if column is None:
            if self._doc_selected_fixed_column_id and self._doc_selected_fixed_column_id.startswith("grade_"):
                raw_id = self._doc_selected_fixed_column_id[len("grade_"):]
                for item in grade_columns:
                    if item.column_id == raw_id:
                        column = item
                        break
            if column is None:
                column = grade_columns[0]
        self._select_doc_fixed_column(f"grade_{column.column_id}")
        self._refresh_doc_selection_status()
        self._open_selected_docs_grade_cell_editor()

    def configure_grade_weighting_dialog(self) -> None:
        """Öffnet Dialoge zur Eingabe der Gewichtung für schriftliche und sonstige Noten (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return
        weighting = self.current_plan.documentation.weighting
        written_text = simpledialog.askstring(
            "Gewichtung", "Anteil schriftlich in %:", parent=self, initialvalue=str(weighting.written_percent)
        )
        if written_text is None:
            return
        sonstige_text = simpledialog.askstring(
            "Gewichtung", "Anteil sonstig in %:", parent=self, initialvalue=str(weighting.sonstige_percent)
        )
        if sonstige_text is None:
            return
        try:
            written_percent = int(written_text.strip())
            sonstige_percent = int(sonstige_text.strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "Bitte ganze Prozentzahlen eingeben.", parent=self)
            return
        self._controller.dispatch(
            UpdateGradeWeightingIntent(written_percent=written_percent, sonstige_percent=sonstige_percent)
        )
        self._refresh_documentation_table()

    def set_selected_documentation_symbol_dialog(self) -> None:
        """Öffnet einen Dialog zur Symbolauswahl für die aktuelle Doku-Zelle (v4).

        Zeigt alle konfigurierten Symbole (eingebaut, jede Rolle) UND alle
        eigenen Doku-Symbole des aktuellen Plans als auswählbare Liste mit
        Tastaturkürzel-Hinweisen (eingebaute Symbole zeigen ihr einzelnes
        Tastenzeichen, eigene ihr ``Ctrl+Shift+<Buchstabe>``-Kürzel). Bewusst
        eine ERWEITERTE statt eine ersetzte Liste (``self.symbol_catalog``
        bleibt unverändert Teil davon) — dieser Dialog erlaubt seit jeher auch
        das Setzen diagnostischer Symbole für einen einzelnen Tag, das darf
        durch eigene Doku-Symbole nicht verloren gehen. Unterstützt
        Zifferntasten 1–9 zur Schnellauswahl, Delete/Backspace/0 zum Löschen.
        """
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        all_symbol_keys = self.symbol_catalog + [
            s.key for s in self.effective_documentation_symbols if s.is_custom
        ]
        if not all_symbol_keys:
            messagebox.showinfo("Keine Symbole", "Es sind keine Symbole konfiguriert.", parent=self)
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]
        student = self.current_plan.student_at(x, y)
        preferred_symbol: str | None = None
        if student is not None and student.is_named():
            session = self.current_plan.documentation.session_for_date(date_key)
            entry = session.entry_for(student.student_id) if session else None
            if entry and entry.symbols:
                non_zero = [s for s in all_symbol_keys if int(entry.symbols.get(s, 0)) > 0]
                if non_zero:
                    preferred_symbol = non_zero[0]

        dialog = self._create_overlay_dialog("Symbol setzen", "360x420")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(frame, text="Symbol auswählen").pack(anchor="w", pady=(0, 6))
        tui.Label(frame, text="Tastaturhilfe im Hover", foreground="#666666").pack(anchor="w", pady=(0, 6))

        symbol_listbox = ui.Listbox(frame, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        symbol_listbox.pack(fill="both", expand=True)
        self._attach_hover_help(
            symbol_listbox,
            label="Symbolauswahl per Tastatur",
            shortcut="1-9 waehlt, 0 loescht, Enter uebernimmt, Entf/Backspace loescht, Esc schliesst",
        )
        for symbol in all_symbol_keys:
            definition = self._symbol_by_meaning.get(symbol)
            if definition is not None:
                shortcut = definition.shortcut.upper() if definition.shortcut else None
            else:
                effective = self._effective_symbol_by_key.get(symbol)
                shortcut = effective.shortcut if effective is not None else None
            suffix = f" [{shortcut}]" if shortcut else ""
            if definition is not None:
                glyph, label = definition.glyph, symbol
            else:
                glyph, label = resolve_symbol_display(symbol, self.effective_documentation_symbols)
            symbol_listbox.insert(ui.END, f"{glyph} {label}{suffix}")

        if all_symbol_keys:
            sel_idx = max(0, min(self._docs_symbol_dialog_last_index, len(all_symbol_keys) - 1))
            if preferred_symbol in all_symbol_keys:
                sel_idx = all_symbol_keys.index(preferred_symbol)
            symbol_listbox.selection_set(sel_idx)
            symbol_listbox.activate(sel_idx)
            symbol_listbox.see(sel_idx)
        self._focus_overlay_widget(dialog, symbol_listbox)

        def apply_symbol() -> None:
            selected = symbol_listbox.curselection()
            if not selected:
                return
            idx = int(selected[0])
            self._docs_symbol_dialog_last_index = idx
            self._toggle_documentation_symbol(all_symbol_keys[idx])
            dialog.destroy()

        def clear_symbol() -> None:
            if not self.current_plan or student is None:
                return
            selected = symbol_listbox.curselection()
            if not selected:
                return
            idx = int(selected[0])
            self._docs_symbol_dialog_last_index = idx
            sym = all_symbol_keys[idx]
            self._controller.dispatch(
                RecordDocumentationSymbolIntent(student_id=student.student_id, date=date_key, symbol=sym, strength=0)
            )
            self.status_var.set(f"Dokumentation '{sym}' geloescht")
            self._refresh_documentation_table()
            dialog.destroy()

        for seq in ("<Delete>", "<BackSpace>", "<0>", "<KP_0>"):
            dialog.bind(seq, lambda _event: clear_symbol())
        symbol_listbox.bind("<Double-Button-1>", lambda _event: apply_symbol())
        symbol_listbox.bind("<Return>", lambda _event: apply_symbol())
        symbol_listbox.bind("<KP_Enter>", lambda _event: apply_symbol())

        def select_by_digit(index: int) -> None:
            if index < 0 or index >= len(all_symbol_keys):
                return
            symbol_listbox.selection_clear(0, ui.END)
            symbol_listbox.selection_set(index)
            symbol_listbox.activate(index)
            symbol_listbox.see(index)

        for digit in range(1, 10):
            dialog.bind(f"<{digit}>", lambda _event, i=digit - 1: select_by_digit(i))
            dialog.bind(f"<KP_{digit}>", lambda _event, i=digit - 1: select_by_digit(i))

        button_row = tui.Frame(frame)
        button_row.pack(fill="x", pady=(8, 0))
        tui.Button(button_row, text="Loeschen", command=clear_symbol).pack(side="left")
        tui.Button(button_row, text="Übernehmen", command=apply_symbol).pack(side="right")
        tui.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(0, 8))
