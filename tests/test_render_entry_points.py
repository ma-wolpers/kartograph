"""Architekturtest: das Raster wird nur über den Scheduler (oder apply_state) gezeichnet.

Direkte ``redraw_grid()``-Aufrufe aus beliebigem GUI-Code würden die
Bündelung pro Idle-Zyklus und die Auswahl-Ebene von ``apply_state`` umgehen.
Erlaubt sind nur die Render-Stelle selbst und ``apply_state``.
"""

from __future__ import annotations

import ast
from pathlib import Path

GUI = Path(__file__).resolve().parents[1] / "app" / "adapters" / "gui"
ALLOWED = {"_mixin_grid_render.py", "_mixin_state_apply.py"}


def test_redraw_grid_is_only_called_by_the_scheduler_and_apply_state():
    offenders = []
    for path in sorted(GUI.glob("*.py")):
        if path.name in ALLOWED:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == "redraw_grid":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []
