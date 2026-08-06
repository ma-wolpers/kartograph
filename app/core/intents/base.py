from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    """Basisklasse für alle UI-Aktionen."""
