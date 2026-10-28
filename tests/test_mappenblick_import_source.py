"""Mappenblick stammt aus dem Nachbar-Checkout (Editable-Installation), nie aus einer Kopie.

Kartograph bindet Mappenblick per ``-e ../../mappenblick`` in ``requirements.txt``
ein, ohne eigenen Pfad-Bootstrap. Dieser Test stellt sicher, dass der importierte
Code wirklich der des Mappenblick-Repos ist und keine Kopie in Kartograph liegt.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT = (REPO_ROOT / ".." / ".." / "mappenblick").resolve()


def test_mappenblick_is_imported_from_sibling_checkout():
    import mappenblick

    package_dir = Path(mappenblick.__file__).resolve().parent
    assert package_dir.parent == EXPECTED_ROOT
    assert not (REPO_ROOT / "mappenblick").exists()
