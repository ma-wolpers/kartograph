"""Sitzplan-Vorschau-Popup für Kartograph.

Zeigt den Sitzplan ohne Noten, Symbole und Farben und aktualisiert sich
automatisch, wenn der Plan im Hauptfenster geändert wird.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import kartograph_theme
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.table_groups import build_seat_geometries_v4
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

_PADDING = 24


class SitzplanPopup:
    """Vorschaufenster: Sitzplan ohne Noten, Symbole und Farben."""

    def __init__(self, parent, theme_key: str = "mono_day", name_format: str = "Vorname Nachname") -> None:
        self._window = ui.Toplevel(parent)
        self._window.title("Sitzplan-Vorschau")
        self._window.geometry("860x640")
        self._theme_key = theme_key
        self._name_format = name_format
        self._plan: SeatingPlan | None = None
        self._flipped = False

        theme = kartograph_theme(theme_key)

        toolbar = ui.Frame(self._window, bg=theme["bg_panel"])
        toolbar.pack(fill="x", side="top")

        self._flip_btn = ui.Button(
            toolbar,
            text="Sicht umkehren",
            command=self._toggle_flip,
        )
        self._flip_btn.pack(side="left", padx=8, pady=4)

        self._canvas = ui.Canvas(
            self._window,
            bg=theme["bg_main"],
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._window.bind("<Configure>", lambda _e: self._window.after_idle(self._redraw))

    @property
    def window(self) -> ui.Toplevel:
        return self._window

    def update(self, plan: SeatingPlan | None, theme_key: str, name_format: str) -> None:
        """Aktualisiert Plan, Theme und Namensformat, dann neu zeichnen."""
        self._plan = plan
        self._theme_key = theme_key
        self._name_format = name_format
        theme = kartograph_theme(theme_key)
        self._canvas.configure(bg=theme["bg_main"])
        self._redraw()

    def _toggle_flip(self) -> None:
        self._flipped = not self._flipped
        self._redraw()

    def _redraw(self) -> None:
        self._canvas.delete("all")
        if not self._plan:
            return

        theme = kartograph_theme(self._theme_key)
        classroom = self._plan.classroom
        geometries = build_seat_geometries_v4(self._plan)

        # Collect all world points (with optional flip — same as pdf_exporter "teacher_top")
        all_points: list[tuple[float, float]] = []
        render_items = []
        for g in geometries:
            pts = list(g.polygon)
            cx, cy = g.center_x, g.center_y
            if self._flipped:
                pts = [(-px, -py) for px, py in pts]
                cx, cy = -cx, -cy
            render_items.append((pts, cx, cy, g))
            all_points.extend(pts)

        if not all_points:
            return

        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
        span_x = max(0.1, max_x - min_x)
        span_y = max(0.1, max_y - min_y)

        self._canvas.update_idletasks()
        cw = max(self._canvas.winfo_width(), 200)
        ch = max(self._canvas.winfo_height(), 200)

        avail_w = cw - 2 * _PADDING
        avail_h = ch - 2 * _PADDING
        cell = max(18, min(avail_w / span_x, avail_h / span_y))

        # Center the content
        origin_x = _PADDING + (avail_w - span_x * cell) / 2 - min_x * cell
        origin_y = _PADDING + (avail_h - span_y * cell) / 2 - min_y * cell

        name_fs = max(7, int(cell * 0.14))

        for pts, cx, cy, g in render_items:
            canvas_pts: list[float] = []
            py_vals: list[float] = []
            for wx, wy in pts:
                cpx = origin_x + wx * cell
                cpy = origin_y + wy * cell
                canvas_pts.extend((cpx, cpy))
                py_vals.append(cpy)

            fill = theme["teacher_fill"] if g.is_teacher else theme["accent_soft"]
            self._canvas.create_polygon(
                canvas_pts,
                fill=fill, outline=theme["border"], width=1,
            )

            label_cx = origin_x + cx * cell
            label_cy = (min(py_vals) + max(py_vals)) / 2

            if g.is_teacher:
                self._canvas.create_text(
                    label_cx, label_cy,
                    text="Lehrertisch",
                    fill=theme["teacher_text"],
                    font=("Segoe UI", max(7, int(cell * 0.12)), "bold"),
                )
            elif g.student is not None:
                name = self._format_name(g.student.first_name, g.student.last_name)
                if name:
                    self._canvas.create_text(
                        label_cx, label_cy,
                        text=name, fill=theme["fg_primary"],
                        font=("Segoe UI", name_fs, "bold"),
                    )

    def _format_name(self, first: str, last: str) -> str:
        first = first.strip()
        last = last.strip()
        if not first and not last:
            return ""
        fmt = self._name_format
        if fmt == "Vorname N":
            return f"{first} {last[0]}".strip() if (first and last) else (first or last)
        if fmt == "V. Nachname":
            return f"{first[0]}. {last}".strip() if (first and last) else (first or last)
        if fmt == "Nachname":
            return last or first
        return f"{first} {last}".strip() if (first and last) else (first or last)
