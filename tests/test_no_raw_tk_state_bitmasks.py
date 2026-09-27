"""Architektur-Guard: die App interpretiert Tk-Modifierbits (``event.state``) nicht selbst.

Die Prüflogik liegt in ``tools/ci/tk_state_guard.py`` (auch vom CI-Guardrail-Skript
genutzt); dieser Test führt sie in der normalen Test-Suite aus.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_guard():
    spec = importlib.util.spec_from_file_location("tk_state_guard", REPO_ROOT / "tools" / "ci" / "tk_state_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def test_guard_detects_the_anti_pattern(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f(event):\n"
        "    a = event.state & 0x0008\n"
        "    b = int(getattr(event, 'state', 0)) & 4\n"
        "    c = flags & 0x10\n",
        encoding="utf-8",
    )
    assert guard.raw_state_bitmask_lines(sample) == [2, 3]


def test_app_does_not_interpret_tk_state_bits():
    offenders = guard.find_offenders(REPO_ROOT / "app")
    assert offenders == {}, f"{guard.RULE} Fundstellen: {offenders}"
