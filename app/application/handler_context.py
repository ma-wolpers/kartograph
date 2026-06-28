from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    plans_dir: Path
    clipboard: StudentClipboard = field(default_factory=StudentClipboard)
