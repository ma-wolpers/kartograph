"""Helpers to make the shared bw-gui core importable from local submodule."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_bw_gui_on_path() -> None:
    """Add local bw-gui source path to sys.path when available."""

    repo_root = Path(__file__).resolve().parents[1]
    candidate = repo_root / "bw-gui" / "src"
    if not candidate.exists():
        return

    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)
