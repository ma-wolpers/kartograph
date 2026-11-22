"""Docs-Navigation-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt den Abgleich Auswahl → Doku-Tabelle (``_sync_docs_cursor``), die aktive
logische Spalte (inkl. Datumsanker), Inline-Editor-Schließung und Wert-Anwendung
für die Dokumentations-Tabelle bereit.
"""

from __future__ import annotations

from app.adapters.gui.docs_cell_editing import commit_cell_text
from app.adapters.gui.docs_table_model import NACHNAME_KEY, VORNAME_KEY, flag_key_of
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult
from bw_gui.runtime import ui


class DocsNavMixin:
    """Mixin: Doku-Cursor-Abgleich, Spaltenauswahl und Inline-Editor-Verwaltung (v4)."""

    def _sync_docs_cursor(self) -> None:
        """Einziger Abgleich Auswahl → Doku-Tabelle: Zeile, aktive Spalte, Sichtbarkeit, Statuszeile, Spaltenknöpfe.

        Ersetzt das frühere Zell-Overlay, das Neusetzen aller Spaltenköpfe und
        den Auswahl-Abgleich über drei Treeviews: das Grid verschiebt nur sein
        Auswahlband, den Zellcursor und die Spaltenmarke (wenige Tk-Aufrufe,
        unabhängig von der Spaltenzahl) und scrollt bei Bedarf.
        """
        index = self._selected_docs_student_index()
        row_id = self._doc_row_id_by_student_index.get(index) if index is not None else None
        key = self._doc_active_column_key()
        self.docs_grid.set_cursor(row_id, key)
        if row_id is not None:
            self.docs_grid.see(row_id, key)
        self._refresh_doc_selection_status()
        self._sync_docs_column_buttons()

    def _close_docs_inline_editor(self, apply_changes: bool = False, *, keep_open_on_invalid: bool = False) -> bool:
        """Schließt den Inline-Editor und trägt ggf. den Wert in das beim Öffnen festgelegte Ziel ein.

        Reihenfolge: prüfen → abkoppeln → eintragen → zerstören. Abgekoppelt wird
        vor dem Eintragen und Zerstören, damit ein dabei ausgelöstes erneutes
        Schließen (Fokusverlust beim Zerstören, Tabellen-Neuaufbau nach dem
        Dispatch) nichts mehr vorfindet und nicht doppelt speichert.

        Args:
            apply_changes: Eingegebenen Wert übernehmen.
            keep_open_on_invalid: Bei ungültiger Eingabe offen bleiben (Enter),
                statt sie mit Hinweis zu verwerfen (Fokusverlust).

        Returns:
            ``True``, wenn der Editor jetzt geschlossen ist.
        """
        editor, target = self._docs_inline_editor, self._docs_inline_editor_target
        if editor is None:
            return True
        commit = None
        if apply_changes and target is not None and self.current_plan and editor.winfo_exists():
            commit = commit_cell_text(self.current_plan, target, editor.get())
            if commit.intent is None:
                self.status_var.set(commit.message)
                if keep_open_on_invalid:
                    editor.selection_range(0, ui.END)
                    return False
                commit = None
        self._docs_inline_editor = None
        self._docs_inline_editor_target = None
        if commit is not None:
            self._controller.dispatch(commit.intent)
            self.status_var.set(commit.message)
        if editor.winfo_exists():
            editor.destroy()
        return True

    def _on_docs_inline_editor_return(self, _event) -> EventResult:
        """Übernimmt den Wert (Return/KP_Enter); bei ungültiger Eingabe bleibt der Editor offen.

        Args:
            _event: bw-gui-``KeyEvent`` (Inhalt wird nicht ausgewertet).
        """
        if self._close_docs_inline_editor(apply_changes=True, keep_open_on_invalid=True):
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

    def _activate_selected_docs_cell(self, initial_text: str | None = None) -> bool:
        """Handelt auf der ausgewählten Zelle (Enter, Strg+G, Tippen) -- s. ``_activate_docs_cell``.

        Args:
            initial_text: Getipptes Startzeichen oder ``None``.

        Returns:
            ``True``, wenn etwas geschah (Editor offen, Dialog, Umschalten).
        """
        selected_iid = self._doc_row_id_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is None:
            return False
        return self._activate_docs_cell(selected_iid, self._doc_active_column_key(), initial_text)

    def _activate_docs_cell(self, row_id: str, column_key: str | None, initial_text: str | None = None) -> bool:
        """Einzige Regel, was "auf einer Zelle handeln" heißt (Enter, Doppelklick, Tippen).

        - Note oder eigene Notizspalte: Inline-Editor (mit *initial_text* als Inhalt, falls getippt).
        - Allgemeine Notizen: mehrzeiliger Notizdialog (nicht beim Tippen).
        - Ja/Nein: Markierung umschalten (nicht beim Tippen -- Ziffern bleiben Fenster-Kürzel).
        - Datum: Symboldialog für den Tageseintrag (nicht beim Tippen -- Buchstaben
          setzen dort direkt Symbole).
        - Sonst: nichts.

        Einen eigenen Knopf „Zelle bearbeiten“ gibt es bewusst nicht (Entscheidung
        der Nutzerin 2026-11-22); Strg+G und Strg+Umschalt+S lösen dasselbe aus.

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            column_key: Spaltenschlüssel der Zelle oder ``None``.
            initial_text: Getipptes Startzeichen oder ``None``.

        Returns:
            ``True``, wenn etwas geschah.
        """
        kind = self._doc_axis.kind_of(column_key)
        if self._doc_axis.is_inline_editable(column_key):
            return self._open_docs_inline_editor(row_id, column_key, initial_text)
        if initial_text is not None:
            return False
        if kind == "notes":
            return self.edit_docs_general_notes_dialog(row_id)
        if kind == "flag":
            return self._toggle_docs_flag(row_id, flag_key_of(column_key))
        if kind == "date":
            self.set_selected_documentation_symbol_dialog()
            return True
        return False

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
        Namensspalten existieren immer und bleiben gültig. Sind keine
        Datumsspalten sichtbar (Doku-Bereich ausgeblendet), wird statt des
        Ankers die erste auswählbare Spalte rechts der Namen aktiv, sonst der
        Nachname -- so gibt es immer eine aktive Spalte für ←/→. Keine
        Auswahl-Aktion, löscht insbesondere keine noch gültige Spalte.

        Args:
            date_count: Aktuelle Anzahl der Datumsspalten nach dem Rebuild.
        """
        self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, date_count - 1)))
        if not self._is_valid_doc_nondate_column(self._doc_selected_nondate_column_id):
            self._doc_selected_nondate_column_id = None
        if self._doc_selected_nondate_column_id is None and self._doc_axis.date_key(0) is None:
            self._doc_selected_nondate_column_id = self._doc_axis.neighbor(VORNAME_KEY, 1) or NACHNAME_KEY
