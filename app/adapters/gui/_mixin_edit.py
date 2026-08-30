"""Edit-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Bearbeitungsoperationen: Symbol- und Farbpunkt-Umschalten, Schülertisch löschen,
Lehrertisch setzen, Escape-Handler sowie zugehörige Tastatur-Shortcut-Handler.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.adapters.gui.main_window_constants import NAME_EDITING, SPACE_SHORTCUT
from app.core.domain.models_v4 import ParticipationRating
from app.core.intents.color_intents import ToggleColorIntent
from app.core.intents.participation_intents import SetParticipationRatingIntent
from app.core.intents.student_intents import (
    CreateStudentIntent,
    DeleteStudentIntent,
    SetTeacherSeatIntent,
)
from app.core.intents.symbol_intents import (
    RecordDocumentationSymbolIntent,
    ToggleDiagnosticSymbolIntent,
)
from app.core.usecases.v4.color_usecases import is_color_tag_used, set_palette_meaning
from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from bw_libs.ui_contract.hsm import ESCAPE_CLOSE_POPUP, ESCAPE_EXIT_INLINE_EDITOR, ESCAPE_POP_PARENT

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class EditMixin:
    """Mixin: Bearbeitungsoperationen für Schülertische, Symbole, Farbpunkte und Escape (v4)."""

    def _on_symbol_shortcut(self, _event, symbol_name: str | None) -> str | None:
        """Tastatur-Shortcut-Handler für Symbole.

        In der Dokuansicht wirkt jedes Symbol auf die dort gewählte
        Datumsspalte (``_toggle_documentation_symbol``). Im Raster gibt es
        keinen Datums-Wähler: Diagnosesymbole togglen wie bisher am Schüler
        selbst (``_toggle_selected_symbol``), Doku-Symbole (eingebaut wie
        eigen) togglen für das heutige Datum
        (``_toggle_documentation_symbol_today_grid``) — beide Symbolarten
        sind damit im Raster per Kürzel nutzbar, nicht mehr nur Diagnose.
        Wird auch vom Leertaste-Resolver (``_on_space_symbol_shortcut``)
        aufgerufen, der *symbol_name* dynamisch aus dem Katalog auflöst.

        Args:
            _event: Tkinter-Tastaturereignis (für Modifier-Prüfung, sonst unbenutzt).
            symbol_name: Bezeichner des umzuschaltenden Symbols, oder ``None``
                wenn kein Katalogeintrag dieses Kürzel trägt (dann No-Op).
        """
        if symbol_name is None:
            return None
        if not self._shortcut_scope_allows("docs") and not self._shortcut_scope_allows("grid"):
            return None
        if _event.state & 0x0004 or _event.state & 0x0008:
            return None
        if not self.editor_view.winfo_ismapped():
            return None
        if not self.current_plan or not self.current_plan_path:
            return None
        if self._editor_surface == "docs":
            self._toggle_documentation_symbol(symbol_name)
            return "break"
        if self._editor_surface != "grid":
            return None
        if symbol_name in self.diagnostic_symbol_catalog:
            self._toggle_selected_symbol(symbol_name)
            return "break"
        if symbol_name in self._documentation_only_symbols:
            self._toggle_documentation_symbol_today_grid(symbol_name)
            return "break"
        return None

    def _on_color_shortcut(self, event, color_key: str) -> str | None:
        """Tastatur-Shortcut-Handler für Farbpunkte im Raster.

        Args:
            event: Tkinter-Tastaturereignis (für Modifier-Prüfung, sonst unbenutzt).
            color_key: Schlüssel des umzuschaltenden Farbpunkts.
        """
        if not self._shortcut_scope_allows("grid"):
            return None
        if event.state & 0x0004 or event.state & 0x0008:
            return None
        if not self.editor_view.winfo_ismapped():
            return None
        if self._editor_surface != "grid":
            return None
        if not self.current_plan or not self.current_plan_path:
            return None
        self._toggle_selected_color(color_key)
        return "break"

    def _toggle_selected_symbol(self, symbol: str) -> None:
        """Schaltet ein diagnostisches Symbol für den aktuell ausgewählten Schüler um (v4).

        Args:
            symbol: Bezeichner des diagnostischen Symbols.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            self.status_var.set("Symbole nur bei Einzelauswahl")
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            self.status_var.set("Symbol nur für Schülertische")
            return
        if symbol not in self.diagnostic_symbol_catalog:
            self.status_var.set("Dieses Symbol ist nur fuer die Dokumentation verfuegbar")
            return
        self._controller.dispatch(ToggleDiagnosticSymbolIntent(student_id=student.student_id, symbol=symbol))
        # Sync doc entry: get new strength after toggle
        updated_student = self._controller.state.current_plan.student_at(x, y) if self._controller.state.current_plan else None
        new_strength = 0
        if updated_student is not None:
            new_strength = int(updated_student.diagnostic.symbols.get(symbol, 0))
        self._controller.dispatch(
            RecordDocumentationSymbolIntent(
                student_id=student.student_id,
                date=self._today_doc_date(),
                symbol=symbol,
                strength=new_strength,
            )
        )

    def _on_space_symbol_shortcut(self, event) -> str | None:
        """Tastatur-Shortcut-Handler (Leertaste): löst das Katalogsymbol dynamisch auf und delegiert.

        Kein eigener Guard, keine eigene Datums- oder Oberflächenlogik mehr —
        welches Symbol (falls überhaupt eines) die Leertaste bedient, ergibt
        sich rein aus dem Katalog (``config/symbols.json``, Kürzel
        ``SPACE_SHORTCUT``), genau wie bei jedem anderen Kürzel. Die gesamte
        Verzweigung (Textfeld-Schutz, Oberfläche, Diagnose- vs. Doku-Symbol)
        läuft in ``_on_symbol_shortcut()``.

        Args:
            event: Tkinter-Tastaturereignis, unverändert an ``_on_symbol_shortcut`` gereicht.
        """
        return self._on_symbol_shortcut(event, self._shortcut_to_symbol.get(SPACE_SHORTCUT))

    def _toggle_documentation_symbol_today_grid(self, symbol: str) -> None:
        """Schaltet ein Doku-Symbol für den ausgewählten Schülertisch im Raster für heute um (v4).

        Raster-Pendant zu ``_toggle_documentation_symbol()`` (Dokuansicht):
        das Raster hat keinen Datums-Wähler, daher wirkt der Toggle immer auf
        das heutige Datum. Nutzt denselben Toggle-Kern
        (``_toggle_documentation_symbol_for_student``, ``_mixin_docs_edit.py``)
        wie die Dokuansicht — kein zweiter Toggle-Pfad.

        Args:
            symbol: Bezeichner des umzuschaltenden Doku-Symbols (eingebauter
                Meaning-Text oder eigene Symbol-ID).
        """
        if not self.selection.is_single():
            self.status_var.set("Symbole nur bei Einzelauswahl")
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            self.status_var.set("Symbol nur für Schülertische")
            return
        self._toggle_documentation_symbol_for_student(student, symbol, self._today_doc_date())

    def _set_participation_rating_today_grid(self, rating: ParticipationRating) -> None:
        """Setzt/löscht die Mitarbeit-Bewertung heute für den ausgewählten Schülertisch im Raster (v4).

        Args:
            rating: Zu setzende Bewertung ("+"/"o"/"-").
        """
        if not self.selection.is_single():
            self.status_var.set("Mitarbeit-Bewertung nur bei Einzelauswahl")
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            self.status_var.set("Mitarbeit-Bewertung nur fuer Schuelertische")
            return
        self._controller.dispatch(SetParticipationRatingIntent(
            student_id=student.student_id, date=self._today_doc_date(), rating=rating))

    def _set_participation_rating_today_docs(self, rating: ParticipationRating) -> None:
        """Setzt/löscht die Mitarbeit-Bewertung heute für den ausgewählten Schüler in der Dokutabelle.

        Args:
            rating: Zu setzende Bewertung ("+"/"o"/"-").
        """
        if not self._doc_student_coords:
            return
        idx = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        x, y = self._doc_student_coords[idx]
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            return
        self._controller.dispatch(SetParticipationRatingIntent(
            student_id=student.student_id, date=self._today_doc_date(), rating=rating))
        self._refresh_documentation_table()

    def _on_participation_rating_shortcut(self, event, rating: ParticipationRating) -> str | None:
        """Tastatur-Shortcut-Handler (+/-/0): Mitarbeit-Bewertung heute setzen/löschen.

        Args:
            event: Tkinter-Tastaturereignis (für Modifier-Prüfung, sonst unbenutzt).
            rating: Zu setzende Bewertung ("+"/"o"/"-").
        """
        if not self._shortcut_scope_allows("docs") and not self._shortcut_scope_allows("grid"):
            return None
        if event.state & 0x0004 or event.state & 0x0008:
            return None
        if not self.editor_view.winfo_ismapped():
            return None
        if not self.current_plan or not self.current_plan_path:
            return None
        if self._editor_surface == "grid":
            self._set_participation_rating_today_grid(rating)
        elif self._editor_surface == "docs":
            self._set_participation_rating_today_docs(rating)
        else:
            return None
        return "break"

    def add_symbol_to_selected_desk_dialog(self) -> None:
        """Öffnet einen Dialog zur Symbolauswahl für den markierten Schülerplatz (v4)."""
        if not self.current_plan:
            return

        if not self.selection.is_single():
            self.status_var.set("Symbole nur bei Einzelauswahl")
            return

        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            self.status_var.set("Symbol nur für Schülertische")
            return

        dialog = self._create_overlay_dialog("Symbol hinzufügen", "350x360")

        tui.Label(dialog, text="Symbol auswählen").pack(anchor="w", padx=12, pady=(12, 6))

        listbox = ui.Listbox(dialog, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        listbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        for symbol in self.diagnostic_symbol_catalog:
            listbox.insert(ui.END, symbol)
        if self.diagnostic_symbol_catalog:
            listbox.selection_set(0)
        self._focus_overlay_widget(dialog, listbox)

        def apply_choice() -> None:
            selected = listbox.curselection()
            if not selected:
                return
            symbol = self.diagnostic_symbol_catalog[int(selected[0])]
            self._toggle_selected_symbol(symbol)
            dialog.destroy()

        dialog.bind("<Return>", lambda _e: apply_choice())

        button_row = tui.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))
        apply_button = tui.Button(button_row, text="Übernehmen", command=apply_choice)
        apply_button.pack(side="right")
        self._attach_hover_help(apply_button, label="Ausgewaehltes Symbol uebernehmen", shortcut="Enter")

    def _toggle_selected_color(self, color_key: str) -> None:
        """Schaltet einen Farbpunkt für den aktuell ausgewählten Schüler um (v4).

        Args:
            color_key: Schlüssel des umzuschaltenden Farbpunkts.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            self.status_var.set("Farbpunkte nur bei Einzelauswahl")
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            self.status_var.set("Farbpunkte nur fuer Schuelertische")
            return
        currently_active = color_key in student.diagnostic.color_tags
        requires_meaning = (not currently_active) and (not is_color_tag_used(self.current_plan, color_key))
        color_label, _hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
        if requires_meaning:
            meaning = simpledialog.askstring(
                "Bedeutung fuer Farbe", f"Was bedeutet {color_label} in diesem Plan?", parent=self
            )
            if meaning is None:
                self.status_var.set("Farbpunkt abgebrochen")
                self.canvas.focus_set()
                return
            clean = meaning.strip()
            if not clean:
                self.status_var.set("Bedeutung darf nicht leer sein")
                self.canvas.focus_set()
                return
            # Set palette meaning on the current plan (direct v4 usecase call), then save via toggle
            updated_plan = set_palette_meaning(self.current_plan, color_key, clean)
            self._replace_current_plan(updated_plan)
        self._controller.dispatch(ToggleColorIntent(student_id=student.student_id, color_key=color_key))
        self.canvas.focus_set()

    def delete_selected_desk(self) -> None:
        """Löscht alle Schüler in der aktuellen Auswahl (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return
        targets = self.selection.cells()
        ts = self.current_plan.classroom.teacher_seat
        has_teacher = any(ts.x == x and ts.y == y for x, y in targets)
        if has_teacher:
            self.status_var.set("Lehrertisch kann nicht geloescht werden")
        for x, y in targets:
            student = self.current_plan.student_at(x, y)
            if student is not None:
                self._controller.dispatch(DeleteStudentIntent(student_id=student.student_id))
        self.canvas.focus_set()
        self._set_selection_single(*self.selection.anchor_cell())

    def set_selected_as_teacher_desk(self) -> None:
        """Verschiebt den Lehrertisch auf die aktuell ausgewählte Zelle (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return
        x, y = self.selected_cell
        # Pre-check out-of-bounds using the usecase result
        from app.core.usecases.v4.student_usecases import move_teacher_seat
        moved_plan = move_teacher_seat(self.current_plan, x, y)
        out_of_bounds = self._count_out_of_bounds_desks(moved_plan)
        if out_of_bounds > 0:
            proceed = messagebox.askyesno(
                "Warnung",
                f"Nach dem Verschieben des Lehrertischs waeren {out_of_bounds} Schuelertische ausserhalb des aktuellen Canvas-Bereichs (+/-{self.canvas_radius}) und damit unsichtbar. Trotzdem fortfahren?",
                parent=self,
            )
            if not proceed:
                return
        self._controller.dispatch(SetTeacherSeatIntent(x=x, y=y))
        self.canvas.focus_set()
        self._set_selection_single(0, 0)
        self.center_on_cell(0, 0)

    def handle_escape(self) -> None:
        """Verarbeitet die Escape-Taste kontextabhängig via HSM-Kontrakt.

        Ein aufgedecktes Tischdetails-Panel zählt wie ein Popup (schließt
        auf das erste Escape), aber erst nachdem eine laufende
        Namensbearbeitung beendet wurde — sonst würde "Popup schließen"
        Vorrang vor "Inline-Editor verlassen" bekommen und die Details
        würden übersprungen, obwohl der Nutzer nur den Namenseditor
        verlassen wollte.
        """
        self._sync_popup_sessions_from_windows()
        has_inline_editor = self.interaction_mode == NAME_EDITING
        details_revealed = self._desk_detail_state is not None
        has_popup = self._popup_registry.has_active_popup() or (details_revealed and not has_inline_editor)
        has_parent_state = self.editor_view.winfo_ismapped()
        action = self._hsm_contract.resolve_escape_action(
            has_popup=has_popup, has_inline_editor=has_inline_editor, has_parent_state=has_parent_state
        )
        if action == ESCAPE_CLOSE_POPUP:
            active_popup = self._popup_registry.active_popup()
            if active_popup is not None:
                popup_id = active_popup.popup_id
                for child in self.winfo_children():
                    if not isinstance(child, ui.Toplevel):
                        continue
                    if str(child) != popup_id:
                        continue
                    self._destroy_tracked_dialog(child)
                    return
                self._popup_registry.close_popup(popup_id)
                self._tracked_popup_ids.discard(popup_id)
                return
            self._hide_details()
            return
        if action == ESCAPE_EXIT_INLINE_EDITOR:
            self.exit_name_edit_mode()
            return
        if action == ESCAPE_POP_PARENT:
            self._return_to_plan_list()
            return
        self._ensure_list_selection(preferred_path=self.current_plan_path)
        self.plan_listbox.focus_set()
