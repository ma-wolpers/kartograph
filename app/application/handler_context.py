from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.core.domain.list_action_history import ListActionHistory
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.plan_history import PlanHistory
from app.core.domain.student_clipboard import StudentClipboard


@dataclass
class HandlerContext:
    """Externe Abhängigkeiten, die alle Handler gemeinsam nutzen.

    Wird einmalig im Controller erzeugt und per Closure an jeden Handler
    gebunden — die Handler-Signaturen bleiben dadurch 2-wertig (intent, state).
    """

    plan_repository: Any          # SeatingPlanRepository (v4-kompatibel)
    settings_repository: Any      # SettingsRepository
    history: PlanHistory
    default_plans_dir: Path       # Fallback, falls kein Ordner konfiguriert ist
    clipboard: StudentClipboard = field(default_factory=StudentClipboard)
    list_history: ListActionHistory = field(default_factory=ListActionHistory)
    # Optionaler GUI-seitiger Hook, den ``_record_and_save`` statt eines
    # sofortigen ``plan_repository.save_plan()`` aufruft (debounced Speichern,
    # siehe ``KartographAppController.set_plan_save_scheduler`` und
    # ``app/adapters/gui/_mixin_plan_save.py``). ``None`` (Standard, u. a. in
    # allen Tests ohne echte GUI) bedeutet: sofort synchron speichern wie
    # bisher — reines Opt-in, keine Verhaltensänderung ohne GUI-Wiring.
    plan_save_scheduler: Callable[[SeatingPlan, Path], None] | None = None
