"""Schreibt eine für Namenfit importierbare CSV-Datei.

Reine I/O-Schicht: die eigentliche Rasterberechnung (Tischgruppen-Spaltenblöcke,
Namensauflösung, Validierung) liegt vollständig in
``app/core/domain/namenfit_csv_export.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.namenfit_csv_export import build_namenfit_rows


def export_namenfit_csv(
    plan: SeatingPlan,
    output_path: Path,
    *,
    name_format: str,
    disambiguate_colliding_names: bool = True,
) -> None:
    """Exportiert *plan* als Namenfit-kompatible CSV-Datei nach *output_path*.

    Schreibt UTF-8 ohne BOM mit dem Standard-CSV-Dialekt (Komma-getrennt) —
    exakt das Format, das Namenfits eigener Import erwartet
    (``open(path, newline="", encoding="utf-8")`` + ``csv.reader``-Standard-
    werte in ``A:\\Code\\namenfit\\app\\core\\layout.py::load_csv_layout``).

    Args:
        plan: Zu exportierender Sitzplan.
        output_path: Zieldatei (wird überschrieben, falls vorhanden).
        name_format: Eines der ``NAME_FORMAT_OPTIONS`` aus ``settings.py``.
        disambiguate_colliding_names: Siehe ``build_namenfit_rows()``.

    Raises:
        UngroupedStudentsError: Siehe ``build_namenfit_rows()``.
        DuplicateDisplayNamesError: Siehe ``build_namenfit_rows()``.
        OSError: Bei Schreibfehlern (z. B. Zielordner nicht beschreibbar).
    """
    rows = build_namenfit_rows(plan, name_format, disambiguate_colliding_names)
    with open(output_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerows(rows)
