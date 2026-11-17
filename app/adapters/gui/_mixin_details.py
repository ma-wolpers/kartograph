"""Details-Panel-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt die Refresh-Logik des Details-Panels, die Steuerung der Panel-Sichtbarkeit,
den Namenseditier-Modus sowie die Callbacks für Namensänderungen bereit.
Die Widget-Konstruktion liegt in ``_mixin_details_layout.py``.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import (
    DESK_DETAIL_EDITING,
    DESK_DETAIL_REVEALED,
    DeskDetailMode,
    NAME_EDITING,
)
from app.core.domain.permanent_absence import accepts_notes, is_permanently_absent
from app.core.domain.student_id import StudentId
from app.core.domain.student_naming import normalize_name_part
from app.core.domain.student_notes import normalize_note_lines
from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.student_intents import CreateStudentIntent, RenameStudentIntent, SetNicknameIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import reset_text_modified, ui


class DetailsMixin:
    """Mixin: Details-Panel-Refresh, Sichtbarkeit und Namenseditier-Modus (v4)."""

    def _refresh_details_panel(self) -> None:
        """Aktualisiert den gesamten Inhalt des Details-Panels für die aktuelle Auswahl.

        Ruft ``apply_state`` nur bei geändertem Inhalt oder geänderter Auswahl auf.
        Liest ausschließlich den vorhandenen ``_desk_detail_state`` und stellt ihn dar --
        mutiert ihn nicht selbst (das übernehmen ausschließlich die State-Funnel-Methoden
        ``_set_desk_detail_state``/``_clear_desk_detail_state``/``_reconcile_desk_detail_state``).
        """
        if not self.current_plan:
            self._set_details_panel_visible(False)
            self._selected_marker_var.set("")
            self._load_detail_fields(None)
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
            self._load_detail_fields(None)
            if self.interaction_mode == NAME_EDITING:
                self.canvas.focus_set()
            self._refresh_tablegroup_overlay()
            return

        self._load_detail_fields(student)

        # Knöpfe bestehen dauerhaft (Neuaufbau nur bei geänderter Menge, s. DetailsButtonsMixin).
        columns = self._details_button_columns()
        self._ensure_detail_buttons(columns, columns)
        self._update_detail_buttons(student)
        self._set_legend_lines(self.symbol_legend_frame, self._symbol_legend_lines(student.diagnostic.symbols))
        self._set_legend_lines(self.color_legend_frame, self._color_legend_lines(self.current_plan, student.diagnostic.color_tags))

        self._refresh_tablegroup_overlay()

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
        dem jetzt unsichtbaren Notizfeld hängen, das keine eigene
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
        """Passt einen veralteten Detail-Zustand an einen Zellwechsel an.

        Teil des State-Funnels, NICHT des Renderers: wird von ``_refresh_details_panel()``
        einmalig VOR dem eigentlichen Rendern aufgerufen und ruft selbst kein
        ``_refresh_details_panel()`` auf (keine Rekursion) -- der anschließende Refresh
        passiert im Aufrufer. Bewusst dispatch-frei (reine Zustands-Buchhaltung): ein
        etwaiges ausstehendes Pending Edit ist zu diesem Zeitpunkt bereits geflusht --
        die zentralen Selektions-Setter in ``_mixin_selection.py`` rufen
        ``_commit_pending_edits()`` VOR ihrem jeweiligen Dispatch auf, nicht diese
        Methode. Würde hier stattdessen geflusht, liefe der Dispatch verschachtelt
        innerhalb des noch laufenden ``apply_state()``-Aufrufs, der diese Methode
        aufgerufen hat.

        Bei Wechsel zu einer anderen einzeln belegten Schülerzelle bleibt der
        Detail-Zustand erhalten (nur die Koordinaten folgen) statt zu schließen --
        ``EDITING`` wird dabei auf ``REVEALED`` heruntergestuft, damit die Navigation
        nicht automatisch den Namenseditor des neuen Schülers aktiviert. Nur bei
        leerer Zelle/Lehrertisch/Mehrfachauswahl wird der Zustand vollständig verworfen.
        """
        if self._desk_detail_state is None:
            return
        if not is_student_single:
            self._desk_detail_state = None
            return
        old_x, old_y, mode = self._desk_detail_state
        if (old_x, old_y) == (x, y):
            return
        if mode == DESK_DETAIL_EDITING:
            mode = DESK_DETAIL_REVEALED
        self._desk_detail_state = (x, y, mode)

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
            self._request_grid_redraw()
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
            self._request_grid_redraw()
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
            self._request_grid_redraw()

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
        self._commit_pending_edits()
        self._flush_pending_plan_save()
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
        self._commit_pending_edits()
        self._flush_pending_plan_save()
        self._downgrade_desk_detail_editing_to_revealed()

    def confirm_selected_cell(self) -> None:
        """Bestätigt die ausgewählte Zelle: kollabiert Auswahl und legt ggf. einen Schüler an."""
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()

        x, y = self.selected_cell
        self._controller.dispatch(CreateStudentIntent(x=x, y=y))

    def _commit_pending_edits(self) -> None:
        """Flusht alle ausstehenden Feld-Edits (Namen, Notizen), bevor
        der Bearbeitungskontext wechselt (anderer Tisch, Panel schließen, Plan
        wechseln, App schließen). Zentraler Ersatz für vormals verstreute
        Einzel-Flush-Aufrufe -- s. ``app/adapters/gui/_pending_field_save.py``.
        """
        for pending in self._pending_edits:
            pending.flush()

    def _capture_name_fields(self) -> tuple[StudentId, dict] | None:
        """Liest den aktuell editierten Schüler und die aktuellen Namensfeld-Werte.

        Callback für ``self._name_pending_save`` (``PendingFieldSave``). Gibt ``None``
        zurück, wenn kein Plan offen ist, die Auswahl kein Einzel-Tisch ist, oder die
        Zelle keinen Schüler enthält -- ``note_change()`` no-opt dann.
        """
        if not self.current_plan or not self.current_plan_path:
            return None
        if not self.selection.is_single():
            return None
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return None
        return student.student_id, {
            "first_name": self._name_var.get(),
            "last_name": self._last_name_var.get(),
            "nickname": self._nickname_var.get(),
        }

    def _apply_name_fields(self, student_id: StudentId, values: dict) -> None:
        """Speichert eine ausstehende Namens-/Spitznamenänderung für *student_id*.

        Sucht den Schüler über seine stabile ID (nicht über die aktuell selektierte
        Zelle) -- unabhängig davon, wohin die Auswahl inzwischen gewandert ist.
        Dispatcht nur bei tatsächlicher Änderung.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        student = self.current_plan.student_by_id(student_id)
        if not student:
            return
        first, last, nickname = (normalize_name_part(values[key]) for key in ("first_name", "last_name", "nickname"))
        if student.first_name_official != first or student.last_name != last:
            self._controller.dispatch(RenameStudentIntent(student_id=student_id, first_name=first, last_name=last))
        if student.nickname != nickname:
            self._controller.dispatch(SetNicknameIntent(student_id=student_id, nickname=nickname))

    def _load_detail_fields(self, student) -> None:
        """Zeigt Namen und Notizen von *student* (``None`` = Felder leeren und sperren).

        Einzige Stelle, die diese Felder programmatisch befüllt. Ein Feld wird nur
        neu geschrieben, wenn ``_field_needs_reload`` es verlangt -- sonst würde
        das Speichern während einer Tipp-Pause (Dispatch → ``apply_state`` →
        Refresh) den gerade bearbeiteten Inhalt durch den normalisierten Stand
        ersetzen (Leerzeichen am Ende und begonnene Leerzeilen weg, Cursor ans Ende).

        Args:
            student: Anzuzeigender Schüler oder ``None``.
        """
        student_id = student.student_id if student is not None else None
        state = "normal" if student is not None else "disabled"
        name_vars = (self._name_var, self._last_name_var, self._nickname_var)
        stored_names = (student.first_name_official, student.last_name, student.nickname) if student else ("", "", "")
        shown_names = tuple(normalize_name_part(var.get()) for var in name_vars)
        if self._field_needs_reload(student_id, self._name_pending_save, stored_names, shown_names):
            with self._name_pending_save.suspended():
                for var, value in zip(name_vars, stored_names):
                    var.set(value)
        for entry in (self.name_entry, self.last_name_entry, self.nickname_entry):
            entry.configure(state=state)

        stored_notes = student.diagnostic.notes if student else []
        shown_notes = normalize_note_lines(self.notes_field.get().splitlines())
        self.notes_field.text.configure(state="normal")
        if self._field_needs_reload(student_id, self._notes_pending_save, stored_notes, shown_notes):
            self.notes_field.set("\n".join(stored_notes))
            reset_text_modified(self.notes_field.text)  # neu befuellt = unveraendert
        notes_allowed = student is not None and accepts_notes(student)  # Notizen nur für Schüler:innen
        self.notes_field.text.configure(state="normal" if notes_allowed else "disabled")

        self._absent_var.set(student is not None and is_permanently_absent(student))
        self.absent_switch.state(["!disabled"] if student is not None and student.is_named() else ["disabled"])
        self._details_loaded_student_id = student_id

    def _field_needs_reload(self, student_id: StudentId | None, pending, stored, shown) -> bool:
        """Einzige Regel, ob ein Detail-Feld den gespeicherten Stand neu laden muss.

        Neu laden, wenn eine andere Person angezeigt wird, oder -- ohne wartende
        Eingabe dieser Person -- wenn der gespeicherte Stand vom normalisierten
        Feldinhalt abweicht (z. B. nach Undo/Redo). Eine noch nicht gespeicherte
        Eingabe hat immer Vorrang; sie wird ohnehin gleich gespeichert.

        Args:
            student_id: Angezeigte Person oder ``None``.
            pending: ``PendingFieldSave`` des Feldes.
            stored: Gespeicherter Wert (bereits normalisiert).
            shown: Feldinhalt, mit derselben Regel normalisiert wie beim Speichern.

        Returns:
            ``True``, wenn das Feld neu befüllt werden muss.
        """
        if student_id != self._details_loaded_student_id:
            return True
        if student_id is not None and pending.has_pending_for(student_id):
            return False
        return stored != shown

    def _on_notes_text_modified(self, _event=None) -> None:
        """Inhaltsaenderung des Notizfeldes (bw-gui ``on_text_modified``).

        Feuert bei Tastatureingabe, Paste und Kontextmenue. Das programmatische Neubefuellen in
        ``_load_detail_fields()`` gilt als unveraendert (``reset_text_modified``) und meldet
        nicht (frueher merkte es harmlos eine Speicherung des unveraenderten Inhalts vor).
        Pruefen und Zuruecksetzen von Tks Modified-Flag erledigt der Contract.
        """
        self._notes_pending_save.note_change()

    def _capture_notes_field(self) -> tuple[StudentId, list[str]] | None:
        """Liest den aktuell angezeigten Schüler und den aktuellen Feldinhalt.

        Callback für ``self._notes_pending_save`` (``PendingFieldSave``).
        """
        if not self.current_plan or not self.current_plan_path:
            return None
        if not self.selection.is_single():
            return None
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return None
        return student.student_id, self.notes_field.get().splitlines()

    def _apply_notes_field(self, student_id: StudentId, lines: list[str]) -> None:
        """Speichert eine ausstehende Notizänderung für *student_id*.

        Normalisiert genau einmal über ``normalize_note_lines`` (dieselbe Regel wie
        Usecase und Deserializer) und verwendet
        denselben normalisierten Wert für Vergleich UND Dispatch -- kein Unterschied
        zwischen dem Wert, gegen den geprüft wird, und dem tatsächlich gespeicherten.
        Dispatcht nur bei tatsächlicher Änderung: da ``<<Modified>>`` (anders als das
        frühere reine ``<FocusOut>``) auch beim programmatischen Neubefüllen für den
        neu selektierten Schüler feuert, würde sonst jeder Tischwechsel einen
        unnötigen Schreibvorgang auslösen.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        student = self.current_plan.student_by_id(student_id)
        if not student:
            return
        normalized = normalize_note_lines(lines)
        if student.diagnostic.notes == normalized:
            return
        self._controller.dispatch(SetNotesIntent(student_id=student_id, notes=normalized))
