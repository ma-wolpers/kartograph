from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg_main": "#EEF3F8",
        "bg_panel": "#FFFFFF",
        "panel_strong": "#E1EAF4",
        "bg_surface": "#F7FAFD",
        "bg_selected": "#D7E7FF",
        "fg_main": "#1F2D3A",
        "fg_muted": "#617287",
        "grid_line": "#C8D5E4",
        "teacher_fill": "#F8DE94",
        "student_fill": "#D8ECD8",
        "empty_fill": "#FFFFFF",
        "accent": "#2B6FD9",
        "focus_ring": "#2B6FD9",
        "danger": "#C83A45",
    },
    "dark": {
        "bg_main": "#161E2A",
        "bg_panel": "#202B3B",
        "panel_strong": "#2A3750",
        "bg_surface": "#253247",
        "bg_selected": "#2E4E7C",
        "fg_main": "#EAF0F7",
        "fg_muted": "#A9B8CC",
        "grid_line": "#3B4F6A",
        "teacher_fill": "#796527",
        "student_fill": "#2F6147",
        "empty_fill": "#233044",
        "accent": "#7EB5FF",
        "focus_ring": "#7EB5FF",
        "danger": "#FF7A83",
    },
}

DEFAULT_THEME = "light"


def theme_names() -> list[str]:
    return list(THEMES.keys())


def normalize_theme_key(value: str | None) -> str:
    if value in THEMES:
        return value
    return DEFAULT_THEME
