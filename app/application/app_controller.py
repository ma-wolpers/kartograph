"""KartographAppController — zentraler Application-Service-Layer.

Einziger Ort, der:
  - den ``IntentRegistry`` hält und alle Handler registriert,
  - den unveränderlichen ``AppState`` aktuell hält,
  - nach jeder Zustandsänderung den ``on_state_changed``-Callback aufruft.

Die GUI sendet ausschließlich ``dispatch(intent)``; sie liest ausschließlich
aus ``state``. Kein GUI-Code importiert dieses Modul direkt — der Controller
wird beim Start via ``wiring.py`` verdrahtet.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.intent_registry import IntentRegistry
from app.core.domain.plan_history import PlanHistory
from app.core.domain.settings import KartographSettings
from app.core.intents.base import Intent
from app.infrastructure.symbol_config_loader import load_symbol_definitions

# --- Handler-Imports --------------------------------------------------------
from app.application.handlers.accommodation_handlers import handle_set_accommodations
from app.application.handlers.color_handlers import handle_toggle_color
from app.application.handlers.custom_symbol_handlers import (
    handle_add_custom_symbol,
    handle_delete_custom_symbol,
    handle_update_custom_symbol,
)
from app.application.handlers.edit_handlers import (
    handle_copy_selection,
    handle_cut_selection,
    handle_paste_selection,
    handle_redo,
    handle_undo,
)
from app.application.handlers.grade_handlers import (
    handle_add_grade_column,
    handle_delete_grade_column,
    handle_record_grade,
    handle_update_grade_weighting,
)
from app.application.handlers.navigation_handlers import (
    handle_clear_selection,
    handle_move_selection,
    handle_select_cell,
)
from app.application.handlers.plan_handlers import (
    handle_archive_plan,
    handle_create_plan,
    handle_delete_plan,
    handle_duplicate_plan,
    handle_open_plan,
    handle_rename_plan,
    handle_restore_plan,
)
from app.application.handlers.session_handlers import (
    handle_add_session,
    handle_clear_doc_entry,
    handle_delete_session,
    handle_go_to_today,
    handle_navigate_session,
)
from app.application.handlers.student_handlers import (
    handle_create_student,
    handle_delete_student,
    handle_move_student,
    handle_rename_student,
    handle_set_nickname,
    handle_set_teacher_seat,
)
from app.application.handlers.participation_handlers import handle_set_participation_rating
from app.application.handlers.symbol_handlers import (
    handle_record_documentation_symbol,
    handle_toggle_diagnostic_symbol,
)
from app.application.handlers.view_handlers import (
    handle_export_namenfit_csv,
    handle_export_pdf,
    handle_export_student_pngs_zip,
    handle_open_settings,
    handle_open_tablegroup_settings,
    handle_reset_view,
    handle_set_editor_surface,
    handle_toggle_editor_surface,
    handle_update_settings,
    handle_zoom_in,
    handle_zoom_out,
)

# --- Intent-Imports ---------------------------------------------------------
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.color_intents import ToggleColorIntent
from app.core.intents.custom_symbol_intents import (
    AddCustomSymbolIntent,
    DeleteCustomSymbolIntent,
    UpdateCustomSymbolIntent,
)
from app.core.intents.edit_intents import (
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
    RedoIntent,
    UndoIntent,
)
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    RecordGradeIntent,
    UpdateGradeWeightingIntent,
)
from app.core.intents.navigation_intents import (
    ClearSelectionIntent,
    MoveSelectionIntent,
    SelectCellIntent,
)
from app.core.intents.participation_intents import SetParticipationRatingIntent
from app.core.intents.plan_intents import (
    ArchivePlanIntent,
    CreatePlanIntent,
    DeletePlanIntent,
    DuplicatePlanIntent,
    OpenPlanIntent,
    RenamePlanIntent,
    RestorePlanIntent,
)
from app.core.intents.session_intents import (
    AddSessionIntent,
    ClearDocEntryIntent,
    DeleteSessionIntent,
    GoToTodayIntent,
    NavigateSessionIntent,
)
from app.core.intents.student_intents import (
    CreateStudentIntent,
    DeleteStudentIntent,
    MoveStudentIntent,
    RenameStudentIntent,
    SetNicknameIntent,
    SetTeacherSeatIntent,
)
from app.core.intents.symbol_intents import (
    RecordDocumentationSymbolIntent,
    ToggleDiagnosticSymbolIntent,
)
from app.core.intents.view_intents import (
    ExportNamenfitCsvIntent,
    ExportPdfIntent,
    ExportStudentPngsZipIntent,
    OpenSettingsIntent,
    OpenTablegroupSettingsIntent,
    ResetViewIntent,
    SetEditorSurfaceIntent,
    ToggleEditorSurfaceIntent,
    UpdateSettingsIntent,
    ZoomInIntent,
    ZoomOutIntent,
)

_log = logging.getLogger("kartograph.app_controller")


class KartographAppController:
    """Zentraler Application-Service-Controller für Kartograph.

    Args:
        plan_repository:     v4-kompatibles ``SeatingPlanRepository``.
        settings_repository: ``SettingsRepository``-Implementierung.
        default_plans_dir:   Fallback-Verzeichnis für Plandateien, falls in
                             den Einstellungen kein Ordner konfiguriert ist.
        symbols_path:        Pfad zur Symbol-Konfigurationsdatei (einmalig beim
                             Start geladen, s. ``AppState.symbol_catalog``).
        on_state_changed:    Callback der GUI; wird nach jeder Zustandsänderung
                             mit dem neuen ``AppState`` aufgerufen.
    """

    def __init__(
        self,
        plan_repository: Any,
        settings_repository: Any,
        default_plans_dir: Path,
        symbols_path: Path,
        on_state_changed: Callable[[AppState], None],
    ) -> None:
        self._ctx = HandlerContext(
            plan_repository=plan_repository,
            settings_repository=settings_repository,
            history=PlanHistory(),
            default_plans_dir=default_plans_dir,
        )
        initial_settings = KartographSettings.from_dict(settings_repository.load_settings())
        symbol_definitions, self.symbol_catalog_warning = load_symbol_definitions(symbols_path)
        self._state: AppState = AppState(settings=initial_settings, symbol_catalog=tuple(symbol_definitions))
        self._on_state_changed = on_state_changed
        self._registry = IntentRegistry()
        self._register_handlers()

    # ------------------------------------------------------------------
    # Öffentliche Schnittstelle
    # ------------------------------------------------------------------

    @property
    def state(self) -> AppState:
        """Aktueller, unveränderlicher Anwendungszustand."""
        return self._state

    @property
    def plan_repository(self) -> Any:
        """Das verwendete ``SeatingPlanRepository`` (für GUI-Mixins, die noch nicht migriert sind)."""
        return self._ctx.plan_repository

    @property
    def settings_repository(self) -> Any:
        """Das verwendete ``SettingsRepository`` (für GUI-Mixins, die noch nicht migriert sind)."""
        return self._ctx.settings_repository

    @property
    def default_plans_dir(self) -> Path:
        """Fallback-Verzeichnis für Plandateien, falls nichts konfiguriert ist."""
        return self._ctx.default_plans_dir

    def replace_plan_in_state(self, plan) -> None:
        """Ersetzt den Plan im aktuellen State ohne History-Eintrag.

        Nur für GUI-seitige Vor-Mutations-Anpassungen (z. B. Farbpaletten-Bedeutung
        vor einem Toggle). Löst keinen on_state_changed-Callback aus.

        Args:
            plan: Plan, der den aktuellen ``current_plan`` im State ersetzt.
        """
        import dataclasses
        self._state = dataclasses.replace(self._state, current_plan=plan)

    def dispatch(self, intent: Intent) -> None:
        """Dispatcht *intent*, aktualisiert ``state`` und ruft den Callback.

        Gibt den alten State unverändert zurück, wenn kein Handler registriert
        ist oder der Handler einen Fehler wirft (wird vom Registry geloggt).
        Der Callback wird nur bei einer tatsächlichen Zustandsänderung aufgerufen.

        Args:
            intent: Auszuführender Intent.
        """
        new_state = self._registry.dispatch(intent, self._state)
        if new_state is not self._state:
            self._state = new_state
            try:
                self._on_state_changed(new_state)
            except Exception:
                _log.exception("on_state_changed-Callback hat eine Exception geworfen")

    # ------------------------------------------------------------------
    # Handler-Registrierung
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        """Registriert alle bekannten Intent-Typen mit ihrem jeweiligen Handler in der Registry.

        Jeder Handler wird als Lambda mit ``ctx`` (per Closure gebunden)
        eingetragen, damit die im ``IntentRegistry``-Aufruf erwartete
        2-stellige Signatur ``(intent, state)`` erhalten bleibt.
        """
        ctx = self._ctx
        r = self._registry

        # Plan
        r.register(OpenPlanIntent,       lambda i, s: handle_open_plan(i, s, ctx))
        r.register(CreatePlanIntent,     lambda i, s: handle_create_plan(i, s, ctx))
        r.register(RenamePlanIntent,     lambda i, s: handle_rename_plan(i, s, ctx))
        r.register(DeletePlanIntent,     lambda i, s: handle_delete_plan(i, s, ctx))
        r.register(DuplicatePlanIntent,  lambda i, s: handle_duplicate_plan(i, s, ctx))
        r.register(ArchivePlanIntent,    lambda i, s: handle_archive_plan(i, s, ctx))
        r.register(RestorePlanIntent,    lambda i, s: handle_restore_plan(i, s, ctx))

        # Student
        r.register(CreateStudentIntent,  lambda i, s: handle_create_student(i, s, ctx))
        r.register(MoveStudentIntent,    lambda i, s: handle_move_student(i, s, ctx))
        r.register(RenameStudentIntent,  lambda i, s: handle_rename_student(i, s, ctx))
        r.register(SetNicknameIntent,    lambda i, s: handle_set_nickname(i, s, ctx))
        r.register(DeleteStudentIntent,  lambda i, s: handle_delete_student(i, s, ctx))
        r.register(SetTeacherSeatIntent, lambda i, s: handle_set_teacher_seat(i, s, ctx))

        # Symbol
        r.register(ToggleDiagnosticSymbolIntent,    lambda i, s: handle_toggle_diagnostic_symbol(i, s, ctx))
        r.register(RecordDocumentationSymbolIntent, lambda i, s: handle_record_documentation_symbol(i, s, ctx))

        # Participation
        r.register(SetParticipationRatingIntent, lambda i, s: handle_set_participation_rating(i, s, ctx))

        # Color
        r.register(ToggleColorIntent, lambda i, s: handle_toggle_color(i, s, ctx))

        # Custom Symbol
        r.register(AddCustomSymbolIntent, lambda i, s: handle_add_custom_symbol(i, s, ctx))
        r.register(UpdateCustomSymbolIntent, lambda i, s: handle_update_custom_symbol(i, s, ctx))
        r.register(DeleteCustomSymbolIntent, lambda i, s: handle_delete_custom_symbol(i, s, ctx))

        # Accommodation
        r.register(SetAccommodationsIntent, lambda i, s: handle_set_accommodations(i, s, ctx))

        # Grade
        r.register(AddGradeColumnIntent,       lambda i, s: handle_add_grade_column(i, s, ctx))
        r.register(DeleteGradeColumnIntent,    lambda i, s: handle_delete_grade_column(i, s, ctx))
        r.register(RecordGradeIntent,          lambda i, s: handle_record_grade(i, s, ctx))
        r.register(UpdateGradeWeightingIntent, lambda i, s: handle_update_grade_weighting(i, s, ctx))

        # Session
        r.register(AddSessionIntent,         lambda i, s: handle_add_session(i, s, ctx))
        r.register(DeleteSessionIntent,      lambda i, s: handle_delete_session(i, s, ctx))
        r.register(NavigateSessionIntent,    lambda i, s: handle_navigate_session(i, s, ctx))
        r.register(GoToTodayIntent,          lambda i, s: handle_go_to_today(i, s, ctx))
        r.register(ClearDocEntryIntent,      lambda i, s: handle_clear_doc_entry(i, s, ctx))

        # Navigation
        r.register(SelectCellIntent,     lambda i, s: handle_select_cell(i, s, ctx))
        r.register(MoveSelectionIntent,  lambda i, s: handle_move_selection(i, s, ctx))
        r.register(ClearSelectionIntent, lambda i, s: handle_clear_selection(i, s, ctx))

        # Edit
        r.register(UndoIntent,           lambda i, s: handle_undo(i, s, ctx))
        r.register(RedoIntent,           lambda i, s: handle_redo(i, s, ctx))
        r.register(CopySelectionIntent,  lambda i, s: handle_copy_selection(i, s, ctx))
        r.register(CutSelectionIntent,   lambda i, s: handle_cut_selection(i, s, ctx))
        r.register(PasteSelectionIntent, lambda i, s: handle_paste_selection(i, s, ctx))

        # View
        r.register(SetEditorSurfaceIntent,       lambda i, s: handle_set_editor_surface(i, s, ctx))
        r.register(ToggleEditorSurfaceIntent,    lambda i, s: handle_toggle_editor_surface(i, s, ctx))
        r.register(ZoomInIntent,                 lambda i, s: handle_zoom_in(i, s, ctx))
        r.register(ZoomOutIntent,                lambda i, s: handle_zoom_out(i, s, ctx))
        r.register(ResetViewIntent,              lambda i, s: handle_reset_view(i, s, ctx))
        r.register(ExportPdfIntent,              lambda i, s: handle_export_pdf(i, s, ctx))
        r.register(ExportNamenfitCsvIntent,      lambda i, s: handle_export_namenfit_csv(i, s, ctx))
        r.register(ExportStudentPngsZipIntent,   lambda i, s: handle_export_student_pngs_zip(i, s, ctx))
        r.register(OpenSettingsIntent,           lambda i, s: handle_open_settings(i, s, ctx))
        r.register(UpdateSettingsIntent,         lambda i, s: handle_update_settings(i, s, ctx))
        r.register(OpenTablegroupSettingsIntent, lambda i, s: handle_open_tablegroup_settings(i, s, ctx))
