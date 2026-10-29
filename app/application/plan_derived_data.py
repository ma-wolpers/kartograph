"""PlanDerivedData — alle aus dem Plan abgeleiteten Anzeigedaten, einmal pro Inhaltsstand.

Einzige Quelle für Werte, die Raster, Doku-Tabelle und Details aus dem
aktuellen Plan berechnen (neueste Symbole, Notenlisten/-anzeigen, neueste
Noten, Sitzgeometrien, Anzeigenamen). Der Controller hält genau ein Objekt
pro ``content_version``; jede Größe wird erst beim ersten Zugriff berechnet
und danach wiederverwendet. Eine reine Cursorbewegung ändert die
``content_version`` nicht und kostet hier daher nichts. Tk-frei.
"""

from __future__ import annotations

from functools import cached_property

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_naming import compute_display_names
from app.core.domain.table_groups import build_seat_geometries_v4
from app.core.usecases.v4.grade_usecases import (
    collect_grade_value_lists_by_student,
    compute_grade_display_by_student,
    compute_grade_subtotal_display_by_student,
    compute_latest_grades_by_student,
)
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student


class PlanDerivedData:
    """Lazily berechnete Ableitungen eines Plans (unveränderlich für einen Inhaltsstand)."""

    def __init__(self, plan: SeatingPlan) -> None:
        """Bindet die Ableitungen an *plan* (wird nicht kopiert und nicht verändert).

        Args:
            plan: Aktueller Plan dieses Inhaltsstands.
        """
        self.plan = plan
        self._names: dict[tuple[str, bool], dict] = {}
        self._subtotals: dict[str, dict] = {}

    @cached_property
    def latest_symbols(self) -> dict:
        """Neueste Symbolstärken je Schüler (``summarize_latest_symbols_by_student``)."""
        return summarize_latest_symbols_by_student(self.plan)

    @cached_property
    def grade_value_lists(self) -> dict:
        """Alle Notenwerte je Schüler und Kategorie (gemeinsame Basis aller Notenanzeigen)."""
        return collect_grade_value_lists_by_student(self.plan)

    @cached_property
    def grade_display(self) -> dict:
        """Gesamtnoten-Anzeige je Schüler (inkl. vorläufiger Klammernoten)."""
        return compute_grade_display_by_student(self.plan, value_lists=self.grade_value_lists)

    @cached_property
    def latest_grades(self) -> dict:
        """Zuletzt eingetragene Note je Schüler und Notenspalte."""
        return compute_latest_grades_by_student(self.plan)

    @cached_property
    def seat_geometries(self) -> list:
        """Sitzgeometrien inkl. Tischgruppen (``build_seat_geometries_v4``)."""
        return build_seat_geometries_v4(self.plan)

    def subtotal_display(self, category: str) -> dict:
        """Teilnoten-Anzeige je Schüler für *category* (``"schriftlich"``/``"sonstig"``).

        Args:
            category: Notenkategorie.
        """
        if category not in self._subtotals:
            self._subtotals[category] = compute_grade_subtotal_display_by_student(
                self.plan, category, value_lists=self.grade_value_lists
            )
        return self._subtotals[category]

    def display_names(self, name_format: str, disambiguate: bool) -> dict:
        """Anzeigenamen je Schüler für ein Namensformat (je Format einmal berechnet).

        Args:
            name_format: Namensformat aus den Einstellungen.
            disambiguate: Kollidierende Namen unterscheidbar machen.
        """
        key = (name_format, disambiguate)
        if key not in self._names:
            self._names[key] = compute_display_names(self.plan.classroom.students, name_format, disambiguate)
        return self._names[key]
