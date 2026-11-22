"""Docs-Dialog-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Dialoge für Datum hinzufügen/ändern/löschen (eine Datumsabfrage
``_ask_documentation_date``), Notenspalte löschen und Symbol-Auswahl bereit.
Notenspalte anlegen und Gewichtung liegen in ``_mixin_grade_dialogs.py``; welcher
Dialog zu „Spalte hinzufügen/umbenennen/löschen“ gehört, entscheidet
``_mixin_docs_column_actions.py``.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, bind_action, dialog_keys, widget_keys
from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.adapters.gui.main_window_constants import SPACE_SHORTCUT
from app.core.domain.effective_symbol import resolve_symbol_display
from app.core.domain.models_v4 import GradeColumn
from app.core.intents.grade_intents import DeleteGradeColumnIntent
from app.core.domain.note_column_kinds import format_date_value, parse_date_input
from app.core.intents.session_intents import AddSessionIntent, DeleteSessionIntent, RenameSessionIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import KeySpec
from bw_gui.runtime import bind_click, listbox_selection, ui
from bw_gui.runtime import widgets as tui


class DocsDialogsMixin:
    """Mixin: Dokumentations-Dialoge (Datum, Notenspalte löschen, Noten, Symbole) (v4)."""

    def _ask_documentation_date(self, title: str, initial_iso: str) -> str | None:
        """Einzige Datumsabfrage der Datenansicht (hinzufügen, verlegen): TT.MM.JJJJ rein, ISO raus.

        Liest über ``note_column_kinds.parse_date_input`` (dieselbe Regel wie
        Datums-Notizspalten); ein unlesbares Datum meldet der Dialog unter dem Feld.

        Args:
            title: Dialogtitel.
            initial_iso: Vorbelegung als ISO-Datum.

        Returns:
            Das Datum als ``JJJJ-MM-TT`` oder ``None`` bei Abbruch.
        """

        def problem(text: str) -> str | None:
            try:
                parse_date_input(text)
            except ValueError:
                return "Bitte ein Datum wie 03.11.2026 eingeben."
            return None

        raw = simpledialog.askstring(
            title, "Datum (TT.MM.JJJJ):", parent=self, initialvalue=format_date_value(initial_iso), validate=problem
        )
        return None if raw is None else parse_date_input(raw)

    def rename_selected_documentation_date_dialog(self) -> None:
        """Verlegt den ausgewählten Dokumentationstermin auf ein anderes Datum (ein Undo-Schritt).

        Über ``RenameSessionIntent``: Einträge wandern mit, ein vorhandenes
        Zieldatum wird zusammengeführt (``rename_session_date``).
        """
        if not self.current_plan or not self.current_plan_path or not self._doc_dates:
            return
        old_date = self._doc_anchor_date()
        new_date = self._ask_documentation_date("Datum ändern", old_date)
        if new_date is not None and new_date != old_date:
            self._controller.dispatch(RenameSessionIntent(old_date=old_date, new_date=new_date))

    def add_documentation_date_dialog(self) -> None:
        """Legt einen Dokumentationstermin an (vorbelegt: heute) und wählt ihn aus (ein Undo-Schritt)."""
        if not self.current_plan or not self.current_plan_path:
            return
        new_date = self._ask_documentation_date("Datum hinzufügen", self._today_doc_date())
        if new_date is not None:
            self._controller.dispatch(AddSessionIntent(date=new_date))

    def delete_selected_documentation_date_dialog(self) -> None:
        """Löscht den aktuell ausgewählten Dokumentations-Termin (Session) nach Bestätigung (v4).

        Schließt die in Architekturplan v2, Abschnitt 13.2 (T7) dokumentierte
        Lücke: ``DeleteSessionIntent``/``handle_delete_session`` waren bereits
        vollständig implementiert (inkl. Entfernen aller Symbol-Einträge
        und Notizen dieses Datums; Noten hängen nicht am Datum aus ``plan.documentation.sessions``), hatten
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

    def set_selected_documentation_symbol_dialog(self) -> None:
        """Öffnet einen Dialog zur Symbolauswahl für die aktuelle Doku-Zelle (v4).

        Zeigt alle setzbaren Symbole (``offered_symbol_keys``: aktive eingebaute jeder Rolle UND alle
        eigenen Doku-Symbole des aktuellen Plans) als auswählbare Liste mit
        Tastaturkürzel-Hinweisen (eingebaute Symbole zeigen ihr einzelnes
        Tastenzeichen, eigene ihr ``Ctrl+Shift+<Buchstabe>``-Kürzel). Bewusst
        eine ERWEITERTE statt eine ersetzte Liste (die aktiven Katalogsymbole
        bleibt unverändert Teil davon) — dieser Dialog erlaubt seit jeher auch
        das Setzen diagnostischer Symbole für einen einzelnen Tag, das darf
        durch eigene Doku-Symbole nicht verloren gehen. Unterstützt
        Zifferntasten 1–9 zur Schnellauswahl, Delete/Backspace/0 zum Löschen.
        """
        # Ziel beim Öffnen festgelegt: Übernehmen und Löschen wirken auf denselben Eintrag.
        target = self._doc_action_target("Symbole")
        if target is None:
            return
        all_symbol_keys = list(self.offered_symbol_keys)
        if not all_symbol_keys:
            messagebox.showinfo("Keine Symbole", "Es sind keine Symbole konfiguriert.", parent=self)
            return

        preferred_symbol: str | None = None
        session = self.current_plan.documentation.session_for_date(target.date)
        entry = session.entry_for(target.student_id) if session else None
        if entry and entry.symbols:
            non_zero = [s for s in all_symbol_keys if int(entry.symbols.get(s, 0)) > 0]
            if non_zero:
                preferred_symbol = non_zero[0]

        dialog = self._create_overlay_dialog("Symbol setzen", "360x420")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(frame, text="Symbol auswählen").pack(anchor="w", pady=(0, 6))
        tui.Label(frame, text="Tastaturhilfe im Hover", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        symbol_listbox = ui.Listbox(frame, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        symbol_listbox.pack(fill="both", expand=True)
        self._attach_hover_help(
            symbol_listbox,
            # Bedienhinweis als Beschreibung: als ``shortcut`` zerlegte ihn der Tastenformatierer ("1+9 …, enter …").
            label="Symbolauswahl per Tastatur:\n1-9 waehlt, 0 loescht, Enter uebernimmt, Entf/Backspace loescht, Esc schliesst",
        )
        for symbol in all_symbol_keys:
            definition = self._symbol_by_meaning.get(symbol)
            if definition is not None:
                if definition.shortcut == SPACE_SHORTCUT:
                    shortcut = "Leertaste"
                else:
                    shortcut = definition.shortcut.upper() if definition.shortcut else None
            else:
                effective = self._effective_symbol_by_key.get(symbol)
                shortcut = effective.shortcut if effective is not None else None
            suffix = f" [{shortcut}]" if shortcut else ""
            if definition is not None:
                glyph, label = definition.glyph, definition.name
            else:
                glyph, label = resolve_symbol_display(symbol, self.effective_documentation_symbols)
            symbol_listbox.insert(ui.END, f"{glyph} {label}{suffix}")

        if all_symbol_keys:
            sel_idx = max(0, min(self._docs_symbol_dialog_last_index, len(all_symbol_keys) - 1))
            if preferred_symbol in all_symbol_keys:
                sel_idx = all_symbol_keys.index(preferred_symbol)
            listbox_selection.set(symbol_listbox, [sel_idx])
            symbol_listbox.activate(sel_idx)
            symbol_listbox.see(sel_idx)
        self._focus_overlay_widget(dialog, symbol_listbox)

        def apply_symbol() -> None:
            selected = symbol_listbox.curselection()
            if not selected:
                return
            idx = int(selected[0])
            self._docs_symbol_dialog_last_index = idx
            self._toggle_documentation_symbol_at(target, all_symbol_keys[idx])
            dialog.destroy()

        def clear_symbol() -> None:
            selected = symbol_listbox.curselection()
            if not selected:
                return
            idx = int(selected[0])
            self._docs_symbol_dialog_last_index = idx
            sym = all_symbol_keys[idx]
            self._controller.dispatch(
                RecordDocumentationSymbolIntent(student_id=target.student_id, date=target.date, symbol=sym, strength=0)
            )
            self.status_var.set(f"Dokumentation '{sym}' geloescht")
            dialog.destroy()

        keys = dialog_keys(dialog)
        clear_keys = [KeySpec.parse("Delete (tolerate: Shift)"), KeySpec.parse("Backspace (tolerate: Shift)"), KeySpec.char("0")]
        bind_action(keys, clear_keys, clear_symbol, binding_id="symbol.clear", text=False)
        bind_click(symbol_listbox, lambda _event: apply_symbol(), count=2)
        bind_action(widget_keys(symbol_listbox), ENTER, apply_symbol, binding_id="symbol.apply")

        def select_by_digit(index: int) -> None:
            if index < 0 or index >= len(all_symbol_keys):
                return
            listbox_selection.set(symbol_listbox, [index])
            symbol_listbox.activate(index)
            symbol_listbox.see(index)

        # Ziffern 1-9 (Haupttastatur und Ziffernblock) wählen den n-ten Eintrag. Früher
        # stand hier "<1>"..."<9>" -- für Tk sind "<1>"..."<5>" MAUSTASTEN, jeder Klick
        # in den Dialog sprang deshalb auf einen festen Eintrag (Bug 3).
        for digit in range(1, 10):
            bind_action(keys, KeySpec.char(str(digit)), lambda i=digit - 1: select_by_digit(i), binding_id=f"symbol.digit.{digit}", text=False)

        button_row = tui.Frame(frame)
        button_row.pack(fill="x", pady=(8, 0))
        tui.Button(button_row, text="Loeschen", command=clear_symbol).pack(side="left")
        tui.Button(button_row, text="Übernehmen", command=apply_symbol).pack(side="right")
        tui.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(0, 8))
