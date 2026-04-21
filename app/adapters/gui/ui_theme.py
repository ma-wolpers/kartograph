from __future__ import annotations

RAW_THEMES: dict[str, dict[str, str]] = {
    "mono_day": {
        "label": "Mono Day",
        "bg_main": "#F2F3F5",
        "bg_panel": "#E9EBEF",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DDE1E7",
        "fg_primary": "#111827",
        "fg_muted": "#4B5563",
        "accent": "#2563EB",
        "accent_soft": "#D6E3FF",
        "focus_ring": "#2563EB",
        "border": "#B9C0CB",
        "warning": "#D97706",
        "danger": "#DC2626",
    },
    "porcelain": {
        "label": "Porcelain",
        "bg_main": "#F8F9FA",
        "bg_panel": "#F0F2F5",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#E3E7ED",
        "fg_primary": "#111827",
        "fg_muted": "#5B6472",
        "accent": "#7C3AED",
        "accent_soft": "#E4DAFA",
        "focus_ring": "#7C3AED",
        "border": "#C5CCD8",
        "warning": "#D97706",
        "danger": "#DB2777",
    },
    "steel_morning": {
        "label": "Steel Morning",
        "bg_main": "#F4F4F5",
        "bg_panel": "#ECEDEF",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DEE1E5",
        "fg_primary": "#18181B",
        "fg_muted": "#52525B",
        "accent": "#0F766E",
        "accent_soft": "#CFECE8",
        "focus_ring": "#0F766E",
        "border": "#BDC3CC",
        "warning": "#CA8A04",
        "danger": "#BE123C",
    },
    "foglight": {
        "label": "Foglight",
        "bg_main": "#F5F6F8",
        "bg_panel": "#ECEFF3",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#E1E5EB",
        "fg_primary": "#111827",
        "fg_muted": "#5E6878",
        "accent": "#0284C7",
        "accent_soft": "#D7EAF6",
        "focus_ring": "#0284C7",
        "border": "#C0C7D2",
        "warning": "#B45309",
        "danger": "#BE123C",
    },
    "ledger": {
        "label": "Ledger",
        "bg_main": "#F3F3F2",
        "bg_panel": "#EBECEB",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DFE1DF",
        "fg_primary": "#171A17",
        "fg_muted": "#5A625C",
        "accent": "#1D4ED8",
        "accent_soft": "#D8E2FA",
        "focus_ring": "#1D4ED8",
        "border": "#C0C5BF",
        "warning": "#CA8A04",
        "danger": "#B91C1C",
    },
    "mono_night": {
        "label": "Mono Night",
        "bg_main": "#0F1115",
        "bg_panel": "#151922",
        "bg_surface": "#1C2230",
        "panel_strong": "#252D3D",
        "fg_primary": "#E5E7EB",
        "fg_muted": "#AAB0BD",
        "accent": "#3B82F6",
        "accent_soft": "#213450",
        "focus_ring": "#60A5FA",
        "border": "#3A4354",
        "warning": "#F59E0B",
        "danger": "#EF4444",
    },
    "graphite_core": {
        "label": "Graphite Core",
        "bg_main": "#121315",
        "bg_panel": "#191B1F",
        "bg_surface": "#21252B",
        "panel_strong": "#2A2F37",
        "fg_primary": "#ECEFF4",
        "fg_muted": "#AEB5C0",
        "accent": "#06B6D4",
        "accent_soft": "#203842",
        "focus_ring": "#22D3EE",
        "border": "#3A404A",
        "warning": "#F59E0B",
        "danger": "#F43F5E",
    },
    "charcoal": {
        "label": "Charcoal",
        "bg_main": "#101113",
        "bg_panel": "#171A1F",
        "bg_surface": "#1E232B",
        "panel_strong": "#282E38",
        "fg_primary": "#E8ECF3",
        "fg_muted": "#B0B8C6",
        "accent": "#3B82F6",
        "accent_soft": "#22364F",
        "focus_ring": "#60A5FA",
        "border": "#3A4250",
        "warning": "#F59E0B",
        "danger": "#EF4444",
    },
    "blackforge": {
        "label": "Blackforge",
        "bg_main": "#0B0C0E",
        "bg_panel": "#121418",
        "bg_surface": "#1A1E24",
        "panel_strong": "#242A33",
        "fg_primary": "#F0F3F8",
        "fg_muted": "#B8BFCC",
        "accent": "#06B6D4",
        "accent_soft": "#1E3740",
        "focus_ring": "#38BDF8",
        "border": "#394250",
        "warning": "#EAB308",
        "danger": "#F43F5E",
    },
}

DEFAULT_THEME = "mono_day"


def _map_theme(raw: dict[str, str]) -> dict[str, str]:
    teacher_fill = "#9A6A24"
    student_fill = raw.get("accent_soft", raw["bg_panel"])
    empty_fill = raw["bg_surface"]
    return {
        "label": raw.get("label", "Theme"),
        "bg_main": raw["bg_main"],
        "bg_panel": raw["bg_panel"],
        "panel_strong": raw["panel_strong"],
        "bg_surface": raw["bg_surface"],
        "bg_selected": raw.get("accent_soft", raw["bg_panel"]),
        "fg_main": raw["fg_primary"],
        "fg_muted": raw["fg_muted"],
        "grid_line": raw.get("border", raw["panel_strong"]),
        "teacher_fill": teacher_fill,
        "teacher_text": "#FFFFFF",
        "student_fill": student_fill,
        "empty_fill": empty_fill,
        "scroll_trough": raw["bg_surface"],
        "scroll_thumb": raw["panel_strong"],
        "scroll_thumb_active": raw.get("accent_soft", raw["bg_panel"]),
        "accent": raw["accent"],
        "focus_ring": raw["focus_ring"],
        "danger": raw.get("danger", "#C83A45"),
    }


THEMES: dict[str, dict[str, str]] = {name: _map_theme(data) for name, data in RAW_THEMES.items()}


def theme_names() -> list[str]:
    return list(THEMES.keys())


def normalize_theme_key(value: str | None) -> str:
    if value in THEMES:
        return value
    return DEFAULT_THEME
