"""Dialoge rund um Notenspalten: Spalte anlegen und Gewichtung (v4, intent-basiert).

Beide Fenster laufen über den zentralen Overlay-Pfad (``_create_overlay_dialog``:
Popup-Registrierung, Escape = ``dialog.cancel``); Enter bestätigt über die
vorhandene Binding-ID ``dialog.confirm``. Kategorien und ihre Namen kommen nur
aus ``GRADE_CATEGORIES``/``GRADE_CATEGORY_LABELS``, alle Eingaberegeln aus
``grade_weighting`` bzw. ``grade_weighting_form`` -- dieses Mixin hält nur Widgets.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, bind_action, dialog_keys
from app.adapters.gui.docs_table_model import grade_column_id, grade_column_key
from app.adapters.gui.grade_weighting_form import complement_percent, evaluate_weighting_form, format_share
from app.core.domain.grade_weighting import format_factor, parse_factor
from app.core.domain.models_v4 import DEFAULT_COLUMN_WEIGHT, GRADE_CATEGORIES, GRADE_CATEGORY_LABELS
from app.core.intents.grade_intents import AddGradeColumnIntent, UpdateGradeWeightingIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import RadioGroup, ScrollableFrame

_FACTOR_HINT = "Faktor (2 = doppelt, 0.5 = halb, 0 = zählt nicht)"


class GradeDialogsMixin:
    """Mixin: Notenspalte anlegen (Kategorie, Titel, Faktor) und Gewichtungsdialog mit Live-Anteilen."""

    def add_grade_column_dialog(self) -> None:
        """Öffnet den Dialog "Notenspalte hinzufügen": Kategorie, Titel und Faktor in einem Fenster.

        Vorbelegung der Kategorie: die der markierten Notenspalte, sonst die
        erste aus ``GRADE_CATEGORIES``. Ein ungültiger Faktor hält den Dialog
        offen und zeigt den Hinweis; OK legt die Spalte als einen Undo-Schritt
        an und markiert sie anschließend in der Doku-Tabelle.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        dialog = self._create_overlay_dialog("Notenspalte hinzufügen", "380x330")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        category_var = ui.StringVar(value=self._preselected_grade_category())
        RadioGroup(
            frame, title="Kategorie", variable=category_var,
            options=[(category, GRADE_CATEGORY_LABELS[category]) for category in GRADE_CATEGORIES],
        ).pack(anchor="w", pady=(0, 10))
        tui.Label(frame, text="Titel").pack(anchor="w")
        title_var = ui.StringVar()
        title_entry = tui.Entry(frame, textvariable=title_var)
        title_entry.pack(fill="x", pady=(2, 8))
        tui.Label(frame, text=_FACTOR_HINT).pack(anchor="w")
        factor_var = ui.StringVar(value=format_factor(DEFAULT_COLUMN_WEIGHT))
        tui.Entry(frame, textvariable=factor_var, width=8).pack(anchor="w", pady=(2, 4))
        error_var = ui.StringVar()
        tui.Label(frame, textvariable=error_var, style="Error.TLabel").pack(anchor="w")

        def confirm() -> None:
            try:
                weight = parse_factor(factor_var.get())
            except ValueError:
                error_var.set("Bitte als Faktor eine Zahl ab 0 eingeben (z. B. 2 oder 0,5).")
                return
            dialog.destroy()
            self._controller.dispatch(
                AddGradeColumnIntent(category=category_var.get(), title=title_var.get(), weight=weight)
            )
            new_column_id = self._controller.state.doc_selected_column_id
            if new_column_id:
                self._select_doc_nondate_column(grade_column_key(new_column_id))
            # Tabelle hat apply_state schon neu gebaut; nur die danach gewählte Spalte markieren.
            self._sync_docs_cursor()

        bind_action(dialog_keys(dialog), ENTER, confirm, binding_id="dialog.confirm")
        self._build_grade_dialog_buttons(frame, dialog, confirm)
        self._focus_overlay_widget(dialog, title_entry)

    def configure_grade_weighting_dialog(self) -> None:
        """Öffnet den Gewichtungsdialog: schriftlich/sonstig in %, darunter Faktor und Anteil je Notenspalte.

        Eine Eingabe in einem Prozentfeld setzt das andere auf 100 − x. Die
        Anteile rechnen bei jeder Eingabe live mit (``evaluate_weighting_form``);
        bei ungültiger Eingabe erscheint der Hinweis und OK ist gesperrt. OK
        schickt genau einen ``UpdateGradeWeightingIntent`` (ein Undo-Schritt).
        """
        if not self.current_plan or not self.current_plan_path:
            return
        columns = list(self.current_plan.documentation.grade_columns)
        weighting = self.current_plan.documentation.weighting
        dialog = self._create_overlay_dialog("Gewichtung", "500x560")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        written_var = ui.StringVar(value=str(weighting.written_percent))
        sonstige_var = ui.StringVar(value=str(weighting.sonstige_percent))
        first_entry = self._build_percent_row(frame, written_var, sonstige_var)
        factor_vars = {column.column_id: ui.StringVar(value=format_factor(column.weight)) for column in columns}
        share_vars = {column.column_id: ui.StringVar() for column in columns}
        self._build_weighting_column_rows(frame, columns, factor_vars, share_vars)
        error_var = ui.StringVar()
        tui.Label(frame, textvariable=error_var, style="Error.TLabel", wraplength=460).pack(anchor="w", pady=(6, 0))

        def evaluate():
            try:
                result = evaluate_weighting_form(
                    columns, written_var.get(), sonstige_var.get(), {cid: var.get() for cid, var in factor_vars.items()}
                )
            except ValueError as error:
                error_var.set(str(error))
                ok_button.configure(state="disabled")
                return None
            error_var.set("")
            ok_button.configure(state="normal")
            for column_id, share in result.shares.items():
                share_vars[column_id].set(format_share(share))
            return result

        def confirm() -> None:
            result = evaluate()
            if result is None:
                return
            dialog.destroy()
            self._controller.dispatch(UpdateGradeWeightingIntent(
                written_percent=result.written_percent,
                sonstige_percent=result.sonstige_percent,
                column_weights=result.column_weights,
            ))

        bind_action(dialog_keys(dialog), ENTER, confirm, binding_id="dialog.confirm")
        ok_button = self._build_grade_dialog_buttons(frame, dialog, confirm)
        self._link_complementary_percents(written_var, sonstige_var)
        for var in (written_var, sonstige_var, *factor_vars.values()):
            var.trace_add("write", lambda *_args: evaluate())
        evaluate()
        self._focus_overlay_widget(dialog, first_entry)

    def _preselected_grade_category(self) -> str:
        """Kategorie der markierten Notenspalte, sonst die erste aus ``GRADE_CATEGORIES``."""
        raw_id = grade_column_id(self._doc_selected_nondate_column_id)
        column = self.current_plan.documentation.column_by_id(raw_id) if raw_id else None
        return column.category if column is not None else GRADE_CATEGORIES[0]

    def _build_percent_row(self, frame: ui.Widget, written_var: ui.StringVar, sonstige_var: ui.StringVar) -> ui.Widget:
        """Baut die Zeile ``Schriftlich [__] %   Sonstig [__] %`` und gibt das erste Eingabefeld zurück.

        Args:
            frame: Eltern-Widget.
            written_var: Variable des Felds "schriftlich".
            sonstige_var: Variable des Felds "sonstig".
        """
        row = tui.Frame(frame)
        row.pack(fill="x", pady=(0, 10))
        entries = []
        for category, var in zip(GRADE_CATEGORIES, (written_var, sonstige_var)):
            tui.Label(row, text=GRADE_CATEGORY_LABELS[category]).pack(side="left", padx=(0 if not entries else 16, 4))
            entry = tui.Entry(row, textvariable=var, width=5)
            entry.pack(side="left")
            tui.Label(row, text="%").pack(side="left", padx=(2, 0))
            entries.append(entry)
        return entries[0]

    def _build_weighting_column_rows(
        self,
        frame: ui.Widget,
        columns: list,
        factor_vars: dict[str, ui.StringVar],
        share_vars: dict[str, ui.StringVar],
    ) -> None:
        """Baut je Kategorie eine Überschrift und die Zeilen ``Titel | Faktor | Anteil`` in einem scrollbaren Bereich.

        Args:
            frame: Eltern-Widget.
            columns: Notenspalten des Plans.
            factor_vars: ``column_id → Variable des Faktorfelds``.
            share_vars: ``column_id → Variable der Anteilsanzeige``.
        """
        scroll = ScrollableFrame(frame)
        scroll.pack(fill="both", expand=True)
        body = scroll.content
        body.columnconfigure(0, weight=1)
        if not columns:
            tui.Label(body, text="Noch keine Notenspalten.", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            return
        tui.Label(body, text=_FACTOR_HINT, style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        row_index = 1
        for category in GRADE_CATEGORIES:
            in_category = [column for column in columns if column.category == category]
            if not in_category:
                continue
            tui.Label(body, text=GRADE_CATEGORY_LABELS[category], style="SectionTitle.TLabel").grid(
                row=row_index, column=0, sticky="w", pady=(10, 2)
            )
            tui.Label(body, text="Faktor").grid(row=row_index, column=1, sticky="w", pady=(10, 2))
            tui.Label(body, text="Anteil").grid(row=row_index, column=2, sticky="e", pady=(10, 2))
            row_index += 1
            for column in in_category:
                tui.Label(body, text=column.title).grid(row=row_index, column=0, sticky="w", padx=(8, 8))
                tui.Entry(body, textvariable=factor_vars[column.column_id], width=6).grid(row=row_index, column=1, pady=1)
                tui.Label(body, textvariable=share_vars[column.column_id], style="Muted.TLabel", width=8, anchor="e").grid(
                    row=row_index, column=2, sticky="e", padx=(8, 0)
                )
                row_index += 1

    def _link_complementary_percents(self, first: ui.StringVar, second: ui.StringVar) -> None:
        """Hält die beiden Prozentfelder bei 100 %: eine Eingabe im einen setzt das andere (``complement_percent``).

        Args:
            first: Variable des einen Prozentfelds.
            second: Variable des anderen Prozentfelds.
        """
        updating = [False]

        def mirror(source: ui.StringVar, target: ui.StringVar) -> None:
            if updating[0]:
                return
            complement = complement_percent(source.get())
            if complement is None or complement == target.get():
                return
            updating[0] = True
            try:
                target.set(complement)
            finally:
                updating[0] = False

        first.trace_add("write", lambda *_args: mirror(first, second))
        second.trace_add("write", lambda *_args: mirror(second, first))

    def _build_grade_dialog_buttons(self, frame: ui.Widget, dialog: ui.Toplevel, confirm) -> ui.Widget:
        """Baut die Knopfzeile ``Abbrechen | OK`` und gibt den OK-Knopf zurück.

        Args:
            frame: Eltern-Widget.
            dialog: Das Dialogfenster (Abbrechen schließt es).
            confirm: Aktion des OK-Knopfs.
        """
        button_row = tui.Frame(frame)
        button_row.pack(fill="x", side="bottom", pady=(10, 0))
        ok_button = tui.Button(button_row, text="OK", command=confirm)
        ok_button.pack(side="right")
        tui.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(0, 8))
        return ok_button
