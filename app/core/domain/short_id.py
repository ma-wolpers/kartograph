"""Kurze, zufällige IDs für Planobjekte (SSOT der Form "8 Hex-Zeichen")."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4


def new_short_id(taken: Iterable[str] = (), *, prefix: str = "") -> str:
    """Erzeugt eine neue ID ``<prefix><8 hex>``, die nicht in *taken* vorkommt.

    Args:
        taken: Bereits vergebene IDs (inkl. Präfix).
        prefix: Optionales Präfix, z. B. ``"flag_"``.

    Returns:
        z. B. ``"3fa85f64"`` bzw. ``"flag_3fa85f64"``.
    """
    used = set(taken)
    while True:
        candidate = f"{prefix}{uuid4().hex[:8]}"
        if candidate not in used:
            return candidate
