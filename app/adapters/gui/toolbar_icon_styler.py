"""Laedt die Toolbar-PNG-Icons und erzeugt theme-faehige Icon-Buttons.

Icons liegen in ``assets/toolbar`` (Quelle/Lizenz: ``ICONS_LICENSE.md`` dort).
Das eigentliche Einfaerben je Theme sowie die Registrierung fuer automatische
Neueinfaerbung bei Theme-Wechseln passiert vollstaendig in bw_gui's
``icon_button()`` (Strict bw-gui-only-Policy, siehe AGENTS.md Regel 6).
"""

from __future__ import annotations

from pathlib import Path

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.theming import icon_button

# Ordnet jeden Toolbar-Aktionsschluessel seiner PNG-Datei in assets/toolbar zu.
_ICON_FILE_BY_KEY: dict[str, str] = {
    "new_plan": "tb_new_plan.png",
    "open_plan": "tb_open_plan.png",
    "rename_plan": "tb_rename_plan.png",
    "delete_plan": "tb_delete.png",
    "duplicate_plan": "tb_duplicate_plan.png",
    "go_to_list": "tb_back_to_list.png",
    "delete_desk": "tb_delete.png",
    "add_symbol": "tb_add_symbol.png",
    "tablegroup_settings": "tb_tablegroup_settings.png",
    "export_pdf": "tb_export_pdf.png",
    "export_namenfit_csv": "tb_export_namenfit_csv.png",
    "teacher_desk": "tb_teacher_desk.png",
    "toggle_documentation": "tb_toggle_docs.png",
    "symbol_filter": "tb_symbol_filter.png",
    "zoom_out": "tb_zoom_out.png",
    "zoom_in": "tb_zoom_in.png",
}


def _icon_dir() -> Path:
    """Gibt den absoluten Pfad zum Toolbar-Assets-Ordner zurueck."""
    return Path(__file__).resolve().parents[3] / "assets" / "toolbar"


class ToolbarIconStyler:
    """Laedt und cached die Basis-Icons und erstellt daraus Icon-Buttons.

    Jeder erzeugte Button wird ueber bw_gui's ``icon_button()`` bei jedem
    Theme-Wechsel automatisch neu eingefaerbt; diese Klasse selbst haelt nur
    die rohen, ungefaerbten ``PhotoImage``-Basisbilder vor.
    """

    def __init__(self) -> None:
        self._base_icons: dict[str, ui.PhotoImage] = {}
        self._loaded = False

    def _ensure_base_icons(self) -> None:
        """Laedt beim ersten Aufruf alle vorhandenen PNG-Icons von der Platte."""
        if self._loaded:
            return
        self._loaded = True
        icon_dir = _icon_dir()
        for icon_key, filename in _ICON_FILE_BY_KEY.items():
            icon_path = icon_dir / filename
            if not icon_path.exists() or not icon_path.is_file():
                continue
            try:
                self._base_icons[icon_key] = ui.PhotoImage(file=str(icon_path))
            except ui.TclError:
                continue

    def create_button(self, parent: ui.Widget, icon_key: str, command):
        """Erstellt einen theme-faehigen Icon-Button fuer *icon_key*.

        Args:
            parent: Eltern-Widget fuer den neuen Button.
            icon_key: Schluessel in ``_ICON_FILE_BY_KEY``.
            command: Callback, der beim Klick ausgefuehrt wird.

        Returns:
            Der erstellte ``ttk.Button``, oder ``None`` falls kein Icon-Asset
            gefunden wurde (Aufrufer faellt dann auf Text-Caption zurueck).
        """
        self._ensure_base_icons()
        base = self._base_icons.get(icon_key)
        if base is None:
            return None
        return icon_button(parent, base, command)
