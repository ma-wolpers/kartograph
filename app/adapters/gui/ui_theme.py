"""Kartograph-specific theme builder.

Wraps bw_gui's canonical theme registry with Kartograph domain tokens
(teacher seat fill color and text color).  All other tokens come directly from
bw_gui and use standard bw_gui names — there is no local THEMES dict.

Re-exports ``normalize_theme_key`` and ``theme_names`` so callers that still
import from this module do not need to change their import statements.
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()

from bw_gui.theming import (
    THEME_ORDER,
    get_theme as _get_theme,
    normalize_theme_key as _normalize,
)

DEFAULT_THEME = "mono_day"

_TEACHER_FILL = "#9A6A24"
_TEACHER_TEXT = "#FFFFFF"


def kartograph_theme(theme_key: str | None = None) -> dict[str, str]:
    """Return the bw_gui theme dict extended with Kartograph-specific domain tokens.

    The returned dict contains every token from ``bw_gui.theming.get_theme()``
    (all standard palette tokens, semantic defaults, intensity scaling) plus two
    domain tokens:

    - ``teacher_fill``: Fixed warm-brown fill for the teacher's desk cell
      (``#9A6A24``).  Intentionally not theme-dependent — it should always be
      visually distinct from student desks.
    - ``teacher_text``: Foreground for text on the teacher desk (``#FFFFFF``).

    Note that student desks use ``accent_soft`` directly (no separate alias
    is needed since the standard bw_gui token is expressive enough).

    Args:
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None
                   or unknown.

    Returns:
        A new dict; the bw_gui registry is not mutated.
    """
    t = _get_theme(theme_key)
    return {**t, "teacher_fill": _TEACHER_FILL, "teacher_text": _TEACHER_TEXT}


def normalize_theme_key(value: str | None) -> str:
    """Return *value* if it is a known bw_gui theme key, otherwise ``DEFAULT_THEME``.

    Re-exported so callers in ``main_window.py`` do not need to update their
    import statements.
    """
    return _normalize(value)


def theme_names() -> list[str]:
    """Return the ordered list of available theme keys.

    Re-exported so ``_mixin_theme.ThemeMixin.toggle_theme()`` can continue to
    import from this module without change.  The list reflects ``bw_gui``'s
    canonical ``THEME_ORDER``.
    """
    return list(THEME_ORDER)
