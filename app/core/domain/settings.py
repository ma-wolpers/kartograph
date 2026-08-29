"""Typisierte Kartograph-Einstellungen (ersetzt das freie Settings-Dict).

Lebt in ``app/core/domain/``, nicht in ``app/adapters/gui/``: Core- und
Application-Schicht dürfen nicht von der GUI abhängen. Default-Werte sind
deshalb als Literale dupliziert statt aus ``main_window_constants.py`` importiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CANVAS_RADIUS = 50
MIN_CANVAS_RADIUS = 1
MAX_CANVAS_RADIUS = 50
DEFAULT_SYMBOL_STRENGTH = 1
DEFAULT_VIEWPORT_FOLLOW_BUFFER = 0
DEFAULT_NAME_FORMAT = "Vorname Nachname"
NAME_FORMAT_OPTIONS = ("Vorname", "Vorname N", "Vorname Nachname", "V. Nachname", "Nachname")
DEFAULT_DETAILS_OVERLAY_POSITION = "bottom"
DEFAULT_TABLEGROUP_OVERLAY_POSITION = "right"
DEFAULT_THEME_KEY = "mono_day"
DEFAULT_SITZPLAN_POPUP_DELAY = 3
DEFAULT_SAVE_DELAY = 2.0
MIN_SAVE_DELAY = 0.3
MAX_SAVE_DELAY = 30.0


@dataclass(frozen=True)
class KartographSettings:
    """Typisierte, persistente Kartograph-Einstellungen.

    Ersetzt das vormals freie Dict aus ``JsonSettingsRepository.load_settings()``.
    """

    plans_dir: str = ""
    theme: str = DEFAULT_THEME_KEY
    canvas_radius: int = DEFAULT_CANVAS_RADIUS
    symbol_strength: int = DEFAULT_SYMBOL_STRENGTH
    viewport_follow_buffer: int = DEFAULT_VIEWPORT_FOLLOW_BUFFER
    name_format: str = DEFAULT_NAME_FORMAT
    disambiguate_colliding_names: bool = False
    grid_visible_symbols: tuple[str, ...] = field(default_factory=tuple)
    details_overlay_position: str = DEFAULT_DETAILS_OVERLAY_POSITION
    tablegroup_overlay_position: str = DEFAULT_TABLEGROUP_OVERLAY_POSITION
    sitzplan_popup_delay: int = DEFAULT_SITZPLAN_POPUP_DELAY
    save_delay: float = DEFAULT_SAVE_DELAY
    show_archived_plans: bool = False

    @classmethod
    def from_dict(cls, payload: dict) -> "KartographSettings":
        """Erstellt ``KartographSettings`` aus einem rohen Settings-Dict.

        Ungültige oder fehlende Werte werden defensiv durch Standardwerte
        ersetzt; das Theme wird nicht gegen die GUI-Theme-Registry validiert
        (das bleibt Aufgabe der GUI), nur grob in einen String normalisiert.

        Args:
            payload: Rohes Dict, z. B. aus ``SettingsRepository.load_settings()``.

        Returns:
            Validiertes ``KartographSettings``-Objekt.
        """
        if not isinstance(payload, dict):
            payload = {}

        def _int(value: object, default: int, *, minimum: int, maximum: int) -> int:
            try:
                parsed = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                parsed = default
            return max(minimum, min(maximum, parsed))

        def _float(value: object, default: float, *, minimum: float, maximum: float) -> float:
            try:
                parsed = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                parsed = default
            return max(minimum, min(maximum, parsed))

        def _str(value: object, default: str, *, options: tuple[str, ...] | None = None) -> str:
            text = str(value or "").strip()
            if not text:
                return default
            if options is not None and text not in options:
                return default
            return text

        def _bool(value: object, default: bool) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return default
            return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "ja"}

        grid_visible_raw = payload.get("grid_visible_symbols")
        grid_visible_symbols = (
            tuple(str(item).strip() for item in grid_visible_raw if str(item).strip())
            if isinstance(grid_visible_raw, list)
            else ()
        )

        return cls(
            plans_dir=str(payload.get("plans_dir") or ""),
            theme=_str(payload.get("theme"), DEFAULT_THEME_KEY),
            canvas_radius=_int(payload.get("canvas_radius"), DEFAULT_CANVAS_RADIUS, minimum=MIN_CANVAS_RADIUS, maximum=MAX_CANVAS_RADIUS),
            symbol_strength=_int(payload.get("symbol_strength"), DEFAULT_SYMBOL_STRENGTH, minimum=0, maximum=2),
            viewport_follow_buffer=_int(payload.get("viewport_follow_buffer"), DEFAULT_VIEWPORT_FOLLOW_BUFFER, minimum=0, maximum=5),
            name_format=_str(
                payload.get("name_format") or payload.get("grid_name_format"),
                DEFAULT_NAME_FORMAT,
                options=NAME_FORMAT_OPTIONS,
            ),
            disambiguate_colliding_names=_bool(payload.get("disambiguate_colliding_names"), False),
            grid_visible_symbols=grid_visible_symbols,
            details_overlay_position=_str(payload.get("details_overlay_position"), DEFAULT_DETAILS_OVERLAY_POSITION, options=("left", "right", "bottom")),
            tablegroup_overlay_position=_str(payload.get("tablegroup_overlay_position"), DEFAULT_TABLEGROUP_OVERLAY_POSITION, options=("left", "right", "bottom")),
            sitzplan_popup_delay=_int(payload.get("sitzplan_popup_delay"), DEFAULT_SITZPLAN_POPUP_DELAY, minimum=1, maximum=30),
            # "save_delay" ersetzt das fruehere, nur namensbezogene "name_save_delay"
            # (jetzt auch fuer Noten-/Symbol-/Farb-Edits genutzt, s. _mixin_plan_save.py) —
            # alte Settings-Dateien lesen den frueheren Schluessel als Fallback, damit ein
            # bereits gesetzter Wert nicht stillschweigend auf den Standard zurueckfaellt.
            save_delay=_float(
                payload.get("save_delay", payload.get("name_save_delay")),
                DEFAULT_SAVE_DELAY,
                minimum=MIN_SAVE_DELAY,
                maximum=MAX_SAVE_DELAY,
            ),
            show_archived_plans=_bool(payload.get("show_archived_plans"), False),
        )

    def to_dict(self) -> dict:
        """Wandelt die Einstellungen in ein JSON-kompatibles Dict um.

        Returns:
            Dict, das via ``SettingsRepository.save_settings()`` persistiert werden kann.
        """
        return {
            "plans_dir": self.plans_dir,
            "theme": self.theme,
            "canvas_radius": self.canvas_radius,
            "symbol_strength": self.symbol_strength,
            "viewport_follow_buffer": self.viewport_follow_buffer,
            "name_format": self.name_format,
            "disambiguate_colliding_names": self.disambiguate_colliding_names,
            "grid_visible_symbols": list(self.grid_visible_symbols),
            "details_overlay_position": self.details_overlay_position,
            "tablegroup_overlay_position": self.tablegroup_overlay_position,
            "sitzplan_popup_delay": self.sitzplan_popup_delay,
            "save_delay": self.save_delay,
            "show_archived_plans": self.show_archived_plans,
        }


def resolve_plans_dir(raw: str, default: Path) -> Path:
    """Liefert den konfigurierten Plan-Ordner, sonst *default*.

    Einzige Stelle, die "konfiguriert oder Standard" für den Plan-Ordner
    entscheidet — wird sowohl von der Handler-Schicht (mit
    ``KartographSettings.plans_dir``) als auch von GUI-Code (teils mit
    rohem Dialog-Text) genutzt, damit diese Logik nicht mehrfach dupliziert
    auseinanderlaufen kann.

    Args:
        raw: Roher, konfigurierter Ordnerpfad (leer, wenn nichts gesetzt ist).
        default: Fallback, falls *raw* leer ist.
    """
    text = (raw or "").strip()
    return Path(text) if text else default
