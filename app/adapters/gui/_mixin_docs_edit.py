"""Docs-Edit-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Umschalten und Löschen von Dokumentationssymbolen sowie
den Inline-Editor der Datentabelle (Noten und eigene Notizspalten) bereit.
"""

from __future__ import annotations

from app.core.domain.symbol_toggle import next_symbol_toggle_strength
from app.core.intents.session_intents import ClearDocEntryIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.adapters.gui._local_keys import ENTER, ESCAPE, widget_keys
from app.adapters.gui.doc_action_target import DocActionTarget
from app.adapters.gui.docs_cell_editing import CellEditTarget, cell_text, commit_cell_text
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import on_focus_change, ui
from bw_gui.runtime import widgets as tui


class DocsEditMixin:
    """Mixin: Symbol-Umschalten, Symbol-Löschen und Inline-Noten-Editor in der Dokumentations-Ansicht (v4)."""

    def _open_docs_inline_editor(self, row_id: str, column_key: str, initial_text: str | None = None) -> bool:
        """Öffnet den Entry-Inline-Editor in der Zelle (*row_id*, *column_key*).

        Ein Editor für alle bearbeitbaren Zellen (Noten und eigene
        Notizspalten, ``DocColumnAxis.is_inline_editable``); was er anzeigt und
        wie er speichert, steht in ``docs_cell_editing``. Die Zellgeometrie
        liefert ``DataGrid.cell_bbox`` (scrollt die Zelle sichtbar und rendert
        vorher ausstehende Änderungen, damit die Position stimmt).

        Zwei Startarten, ein Editor: ohne *initial_text* (Enter, Doppelklick,
        Strg+G) steht der bisherige Wert markiert darin; mit *initial_text*
        (Tippen auf der Zelle) ersetzt der Text den Wert, der Cursor steht dahinter.

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            column_key: Spaltenschlüssel, z. B. ``"grade_<id>"`` oder ``"note_<id>"``.
            initial_text: Getipptes Startzeichen oder ``None`` für den bisherigen Wert.

        Returns:
            ``True``, wenn der Editor jetzt offen ist; ``False`` für nicht bearbeitbare
            Spalten, unbekannte/unbenannte Zeilen oder nicht darstellbare Zellen.
        """
        if not self.current_plan:
            return False
        if not self._doc_axis.is_inline_editable(column_key):
            return False
        self._close_docs_inline_editor(apply_changes=False)
        box = self.docs_grid.cell_bbox(row_id, column_key)
        if box is None:
            return False
        host, x, y, width, height = box

        target = self._cell_edit_target(row_id, column_key)
        if target is None:
            return False
        replace_with_typed = initial_text is not None
        if not replace_with_typed:
            initial_text = cell_text(self.current_plan, target)

        editor = tui.Entry(host)
        editor.insert(0, initial_text)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        if replace_with_typed:
            editor.icursor(ui.END)
        else:
            editor.selection_range(0, ui.END)
        keys = widget_keys(editor)
        keys.bind(ENTER, self._on_docs_inline_editor_return, binding_id="docs.inline.return", intent="docs.inline.return", allow_when_text_input=True)
        keys.bind(ESCAPE, self._on_docs_inline_editor_escape, binding_id="docs.inline.escape", intent="docs.inline.escape", allow_when_text_input=True)
        on_focus_change(editor, on_lost=lambda _change: self._close_docs_inline_editor(apply_changes=True))

        self._docs_inline_editor = editor
        self._docs_inline_editor_target = target
        return True

    def _cell_edit_target(self, row_id: str, column_key: str) -> CellEditTarget | None:
        """Einzige Regel, *welche* Zelle mit Textwert geschrieben wird: Zeile und Spalte der Zelle.

        Für Editor, Entf, Ausschneiden und Einfügen. Nie die spätere Auswahl;
        ein Datum spielt keine Rolle (ein Wert je Spalte). Noten sind bei
        dauerhaft Abwesenden gesperrt (``_report_if_locked``); Notizspalten und
        allgemeine Notizen nicht (``accepts_notes``).

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
            column_key: Spaltenschlüssel mit Textwert (``DocColumnAxis.holds_text``).

        Returns:
            Das Ziel oder ``None`` (unbekannte Zeile, unbenannter Tisch, gesperrte Note
            -- dann mit Sperrhinweis).
        """
        student = self._named_docs_student(self._doc_student_index_by_iid.get(row_id))
        if student is None or (self._doc_axis.is_grade(column_key) and self._report_if_locked(student)):
            return None
        return CellEditTarget(student.student_id, column_key)

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

        Datenansicht: ausgewählte Zeile am Datumsanker; Raster: markierter
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

        Bearbeitbare Zelle (Note, eigene Notizspalte): nur dieser Wert -- über
        denselben Weg wie ein geleerter Inline-Editor (``commit_cell_text`` mit
        leerer Eingabe). Datumsspalte: der Tageseintrag (Symbole, Mitarbeit,
        Notiz). Name, Zusammenfassung, Teil- und Gesamtnote, allgemeine Notizen
        und Ja/Nein sind hier nicht löschbar -- die Statuszeile sagt es.
        """
        student, key = self._selected_docs_student(), self._doc_active_column_key()
        if student is None or key is None:
            return
        if self._doc_axis.is_inline_editable(key):
            target = self._cell_edit_target(str(student.student_id), key)
            commit = commit_cell_text(self.current_plan, target, "") if target is not None else None
            if commit is not None and commit.intent is not None:
                self._controller.dispatch(commit.intent)
                self.status_var.set(commit.message)
        elif self._doc_axis.is_date(key):
            if not self._report_if_locked(student):
                self._controller.dispatch(ClearDocEntryIntent(student_id=student.student_id, date=self._doc_anchor_date()))
        else:
            self.status_var.set("In dieser Spalte gibt es nichts zu löschen.")
