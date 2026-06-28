"""Theme-Mixin für das Kartograph-Hauptfenster.

Stellt das Anwenden und Umschalten von Themes bereit, inklusive der
Stil-Konfiguration aller ttk-Widgets, Scrollbars, der Listbox sowie
der Hover-Tooltips und der Farbpunkt-Buttons.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import THEMES, normalize_theme_key, theme_names
from app.core.domain.settings import KartographSettings
from app.core.intents.view_intents import UpdateSettingsIntent


class ThemeMixin:
    """Mixin: Theme-Anwendung und Theme-Wechsel."""

    def _on_theme_changed(self) -> None:
        """Persistiert das in ``self.theme_var`` gewählte Theme über UpdateSettingsIntent (v4).

        ``apply_state`` übernimmt das neue Theme anschließend selbst in
        ``self.theme_key`` und ruft ``apply_theme()``/``redraw_grid()`` auf --
        diese Methode darf ``self.theme_key`` daher nicht selbst vorab setzen,
        sonst erkennt der Vergleich in ``apply_state`` keine Änderung mehr.
        """
        new_theme = normalize_theme_key(self.theme_var.get())
        self._settings["theme"] = new_theme
        self._controller.dispatch(UpdateSettingsIntent(settings=KartographSettings.from_dict(self._settings)))

    def toggle_theme(self) -> None:
        """Rotiert zum nächsten Theme in der Reihenfolge von theme_names() (v4: UpdateSettingsIntent)."""
        names = theme_names()
        current_index = names.index(self.theme_key) if self.theme_key in names else 0
        next_theme = names[(current_index + 1) % len(names)]
        self.theme_var.set(next_theme)
        self._on_theme_changed()

    def apply_theme(self) -> None:
        """Wendet das aktuelle Theme auf alle Widgets und Stile an."""
        theme = THEMES[self.theme_key]

        self.configure(bg=theme["bg_main"])
        self.style.configure("TFrame", background=theme["bg_panel"])
        self.style.configure("Main.TFrame", background=theme["bg_main"])
        self.style.configure("Panel.TFrame", background=theme["bg_panel"])
        self.style.configure("StrongPanel.TFrame", background=theme["panel_strong"])

        self.style.configure("TLabel", background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.configure("Main.TLabel", background=theme["bg_main"], foreground=theme["fg_main"])
        self.style.configure("Panel.TLabel", background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.configure("StrongPanel.TLabel", background=theme["panel_strong"], foreground=theme["fg_main"])

        self.style.configure("TButton", padding=(10, 6), background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.map("TButton", background=[("active", theme["bg_selected"])], foreground=[("active", theme["fg_main"])])

        self.style.configure("TEntry", fieldbackground=theme["bg_surface"], foreground=theme["fg_main"], insertcolor=theme["fg_main"])

        self.style.configure("Horizontal.TScrollbar", troughcolor=theme["scroll_trough"], background=theme["scroll_thumb"], bordercolor=theme["grid_line"], arrowcolor=theme["fg_muted"])
        self.style.map("Horizontal.TScrollbar", background=[("active", theme["scroll_thumb_active"])])
        self.style.configure("Vertical.TScrollbar", troughcolor=theme["scroll_trough"], background=theme["scroll_thumb"], bordercolor=theme["grid_line"], arrowcolor=theme["fg_muted"])
        self.style.map("Vertical.TScrollbar", background=[("active", theme["scroll_thumb_active"])])

        self.main_frame.configure(style="Main.TFrame")
        self.list_view.configure(style="Panel.TFrame")
        self.list_toolbar.configure(style="StrongPanel.TFrame")
        self.list_body.configure(style="Panel.TFrame")
        self.editor_view.configure(style="Panel.TFrame")
        self.editor_topbar.configure(style="StrongPanel.TFrame")
        self.grid_stack.configure(style="Panel.TFrame")
        self.grid_container.configure(style="Panel.TFrame")
        self.details_container.configure(style="Panel.TFrame")
        self.details_header.configure(style="Panel.TFrame")
        self.details_frame.configure(style="Panel.TFrame")
        self.docs_container.configure(style="Panel.TFrame")
        self.docs_toolbar.configure(style="StrongPanel.TFrame")
        self.docs_table_container.configure(style="Panel.TFrame")

        self.canvas.configure(bg=theme["bg_surface"])
        _scroll_kw = dict(
            bg=theme["scroll_thumb"],
            activebackground=theme["scroll_thumb_active"],
            troughcolor=theme["scroll_trough"],
            highlightbackground=theme["scroll_trough"],
            highlightcolor=theme["scroll_trough"],
            relief="flat",
            bd=0,
        )
        self.x_scroll.configure(**_scroll_kw)
        self.y_scroll.configure(**_scroll_kw)

        self.plan_listbox.configure(
            bg=theme["bg_panel"],
            fg=theme["fg_main"],
            selectbackground=theme["accent"],
            selectforeground="#FFFFFF",
            highlightbackground=theme["grid_line"],
            highlightcolor=theme["focus_ring"],
            borderwidth=1,
            relief="solid",
        )

        self.style.configure("Treeview", background=theme["bg_surface"], fieldbackground=theme["bg_surface"], foreground=theme["fg_main"], bordercolor=theme["grid_line"])
        self.style.configure("Treeview.Heading", background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.map("Treeview", background=[("selected", theme["accent"])], foreground=[("selected", "#FFFFFF")])

        if self._shared_menu_bar is not None:
            self._shared_menu_bar.refresh_theme(self._shared_menu_theme_key())

        shared_theme_key = self._shared_menu_theme_key()
        active_tooltips: list[object] = []
        for tooltip in self._hover_tooltips:
            owner = getattr(tooltip, "widget", None)
            if owner is None:
                continue
            try:
                if not int(owner.winfo_exists()):
                    continue
            except Exception:
                continue
            if hasattr(tooltip, "theme_key"):
                setattr(tooltip, "theme_key", shared_theme_key)
            active_tooltips.append(tooltip)
        self._hover_tooltips = active_tooltips

        self._apply_color_button_theme()

    def _apply_color_button_theme(self) -> None:
        """Passt Hintergrundfarben aller Farbpunkt-Buttons an das aktuelle Theme an."""
        theme = THEMES[self.theme_key]
        for button in self._color_marker_buttons:
            button.configure(
                bg=theme["bg_panel"],
                activebackground=theme["bg_selected"],
                activeforeground=theme["fg_main"],
                highlightbackground=theme["grid_line"],
                bd=1,
            )
