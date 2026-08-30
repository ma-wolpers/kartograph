"""Tests: gemeinsamer Doku-Symbol-Toggle-Kern und die Datumssemantik von Raster vs. Dokuansicht.

Raster hat keinen Datums-Waehler -> wirkt immer auf heute
(_toggle_documentation_symbol_today_grid). Dokuansicht wirkt auf die dort
ausgewaehlte Datumsspalte, auch wenn das ein Datum in der Vergangenheit ist
(_toggle_documentation_symbol), unveraendert seit der Umstellung der
Leertaste auf den katalogbasierten Resolver -- die Leertaste hat keine
eigene Datumslogik mehr, sie laeuft ueber denselben generischen Pfad
(_on_symbol_shortcut) wie jedes andere Kuerzel.

Nutzt das etablierte Test-Double-Muster aus
tests/test_main_window_documentation_only_symbols.py:
KartographMainWindow.__new__(...) + gezielt befuellte Instanzattribute,
kein echtes Tk noetig.
"""

from __future__ import annotations

from app.adapters.gui.main_window import KartographMainWindow
from app.core.domain.plan_selection import RectSelection
from app.core.usecases.v4.symbol_usecases import record_symbol
from tests.conftest import make_plan, make_student

DOC_SYMBOL = "Nicht abgegeben / verweigert"
DIAGNOSTIC_SYMBOL = "Beteiligung"


class _RecordingController:
    """Test-Double: zeichnet dispatchte Intents auf, statt sie auszufuehren."""

    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, intent: object) -> None:
        self.dispatched.append(intent)


class _FakeStatusVar:
    """Test-Double fuer ui.StringVar: nur .set() wird von den Guards gebraucht."""

    def __init__(self) -> None:
        self.value: str | None = None

    def set(self, value: str) -> None:
        self.value = value


def _window(*, plan, diagnostic_symbol_catalog=None) -> KartographMainWindow:
    window = KartographMainWindow.__new__(KartographMainWindow)
    window.__dict__["current_plan"] = plan
    window.__dict__["_controller"] = _RecordingController()
    window.__dict__["diagnostic_symbol_catalog"] = diagnostic_symbol_catalog or []
    window.__dict__["status_var"] = _FakeStatusVar()
    return window


class TestToggleDocumentationSymbolForStudent:
    """Der gemeinsame Toggle-Kern, unabhaengig von Raster/Dokuansicht."""

    def test_documentation_symbol_zero_to_one(self):
        student = make_student()
        window = _window(plan=make_plan(students=[student]))

        window._toggle_documentation_symbol_for_student(student, DOC_SYMBOL, "2026-01-15")

        intent = window._controller.dispatched[-1]
        assert intent.strength == 1
        assert intent.date == "2026-01-15"
        assert intent.symbol == DOC_SYMBOL
        assert intent.student_id == student.student_id

    def test_documentation_symbol_one_to_zero(self):
        student = make_student()
        plan = record_symbol(make_plan(students=[student]), student.student_id, "2026-01-15", DOC_SYMBOL, 1)
        window = _window(plan=plan)

        window._toggle_documentation_symbol_for_student(student, DOC_SYMBOL, "2026-01-15")

        assert window._controller.dispatched[-1].strength == 0

    def test_diagnostic_symbol_cycles_instead_of_toggling_binary(self):
        student = make_student()
        plan = record_symbol(make_plan(students=[student]), student.student_id, "2026-01-15", DIAGNOSTIC_SYMBOL, 2)
        window = _window(plan=plan, diagnostic_symbol_catalog=[DIAGNOSTIC_SYMBOL])

        window._toggle_documentation_symbol_for_student(student, DIAGNOSTIC_SYMBOL, "2026-01-15")

        assert window._controller.dispatched[-1].strength == 3


