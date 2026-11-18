"""Typisiertes Intent-System für Kartograph.

Alle UI-Aktionen werden als unveränderliche Dataclasses modelliert und
via ``KartographAppController.dispatch(intent)`` verarbeitet.
"""

from app.core.intents.base import Intent

from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.snapshot_intents import (
    CreateSnapshotIntent,
    DeleteSnapshotIntent,
    RenameSnapshotIntent,
    RestoreSnapshotIntent,
)
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
    DeleteStudentsIntent,
    SetPermanentlyAbsentIntent,
    SetTeacherSeatIntent,
)
from app.core.intents.symbol_intents import (
    ToggleDiagnosticSymbolIntent,
    RecordDocumentationSymbolIntent,
)
from app.core.intents.participation_intents import SetParticipationRatingIntent
from app.core.intents.color_intents import ToggleColorIntent
from app.core.intents.tablegroup_intents import ApplyTablegroupSettingsIntent
from app.core.intents.catalog_intents import (
    AddCatalogSymbolIntent,
    AddCompetenceIntent,
    UpdateCatalogSymbolIntent,
    UpdateCompetenceIntent,
)
from app.core.intents.custom_symbol_intents import (
    AddCustomSymbolIntent,
    DeleteCustomSymbolIntent,
    SetSymbolOverrideIntent,
    UpdateCustomSymbolIntent,
)
from app.core.intents.submission_intents import ApplyMissingSubmissionsIntent, SetSubmissionStatusIntent
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    RecordGradeIntent,
    ResolveGradeConflictsIntent,
    SetGradeScaleIntent,
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
    # Notizen
    "SetNotesIntent",
    # Snapshot
    "CreateSnapshotIntent",
    "DeleteSnapshotIntent",
    "RenameSnapshotIntent",
    "RestoreSnapshotIntent",
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
    "DeleteStudentsIntent",
    "SetPermanentlyAbsentIntent",
    "SetTeacherSeatIntent",
    # Symbol
    "ToggleDiagnosticSymbolIntent",
    "RecordDocumentationSymbolIntent",
    # Participation
    "SetParticipationRatingIntent",
    # Color
    "ToggleColorIntent",
    "ApplyTablegroupSettingsIntent",
    "AddCustomSymbolIntent",
    "UpdateCustomSymbolIntent",
    "DeleteCustomSymbolIntent",
    "SetSymbolOverrideIntent",
    # Programmweiter Katalog
    "UpdateCatalogSymbolIntent",
    "AddCatalogSymbolIntent",
    "UpdateCompetenceIntent",
    "AddCompetenceIntent",
    # Grade
    "AddGradeColumnIntent",
    "DeleteGradeColumnIntent",
    "RecordGradeIntent",
    "ResolveGradeConflictsIntent",
    "SetGradeScaleIntent",
    "UpdateGradeWeightingIntent",
    # Abgaben
    "ApplyMissingSubmissionsIntent",
    "SetSubmissionStatusIntent",
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
