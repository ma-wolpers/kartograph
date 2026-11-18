"""Formular „Kompetenz (alle Pläne)“: Name, Gruppe und drei Stufentexte bearbeiten oder anlegen.

Die Stufen stehen von oben nach unten absteigend (3 = höchste Ausprägung), wie
in ``docs/SYMBOLE.md``. Ein kurzer Hinweis nennt die wichtigsten
Formulierungsregeln; geprüft wird nur, was die Regeln in
``catalog_validation.validate_competence_fields`` verlangen (über den reinen
Usecase, vor dem Dispatch). Enter ist hier nicht gebunden — es gehört in die
mehrzeiligen Textfelder.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ESCAPE
from app.adapters.gui._symbol_form_widgets import FORM_HINT_WRAP
from app.core.domain.catalog_validation import CatalogValidationError
from app.core.intents.catalog_intents import AddCompetenceIntent, UpdateCompetenceIntent
from app.core.usecases.catalog_usecases import add_competence, update_competence
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui
from bw_gui.widgets import WrappedTextField

WRITING_HINT = ("ohne Subjekt, Verb vorn, klein, ohne Schlusspunkt · jede Stufe sagt, was gelingt; "
                "Stufe 1 nennt die Hilfe („…, wenn … zur Verfügung steht (z. B. …)“)")
LEVEL_LABELS = ("Stufe 3 (höchste)", "Stufe 2", "Stufe 1")


class CatalogCompetenceFormMixin:
    """Mixin: Formular für eine programmweite Kompetenz."""

    def _open_catalog_competence_form(self, competence_id: str | None) -> None:
        """Öffnet das Formular zum Bearbeiten (*competence_id*) oder Anlegen (``None``).

        Args:
            competence_id: ID der Kompetenz oder ``None`` für eine neue.
        """
        state = self._controller.state
        current = next((c for c in state.competence_catalog if c.id == competence_id), None)
        title = f"Kompetenz „{current.name}“ (alle Pläne)" if current else "Neue Kompetenz (alle Pläne)"
        dialog = self._create_overlay_dialog(title, "560x560", parent=self._catalog_window)
        frame = tui.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)

        name_var = ui.StringVar(value=current.name if current else "")
        group_var = ui.StringVar(value=current.group if current else "")
        row = tui.Frame(frame)
        row.pack(fill="x")
        tui.Label(row, text="Name").pack(side="left")
        name_entry = tui.Entry(row, textvariable=name_var, width=30)
        name_entry.pack(side="left", padx=(6, 12))
        tui.Label(row, text="Gruppe").pack(side="left")
        groups = list(dict.fromkeys(c.group for c in state.competence_catalog if c.group))
        tui.Combobox(row, textvariable=group_var, values=groups, width=20).pack(side="left", padx=(6, 0))
        tui.Label(frame, text=WRITING_HINT, style="Muted.TLabel", wraplength=FORM_HINT_WRAP,
                  justify="left").pack(anchor="w", pady=(8, 4))

        fields: list[WrappedTextField] = []
        initial = tuple(reversed(current.levels)) if current else ("", "", "")
        for label, text in zip(LEVEL_LABELS, initial):
            tui.Label(frame, text=label).pack(anchor="w", pady=(6, 2))
            field = WrappedTextField(frame, initial=text, height=3)
            field.pack(fill="x")
            fields.append(field)

        status_var = ui.StringVar(value="")
        tui.Label(frame, textvariable=status_var, style="Error.TLabel", wraplength=FORM_HINT_WRAP,
                  justify="left").pack(anchor="w", pady=(8, 0))

        def submit() -> None:
            three, two, one = (field.get() for field in fields)
            levels = (one, two, three)
            try:
                if current is None:
                    add_competence(state.competence_catalog, name_var.get(), group_var.get(), levels)
                    intent = AddCompetenceIntent(name_var.get(), group_var.get(), levels)
                else:
                    update_competence(state.competence_catalog, current.id, name_var.get(), group_var.get(), levels)
                    intent = UpdateCompetenceIntent(current.id, name_var.get(), group_var.get(), levels)
            except CatalogValidationError as exc:
                status_var.set(str(exc))
                return
            self._controller.dispatch(intent)
            dialog.destroy()
            self._refresh_catalog_tables()

        buttons = tui.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        cancel = tui.Button(buttons, text="Abbrechen", command=dialog.destroy)
        cancel.pack(side="right")
        self._attach_hover_help(cancel, label="Ohne Speichern schließen", shortcut=ESCAPE)
        tui.Button(buttons, text="Speichern", command=submit).pack(side="right", padx=(0, 8))
        self._focus_overlay_widget(dialog, name_entry)
