"""Re-Export-Shim für die Usecase-Schicht.

Alle öffentlichen Funktionen werden aus ihren spezifischen Modulen importiert
und hier wieder exportiert, damit bestehende Imports (z.B. in main_window.py
und pdf_exporter.py) unverändert bleiben.
"""

# Tisch-Operationen
from app.core.usecases.desk_usecases import (
    create_student_desk,
    delete_desk,
    set_teacher_desk,
    update_student_last_name,
    update_student_name,
)

# Dokumentationsdaten
from app.core.usecases.date_usecases import (
    ensure_documentation_date,
    rename_documentation_date,
)

# Symbol-Operationen
from app.core.usecases.symbol_usecases import (
    set_documentation_symbol,
    summarize_latest_symbols_for_student,
    toggle_symbol,
)

# Noten-Operationen
from app.core.usecases.grade_usecases import (
    add_grade_column,
    compute_grade_display_for_student,
    compute_grade_subtotal_display_for_student,
    set_documentation_grade,
    set_grade_weighting,
)

# Farb-Operationen
from app.core.usecases.color_usecases import (
    cleanup_unused_color_meanings,
    is_color_used,
    set_color_meaning,
    toggle_color_marker,
)

__all__ = [
    # desk
    "create_student_desk",
    "delete_desk",
    "set_teacher_desk",
    "update_student_last_name",
    "update_student_name",
    # date
    "ensure_documentation_date",
    "rename_documentation_date",
    # symbol
    "set_documentation_symbol",
    "summarize_latest_symbols_for_student",
    "toggle_symbol",
    # grade
    "add_grade_column",
    "compute_grade_display_for_student",
    "compute_grade_subtotal_display_for_student",
    "set_documentation_grade",
    "set_grade_weighting",
    # color
    "cleanup_unused_color_meanings",
    "is_color_used",
    "set_color_meaning",
    "toggle_color_marker",
]
