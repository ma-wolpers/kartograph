"""Architektur-Guard: die App interpretiert Tk-Modifierbits (``event.state``) nicht selbst.

Die Prüflogik liegt zentral in bw-gui (``bw_gui.testing.tk_state_guard``) und wird
von allen Consumer-Repos sowie vom CI-Guardrail-Skript genutzt -- keine Kopie pro Repo.
"""

from __future__ import annotations

from pathlib import Path

from bw_gui.testing.tk_state_guard import RULE, find_offenders

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_app_does_not_interpret_tk_state_bits():
    offenders = find_offenders(REPO_ROOT / "app")
    assert offenders == {}, f"{RULE} Fundstellen: {offenders}"
