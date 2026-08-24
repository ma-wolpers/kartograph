from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    last_deleted_plan: tuple[Path, SeatingPlan] | None = None  # zuletzt gelöschter Plan, für Undo