class TestToggleDocumentationSymbolTodayGrid:
    """Raster: kein Datums-Waehler -> wirkt immer auf das heutige Datum."""

    def test_toggles_for_today_using_grid_selected_student(self):
        student = make_student(x=2, y=3)
        window = _window(plan=make_plan(students=[student]))
        window.__dict__["selection"] = RectSelection(2, 3)
        window.__dict__["selected_cell"] = (2, 3)

        window._toggle_documentation_symbol_today_grid(DOC_SYMBOL)

        intent = window._controller.dispatched[-1]
        assert intent.date == window._today_doc_date()
        assert intent.student_id == student.student_id
        assert intent.strength == 1

    def test_no_toggle_without_single_selection(self):
        student = make_student(x=0, y=0)
        window = _window(plan=make_plan(students=[student]))
        selection = RectSelection(0, 0)
        selection.set_focus(1, 0)
        window.__dict__["selection"] = selection

        window._toggle_documentation_symbol_today_grid(DOC_SYMBOL)

        assert window._controller.dispatched == []

    def test_no_toggle_for_empty_desk(self):
        window = _window(plan=make_plan(students=[]))
        window.__dict__["selection"] = RectSelection(0, 0)
        window.__dict__["selected_cell"] = (0, 0)

        window._toggle_documentation_symbol_today_grid(DOC_SYMBOL)

        assert window._controller.dispatched == []


class TestToggleDocumentationSymbolDocsUsesSelectedColumn:
    """Dokuansicht: wirkt auf die dort gewaehlte Datumsspalte, nicht auf heute."""

    def test_uses_selected_past_date_column_not_today(self):
        student = make_student(x=0, y=0)
        window = _window(plan=make_plan(students=[student]))
        past_date = "2020-01-01"
        window.__dict__["_doc_student_coords"] = [(0, 0)]
        window.__dict__["_doc_selected_student_index"] = 0
        window.__dict__["_doc_dates"] = [past_date, window._today_doc_date()]
        window.__dict__["_doc_selected_date_index"] = 0
        window._refresh_documentation_table = lambda: None  # Tk-freie Isolierung

        window._toggle_documentation_symbol(DOC_SYMBOL)

        intent = window._controller.dispatched[-1]
        assert intent.date == past_date
        assert intent.date != window._today_doc_date()

    def test_uses_today_column_when_that_column_is_selected(self):
        student = make_student(x=0, y=0)
        window = _window(plan=make_plan(students=[student]))
        today = window._today_doc_date()
        window.__dict__["_doc_student_coords"] = [(0, 0)]
        window.__dict__["_doc_selected_student_index"] = 0
        window.__dict__["_doc_dates"] = ["2020-01-01", today]
        window.__dict__["_doc_selected_date_index"] = 1
        window._refresh_documentation_table = lambda: None

        window._toggle_documentation_symbol(DOC_SYMBOL)

        assert window._controller.dispatched[-1].date == today


class TestOnSpaceSymbolShortcutDelegation:
    """_on_space_symbol_shortcut hat keine eigene Fachlogik mehr -- reiner Resolver+Delegator
    an _on_symbol_shortcut(), welches Symbol (falls ueberhaupt eines) die Leertaste
    bedient, ergibt sich ausschliesslich aus der Katalog-Map self._shortcut_to_symbol."""

    def test_delegates_to_on_symbol_shortcut_with_resolved_symbol(self):
        window = KartographMainWindow.__new__(KartographMainWindow)
        window.__dict__["_shortcut_to_symbol"] = {"space": "Abwesend"}
        received: dict[str, object] = {}

        def fake_on_symbol_shortcut(event, symbol_name):
            received["event"] = event
            received["symbol_name"] = symbol_name
            return "break"

        window._on_symbol_shortcut = fake_on_symbol_shortcut
        sentinel_event = object()

        result = window._on_space_symbol_shortcut(sentinel_event)

        assert result == "break"
        assert received["symbol_name"] == "Abwesend"
        assert received["event"] is sentinel_event

    def test_delegates_with_none_when_no_symbol_claims_space(self):
        window = KartographMainWindow.__new__(KartographMainWindow)
        window.__dict__["_shortcut_to_symbol"] = {"x": DOC_SYMBOL}
        received: dict[str, object] = {}
        window._on_symbol_shortcut = lambda event, symbol_name: received.setdefault("symbol_name", symbol_name)

        window._on_space_symbol_shortcut(object())

        assert received["symbol_name"] is None


class TestOnSymbolShortcutNoneGuard:
    """_on_symbol_shortcut() muss ein nicht konfiguriertes Leertaste-Symbol (None) sauber ignorieren."""

    def test_returns_none_immediately_when_symbol_name_is_none(self):
        window = KartographMainWindow.__new__(KartographMainWindow)

        class _FakeEvent:
            state = 0

        assert window._on_symbol_shortcut(_FakeEvent(), None) is None
