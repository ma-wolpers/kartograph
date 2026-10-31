"""Dialog für alte Mehrfachnoten: pro Person und Spalte die gültige Note wählen.

Seit es eine Note je Person und Spalte gibt, können Altpläne dort mehrere Noten
enthalten (``DocumentationBlock.grade_conflicts``). Der Dialog meldet sie beim
Öffnen des Plans. "Später" ändert nichts: Die Werte bleiben in der Datei, und der
Dialog erscheint beim nächsten Öffnen wieder.
"""

from __future__ import annotations

from app.core.domain.grade_scale import scale_for
from app.core.domain.student_id import StudentId
from app.core.intents.grade_intents import ResolveGradeConflictsIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import ScrollableFrame

_INTRO = (
    "In diesen Notenspalten stehen mehrere Noten derselben Person. Künftig gilt eine Note pro Spalte: "
    "Bitte jeweils die gültige wählen (vorbelegt ist die neueste).\n\n"
    "Bis zur Entscheidung zählt nur die neueste Note, die Gesamtnote kann sich dadurch ändern. "
    "Mit „Später“ bleiben alle Werte gespeichert, und diese Abfrage erscheint beim nächsten Öffnen wieder."
)


class GradeConflictsMixin:
    """Mixin: meldet alte Mehrfachnoten beim Öffnen eines Plans und lässt sie auflösen."""

    def _report_grade_conflicts(self) -> bool:
        """Öffnet den Dialog, falls der aktuelle Plan offene Mehrfachnoten enthält.

        Returns:
            ``True``, wenn der (modale) Dialog geöffnet wurde.
        """
        if not self.current_plan or not self.current_plan.documentation.grade_conflicts:
            return False
        self._open_grade_conflicts_dialog()
        return True

    def _open_grade_conflicts_dialog(self) -> None:
        """Zeigt je Konflikt Person, Spalte und eine Auswahl der Noten mit Datum."""
        doc = self.current_plan.documentation
        scale = scale_for(doc.grade_scale)
        dialog = self._create_overlay_dialog("Mehrere Noten in einer Spalte", "720x560")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(container, text=_INTRO, wraplength=690, justify="left").pack(anchor="w", pady=(0, 10))
        buttons = tui.Frame(container)
        buttons.pack(fill="x", side="bottom", pady=(10, 0))
        scroll = ScrollableFrame(container)
        scroll.pack(fill="both", expand=True)

        rows: list[tuple[StudentId, str, ui.StringVar, dict[str, float]]] = []
        for conflict in doc.grade_conflicts:
            student = self.current_plan.classroom.student_by_id(conflict.student_id)
            column = doc.column_by_id(conflict.column_id)
            values = {f"{scale.format_value(value)}  ({date})": value for date, value in reversed(conflict.candidates)}
            row = tui.Frame(scroll.content)
            row.pack(fill="x", pady=2)
            tui.Label(row, text=student.display_name(), width=28, anchor="w").pack(side="left")
            tui.Label(row, text=column.title, width=20, anchor="w").pack(side="left")
            choice = ui.StringVar(master=dialog, value=next(iter(values)))
            tui.Combobox(row, textvariable=choice, state="readonly", values=list(values), width=24).pack(side="left")
            rows.append((conflict.student_id, conflict.column_id, choice, values))

        def apply_choices() -> None:
            choices = tuple((sid, column_id, values[choice.get()]) for sid, column_id, choice, values in rows)
            self._destroy_tracked_dialog(dialog)
            self._controller.dispatch(ResolveGradeConflictsIntent(choices=choices))

        tui.Button(buttons, text="Übernehmen", command=apply_choices).pack(side="right")
        tui.Button(buttons, text="Später", command=lambda: self._destroy_tracked_dialog(dialog)).pack(side="right", padx=(0, 6))
