"""Typisiertes Intent-System für Kartograph.

Alle UI-Aktionen werden als unveränderliche Dataclasses modelliert und
via ``KartographAppController.dispatch(intent)`` verarbeitet.
"""

from app.core.intents.base import Intent

from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.plan_intents import (
    OpenPlanIntent,
    CreatePlanIntent,
    RenamePlanIntent,
    DeletePlanIntent,
    DuplicatePlanIntent,
    ArchivePlanIntent,
    RestorePlanIntent,
)
from app.core.intents.student_intents import (
    CreateStudentIntent,
    MoveStudentIntent,
    RenameStudentIntent,
    DeleteStudentIntent,
    SetTeacherSeatIntent,
)
from app.core.intents.symbol_intents import (
    ToggleDiagnosticSymbolIntent,
    RecordDocumentationSymbolIntent,
)
from app.core.intents.participation_intents import SetParticipationRatingIntent
from app.core.intents.color_intents import ToggleColorIntent
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    RecordGradeIntent,
    UpdateGradeWeightingIntent,
)
from app.core.intents.session_intents import (
    AddSessionIntent,
    DeleteSessionIntent,
    NavigateSessionIntent,
    GoToTodayIntent,
    ClearDocEntryIntent,
)
from app.core.intents.navigation_intents import (
    SelectCellIntent,
    MoveSelectionIntent,
    ClearSelectionIntent,
)
from app.core.intents.edit_intents import (
    UndoIntent,
    RedoIntent,
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
)
from app.core.intents.view_intents import (
    SetEditorSurfaceIntent,
    ToggleEditorSurfaceIntent,
    ZoomInIntent,
    ZoomOutIntent,
    ResetViewIntent,
    ExportPdfIntent,
    ExportNamenfitCsvIntent,
    ExportStudentPngsZipIntent,
    OpenSettingsIntent,
    OpenTablegroupSettingsIntent,
    UpdateSettingsIntent,
)

__all__ = [
    "Intent",
    # Accommodation
    "SetAccommodationsIntent",
    # Plan
    "OpenPlanIntent",
    "CreatePlanIntent",
    "RenamePlanIntent",
    "DeletePlanIntent",
    "DuplicatePlanIntent",
    "ArchivePlanIntent",
    "RestorePlanIntent",
    # Student
    "CreateStudentIntent",
    "MoveStudentIntent",
    "RenameStudentIntent",
    "DeleteStudentIntent",
    "SetTeacherSeatIntent",
    # Symbol
    "ToggleDiagnosticSymbolIntent",
    "RecordDocumentationSymbolIntent",
    # Participation
    "SetParticipationRatingIntent",
    # Color
    "ToggleColorIntent",
    # Grade
    "AddGradeColumnIntent",
    "DeleteGradeColumnIntent",
    "RecordGradeIntent",
    "UpdateGradeWeightingIntent",
    # Session
    "AddSessionIntent",
    "DeleteSessionIntent",
    "NavigateSessionIntent",
    "GoToTodayIntent",
    "ClearDocEntryIntent",
    # Navigation
    "SelectCellIntent",
    "MoveSelectionIntent",
    "ClearSelectionIntent",
    # Edit
    "UndoIntent",
    "RedoIntent",
    "CopySelectionIntent",
    "CutSelectionIntent",
    "PasteSelectionIntent",
    # View
    "SetEditorSurfaceIntent",
    "ToggleEditorSurfaceIntent",
    "ZoomInIntent",
    "ZoomOutIntent",
    "ResetViewIntent",
    "ExportPdfIntent",
    "ExportNamenfitCsvIntent",
    "ExportStudentPngsZipIntent",
    "OpenSettingsIntent",
    "OpenTablegroupSettingsIntent",
    "UpdateSettingsIntent",
]
