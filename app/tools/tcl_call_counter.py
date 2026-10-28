"""Zählt die tatsächlichen Tcl/Tk-Aufrufe einer Aktion (einzige Zählstelle für Benchmarks und Budgets).

Jeder Tkinter-Widget-Aufruf landet in ``_tkinter.tkapp.call``; cProfile
zählt diese Aufrufe exakt, ohne Tkinter zu patchen. Deterministisch, daher
für Budget-Tests geeignet (anders als Zeitmessungen).
"""

from __future__ import annotations

import cProfile
import pstats
from typing import Callable

_TKAPP_CALL = "<method 'call' of '_tkinter.tkapp' objects>"


def count_tcl_calls(action: Callable[[], object]) -> int:
    """Führt *action* aus und gibt die Zahl der dabei abgesetzten Tcl-Aufrufe zurück.

    Args:
        action: Parameterlose Aktion, z. B. ein Navigationsschritt plus ``update()``.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        action()
    finally:
        profiler.disable()
    stats = pstats.Stats(profiler)
    return sum(entry[1] for key, entry in stats.stats.items() if key[2] == _TKAPP_CALL)
