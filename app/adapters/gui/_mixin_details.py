"""Details-Panel-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt die Refresh-Logik des Details-Panels, die Steuerung der Panel-Sichtbarkeit,
den Namenseditier-Modus sowie die Callbacks für Namensänderungen bereit.
Die Widget-Konstruktion liegt in ``_mixin_details_layout.py``.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import (
    DEFAULT_NAME_SAVE_DELAY,
    DESK_DETAIL_EDITING,
    DESK_DETAIL_REVEALED,
    DeskDetailMode,
    NAME_EDITING,
)
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.student_intents import CreateStudentIntent, RenameStudentIntent, SetNicknameIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class DetailsMixin:
    """Mixin: Details-Panel-Refresh, Sichtbarkeit und Namenseditier-Modus (v4)."""

    def _refresh_details_panel(self) -> None:
        """Aktualisiert den gesamten Inhalt des Details-Panels für die aktuelle Auswahl.

        Liest ausschließlich den vorhandenen ``_desk_detail_state`` und stellt ihn dar --
        mutiert ihn nicht selbst (das übernehmen ausschließlich die State-Funnel-Methoden
        ``_set_desk_detail_state``/``_clear_desk_detail_state``/``_reconcile_desk_detail_state``).
        """
        self._color_marker_buttons = []
        for child in self.symbols_frame.winfo_children():
            child.destroy()
        for child in self.symbol_legend_frame.winfo_children():
            child.destroy()
        for child in self.colors_frame.winfo_children():
            child.destroy()
        for child in self.color_legend_frame.winfo_children():
            child.destroy()

        if not self.current_plan:
            self._set_details_panel_visible(False)
            self._selected_marker_var.set("")
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            self._set_accommodations_field(None)
            self._refresh_tablegroup_overlay()
            return

        x, y = self.selection.active_cell()
        student = self.current_plan.student_at(x, y)
        ts = self.current_plan.classroom.teacher_seat
        is_teacher = ts.x == x and ts.y == y

        min_x, min_y, max_x, max_y = self.selection.bounds()
        if self.selection.is_single():
            self._selected_marker_var.set(f"Markierung: ({x}, {y})")
        else:
            count = (max_x - min_x + 1) * (max_y - min_y + 1)
            self._selected_marker_var.set(f"Bereich: ({min_x}, {min_y}) bis ({max_x}, {max_y}) | {count} Zellen")

        is_student_single = bool(self.selection.is_single() and student is not None and not is_teacher)
        self._reconcile_desk_detail_state(x, y, is_student_single)
        is_revealed = is_student_single and self._desk_detail_state is not None
        self._set_details_panel_visible(is_revealed)

        if not is_student_single:
            self._name_var.set("")
            self._last_name_var.set("")
            self._nickname_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            self.nickname_entry.configure(state="disabled")
            self._set_accommodations_field(None)
            if self.interaction_mode == NAME_EDITING:
                self.canvas.focus_set()
            self._refresh_tablegroup_overlay()
            return

        self._name_var.set(student.first_name_official)
        self._last_name_var.set(student.last_name)
        self._nickname_var.set(student.nickname)
        self.name_entry.configure(state="normal")
        self.last_name_entry.configure(state="normal")
        self.nickname_entry.configure(state="normal")
        self._set_accommodations_field(student)

        symbol_cols = self._details_button_columns()
        self._populate_symbol_buttons(student, symbol_cols)
        active_lines = self._symbol_legend_lines(student.diagnostic.symbols)
        if active_lines:
            for line in active_lines:
                tui.Label(self.symbol_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        color_cols = self._details_button_columns()
        self._populate_color_buttons(student, color_cols)
        self._apply_color_button_theme()
        for line in self._color_legend_lines(self.current_plan, student.diagnostic.color_tags):
            tui.Label(self.color_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        self._refresh_tablegroup_overlay()

    def _populate_symbol_buttons(self, student, symbol_cols: int) -> None:
        """Erstellt die Symbol-Toggle-Buttons im ``symbols_frame``.

        Args:
            student: Schüler, dessen Symbolstatus angezeigt wird.
            symbol_cols: Anzahl der Spalten im Button-Raster.
        """
        tui.Label(self.symbols_frame, text="Symbole").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for symbol in self.diagnostic_symbol_catalog:
            count = int(student.diagnostic.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            caption = f"{icon} {symbol}" if count == 0 else f"{icon} {symbol} x{count}"
            idx = self.diagnostic_symbol_catalog.index(symbol)
            row = 1 + (idx // symbol_cols)
            col = idx % symbol_cols
            button = tui.Button(
                self.symbols_frame,
                text=caption,
                command=lambda s=symbol: self._toggle_selected_symbol(s),
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._attach_hover_help(button, label=f"Symbol {symbol} umschalten", shortcut=shortcut.upper() if shortcut else None)
        for col in range(symbol_cols):
            self.symbols_frame.columnconfigure(col, weight=1)

    def _populate_color_buttons(self, student, color_cols: int) -> None:
        """Erstellt die Farbpunkt-Toggle-Buttons im ``colors_frame``.

        Args:
            student: Schüler, dessen Farbpunkt-Status angezeigt wird.
            color_cols: Anzahl der Spalten im Button-Raster.
        """
        tui.Label(self.colors_frame, text="Farbpunkte").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for key, color_key, label, hex_color in self.color_palette:
            active = color_key in student.diagnostic.color_tags
            caption = label if not active else f"{label}*"
            idx = int(key) - 1
            row = 1 + (idx // color_cols)
            col = idx % color_cols
            button = ui.Button(
                self.colors_frame,
                text=caption,
                command=lambda ck=color_key: self._toggle_selected_color(ck),
                fg=hex_color,
                relief="sunken" if active else "raised",
                padx=6,
                pady=2,
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._color_marker_buttons.append(button)
            self._attach_hover_help(button, label=f"Farbpunkt {label} umschalten", shortcut=key)
        for col in range(color_cols):
            self.colors_frame.columnconfigure(col, weight=1)

    def _set_details_panel_visible(self, visible: bool) -> None:
        """Blendet das ``details_frame`` ein oder aus.

        Args:
            visible: ``True`` blendet das Panel ein, ``False`` blendet es aus.
        """
        fill_mode = "both" if self.details_overlay_position in {"left", "right"} else "x"
        if visible and not self._details_panel_visible:
            self.details_frame.pack(fill=fill_mode, padx=12, pady=(4, 12))
            self._details_panel_visible = True
            return
        if not visible and self._details_panel_visible:
            self.details_frame.pack_forget()
            self._details_panel_visible = False

    def _set_desk_detail_state(self, x: int, y: int, mode: DeskDetailMode) -> None:
        """Bringt die Tischdetails-UI für Zelle (x, y) in den Zustand *mode*.

        Kein bloßer Feld-Setter: hält Detail-Zustand, Panel-Darstellung und (bei
        EDITING) Tk-Fokus synchron. Reihenfolge bewusst so: Zustand setzen -> rendern
        -> Feld ist sichtbar/aktiv -> erst dann fokussieren -- damit der historische
        Bug "Fokus auf unsichtbarem Panel" strukturell nicht mehr durch einen
        einzelnen Aufrufer reproduzierbar ist. EDITING ist dabei der semantische
        Quellzustand der Anwendung; der echte Tk-Fokus auf ``name_entry`` ist nur die
        technische Konsequenz davon, nicht umgekehrt.
        """
        self._desk_detail_state = (x, y, mode)
        self._refresh_details_panel()
        if mode == DESK_DETAIL_EDITING and self.name_entry.instate(["!disabled"]):
            self.name_entry.focus_set()
            self.name_entry.selection_clear()
            self.name_entry.icursor(ui.END)

    def _clear_desk_detail_state(self) -> None:
        """Blendet aufgedeckte/editierte Tischdetails wieder aus (HIDDEN).

        Holt den Tk-Fokus zurück zum Canvas (analog zu ``exit_name_edit_mode()``),
        falls der Editor noch sichtbar ist -- sonst bleibt der Fokus z. B. auf
        dem jetzt unsichtbaren Nachteilsausgleiche-Feld hängen, das keine eigene
        Escape-Bindung hat und den globalen Handler stumm blockiert (Pfeiltasten
        und Enter reagieren dann nicht mehr, da sie Canvas-Fokus voraussetzen).
        """
        if self._desk_detail_state is None:
            return
        self._desk_detail_state = None
        self._refresh_details_panel()
        if self.editor_view.winfo_ismapped():
            self.canvas.focus_set()

    def _reconcile_desk_detail_state(self, x: int, y: int, is_student_single: bool) -> None:
        """Verwirft einen veralteten Detail-Zustand (Zellwechsel, Mehrfachauswahl oder
        Zelle nicht mehr einzeln von einem benannten Schüler belegt).

        Teil des State-Funnels, NICHT des Renderers: wird von ``_refresh_details_panel()``
        einmalig VOR dem eigentlichen Rendern aufgerufen und ruft selbst kein
        ``_refresh_details_panel()`` auf (keine Rekursion) -- der anschließende Refresh
        passiert im Aufrufer.
        """
        if self._desk_detail_state is None:
            return
        if not is_student_single or self._desk_detail_state[:2] != (x, y):
            self._desk_detail_state = None

    def _downgrade_desk_detail_editing_to_revealed(self) -> bool:
        """Fällt von EDITING auf REVEALED für dieselbe Zelle zurück, falls aktuell
        EDITING. Idempotent; gibt zurück, ob tatsächlich heruntergestuft wurde."""
        if self._desk_detail_state is None or self._desk_detail_state[2] != DESK_DETAIL_EDITING:
            return False
        x, y, _mode = self._desk_detail_state
        self._set_desk_detail_state(x, y, DESK_DETAIL_REVEALED)
        return True

    def _reveal_details(self, x: int, y: int) -> None:
        """Deckt die Tischdetails für Zelle (x, y) explizit auf, lesend (Enter).

        Args:
            x: Raster-x-Koordinate der Zelle.
            y: Raster-y-Koordinate der Zelle.
        """
        self._set_desk_detail_state(x, y, DESK_DETAIL_REVEALED)

    def _hide_details(self) -> None:
        """Blendet aufgedeckte Tischdetails wieder aus, falls welche offen sind (Escape / Verlassen)."""
        self._clear_desk_detail_state()

    def _confirm_selected_desk(self) -> None:
        """1. Enter zeigt die Tischdetails lesend; erneutes Enter auf derselben Zelle startet die Namensbearbeitung.

        Bei einem neu angelegten (bisher leeren) Tisch gibt es nichts zu lesen, daher
        startet dort bereits das erste Enter direkt die Namensbearbeitung.
        """
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()
            self.redraw_grid()
            self._refresh_details_panel()

        x, y = self.selected_cell
        ts = self.current_plan.classroom.teacher_seat
        if ts.x == x and ts.y == y:
            self.status_var.set("Lehrertisch ist nicht editierbar")
            return

        details_are_open_for_cell = self._desk_detail_state is not None and self._desk_detail_state[:2] == (x, y)
        is_new_desk = self.current_plan.student_at(x, y) is None
        if details_are_open_for_cell or is_new_desk:
            self.enter_name_edit_mode()
            return
        self._reveal_details(x, y)

    def enter_name_edit_mode(self) -> None:
        """Aktiviert den Namenseditier-Modus (semantischer Zustand EDITING) für den
        aktuell ausgewählten Schüler; legt ihn bei Bedarf an. Der Tk-Fokus auf
        ``name_entry`` folgt aus diesem Zustandsübergang (siehe ``_set_desk_detail_state``),
        nicht umgekehrt."""
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()
            self.redraw_grid()
            self._refresh_details_panel()

        x, y = self.selected_cell
        ts = self.current_plan.classroom.teacher_seat
        if ts.x == x and ts.y == y:
            self.status_var.set("Lehrertisch ist nicht editierbar")
            self.canvas.focus_set()
            return

        student = self.current_plan.student_at(x, y)
        if not student:
            self._controller.dispatch(CreateStudentIntent(x=x, y=y))
            self.redraw_grid()

        # Re-read from updated state
        student = self.current_plan.student_at(x, y)
        if not student:
            self.canvas.focus_set()
            return

        self._set_desk_detail_state(x, y, DESK_DETAIL_EDITING)

    def exit_name_edit_mode(self) -> None:
        """Beendet den Namenseditier-Modus: speichert ausstehende Änderungen sofort und
        stuft den Detail-Zustand (falls EDITING) bedingungslos auf REVEALED zurück --
        unabhängig davon, ob der Editor gerade sichtbar ist, damit nie ein stale
        EDITING-Zustand zurückbleibt. Fokus geht nur zum Canvas, wenn der Editor
        tatsächlich sichtbar ist."""
        self._flush_pending_name_save()
        self._downgrade_desk_detail_editing_to_revealed()
        if not self.editor_view.winfo_ismapped():
            return
        self.canvas.focus_set()

    def _on_name_field_focus_out(self) -> None:
        """FocusOut auf Vorname-/Nachname-/Spitzname-Feld: speichert ausstehende
        Änderungen sofort und stuft EDITING auf REVEALED zurück, falls der Fokus das
        (wiederverwendete) Eingabefeld verlassen hat -- ohne selbst den Fokus zu bewegen.
        Generische Absicherung für Fokusverlust, der nicht über ``exit_name_edit_mode()``
        läuft (Klick auf Farbpunkt/Button, andere/dieselbe Tischzelle, Tab, Planliste, ...).
        Darf mehrfach bzw. zusammen mit ``exit_name_edit_mode()`` feuern, ohne
        inkonsistenten Zustand zu erzeugen (beide Downgrade-Pfade sind idempotent)."""
        self._flush_pending_name_save()
        self._downgrade_desk_detail_editing_to_revealed()

    def confirm_selected_cell(self) -> None:
        """Bestätigt die ausgewählte Zelle: kollabiert Auswahl und legt ggf. einen Schüler an."""
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()

        x, y = self.selected_cell
        self._controller.dispatch(CreateStudentIntent(x=x, y=y))

    def _schedule_name_save(self) -> None:
        """Callback für Tastatureingabe in Vorname-/Nachname-/Spitzname-Feld.

        Merkt sich die aktuell eingegebenen Werte sofort (unabhängig davon, ob spätere
        Auswahlwechsel die Eingabefelder wieder leeren) und plant eine debounced
        Speicherung: gespeichert wird erst, wenn `name_save_delay` Sekunden lang keine
        weitere Eingabe kam. ``exit_name_edit_mode`` bzw. FocusOut auf den Feldern lösen
        eine sofortige Speicherung aus, sodass beim Verlassen nichts verloren geht.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return

        if self._pending_name_save is not None and self._pending_name_save["student_id"] != student.student_id:
            self._flush_pending_name_save()

        self._pending_name_save = {
            "student_id": student.student_id,
            "first_name": self._name_var.get(),
            "last_name": self._last_name_var.get(),
            "nickname": self._nickname_var.get(),
        }

        if self._name_save_after_id is not None:
            try:
                self.after_cancel(self._name_save_after_id)
            except Exception:
                pass
            self._name_save_after_id = None

        delay_ms = int(getattr(self, "name_save_delay", DEFAULT_NAME_SAVE_DELAY) * 1000)
        if delay_ms <= 0:
            self._flush_pending_name_save()
            return
        self._name_save_after_id = self.after(delay_ms, self._flush_pending_name_save)

    def _flush_pending_name_save(self) -> None:
        """Speichert eine ausstehende Namens-/Spitznamenänderung sofort.

        Wird vom debounce-Timer, von ``exit_name_edit_mode`` (Escape/Return/Auswahlwechsel)
        sowie von FocusOut auf den Namensfeldern aufgerufen. Nutzt die bei der Eingabe
        gemerkten Werte statt der aktuellen Feldinhalte, damit ein zwischenzeitlich vom
        Auswahlwechsel geleertes Eingabefeld keine Daten verwerfen kann.
        """
        if self._name_save_after_id is not None:
            try:
                self.after_cancel(self._name_save_after_id)
            except Exception:
                pass
            self._name_save_after_id = None
        pending = self._pending_name_save
        self._pending_name_save = None
        if pending is None:
            return
        if not self.current_plan or not self.current_plan_path:
            return
        student = self.current_plan.student_by_id(pending["student_id"])
        if not student:
            return
        if student.first_name_official != pending["first_name"] or student.last_name != pending["last_name"]:
            self._controller.dispatch(
                RenameStudentIntent(
                    student_id=pending["student_id"],
                    first_name=pending["first_name"],
                    last_name=pending["last_name"],
                )
            )
        if student.nickname != pending["nickname"]:
            self._controller.dispatch(
                SetNicknameIntent(student_id=pending["student_id"], nickname=pending["nickname"])
            )

    def _set_accommodations_field(self, student) -> None:
        """Befüllt das Nachteilsausgleiche-Textfeld oder deaktiviert es bei *student* = None.

        Args:
            student: Anzuzeigender Schüler, oder ``None`` um das Feld zu leeren und zu sperren.
        """
        self.accommodations_field.text.configure(state="normal")
        self.accommodations_field.set("\n".join(student.diagnostic.accommodations) if student else "")
        if student is None:
            self.accommodations_field.text.configure(state="disabled")

    def _on_accommodations_changed(self) -> None:
        """Callback für FocusOut im Nachteilsausgleiche-Feld: speichert die Zeilenliste."""
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return
        lines = self.accommodations_field.get().splitlines()
        self._controller.dispatch(
            SetAccommodationsIntent(student_id=student.student_id, accommodations=lines)
        )
