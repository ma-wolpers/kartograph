from __future__ import annotations

from app.adapters.gui.ui_intents import UiIntent


class MainWindowUiIntentController:
    def __init__(self, app: "KartographMainWindow"):
        self.app = app

    def handle_intent(self, intent: str) -> str | None:
        if intent == UiIntent.LIST_OPEN_SELECTED:
            self.app.open_selected_plan_from_list()
            return "break"
        if intent == UiIntent.NEW_PLAN:
            self.app.create_new_plan_dialog()
            return "break"
        if intent == UiIntent.RENAME_SELECTED_PLAN:
            self.app.rename_selected_plan_dialog()
            return "break"
        if intent == UiIntent.DELETE_SELECTED_PLAN:
            self.app.delete_selected_plan_dialog()
            return "break"
        if intent == UiIntent.DUPLICATE_SELECTED_PLAN:
            self.app.duplicate_selected_plan_dialog()
            return "break"
        if intent == UiIntent.OPEN_SETTINGS:
            self.app.open_settings_dialog()
            return "break"
        if intent == UiIntent.DELETE_DESK:
            self.app.delete_selected_desk()
            return "break"
        if intent == UiIntent.SET_TEACHER_DESK:
            self.app.set_selected_as_teacher_desk()
            return "break"
        if intent == UiIntent.ADD_SYMBOL:
            self.app.add_symbol_to_selected_desk_dialog()
            return "break"
        if intent == UiIntent.OPEN_TABLEGROUP_SETTINGS:
            self.app.open_tablegroup_settings_overlay()
            return "break"
        if intent == UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG:
            self.app.open_shortcut_runtime_debug_dialog()
            return "break"
        if intent == UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE:
            self.app.toggle_shortcut_runtime_offline()
            return "break"
        if intent == UiIntent.ESCAPE:
            self.app.handle_escape()
            return "break"
        if intent == UiIntent.CONFIRM_SELECTION:
            self.app.enter_name_edit_mode()
            return "break"
        if intent == UiIntent.MOVE_UP:
            self.app.move_selection(0, -1)
            return "break"
        if intent == UiIntent.MOVE_DOWN:
            self.app.move_selection(0, 1)
            return "break"
        if intent == UiIntent.MOVE_LEFT:
            self.app.move_selection(-1, 0)
            return "break"
        if intent == UiIntent.MOVE_RIGHT:
            self.app.move_selection(1, 0)
            return "break"
        if intent == UiIntent.ZOOM_IN:
            self.app.zoom_in()
            return "break"
        if intent == UiIntent.ZOOM_OUT:
            self.app.zoom_out()
            return "break"
        if intent == UiIntent.RESET_VIEW:
            self.app.reset_viewport()
            return "break"
        if intent == UiIntent.GO_TO_LIST:
            self.app.show_plan_list_view()
            return "break"
        if intent == UiIntent.VIEW_GRID:
            self.app.show_grid_surface()
            return "break"
        if intent == UiIntent.VIEW_DOCUMENTATION:
            self.app.show_documentation_surface()
            return "break"
        if intent == UiIntent.TOGGLE_DOCUMENTATION:
            self.app.toggle_documentation_surface()
            return "break"
        if intent == UiIntent.RENAME_DOCUMENTATION_DATE:
            self.app.rename_selected_documentation_date_dialog()
            return "break"
        if intent == UiIntent.ADD_GRADE_COLUMN:
            self.app.add_grade_column_dialog()
            return "break"
        if intent == UiIntent.TOGGLE_THEME:
            self.app.toggle_theme()
            return "break"
        if intent == UiIntent.EXPORT_PDF:
            self.app.export_plan_pdf_dialog()
            return "break"
        if intent == UiIntent.UNDO:
            self.app.undo_last_change()
            return "break"
        if intent == UiIntent.REDO:
            self.app.redo_last_change()
            return "break"
        if intent == UiIntent.UNDO_LAST_FIVE:
            self.app.undo_last_five_changes()
            return "break"
        if intent == UiIntent.COPY:
            self.app.copy_selection()
            return "break"
        if intent == UiIntent.CUT:
            self.app.cut_selection()
            return "break"
        if intent == UiIntent.PASTE:
            self.app.paste_selection()
            return "break"
        if intent == UiIntent.EXPAND_UP:
            self.app.expand_selection(0, -1)
            return "break"
        if intent == UiIntent.EXPAND_DOWN:
            self.app.expand_selection(0, 1)
            return "break"
        if intent == UiIntent.EXPAND_LEFT:
            self.app.expand_selection(-1, 0)
            return "break"
        if intent == UiIntent.EXPAND_RIGHT:
            self.app.expand_selection(1, 0)
            return "break"
        return None
