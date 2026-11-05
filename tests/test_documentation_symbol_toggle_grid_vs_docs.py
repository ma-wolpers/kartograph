"""Tests: Ziel von Doku-Aktionen (Raster vs. Dokuansicht) und der gemeinsame Toggle-Kern.

Einzige Regel fuer Schueler und Datum ist ``_doc_action_target()``: Raster
(kein Datums-Waehler) -> markierter Tisch heute; Dokuansicht -> ausgewaehlte
Zeile am Datumsanker, auch wenn das ein Datum in der Vergangenheit ist.
Doku-Symbole, Diagnosesymbole und Mitarbeit (+/o/-) nutzen alle diese Regel;
die Leertaste hat keine eigene Datumslogik, sie laeuft ueber denselben
generischen Pfad (_on_symbol_shortcut) wie jedes andere Kuerzel.

Nutzt das etablierte Test-Double-Muster aus
tests/test_main_window_documentation_only_symbols.py:
KartographMainWindow.__new__(...) + gezielt befuellte Instanzattribute,
kein echtes Tk noetig.
"""

from __future__ import annotations

from datetime import date

from app.adapters.gui.doc_action_target import DocActionTarget
from app.adapters.gui.main_window import KartographMainWindow
from app.core.domain.plan_selection import RectSelection
from app.core.usecases.v4.symbol_usecases import record_symbol
from tests.conftest import make_plan, make_student

DOC_SYMBOL = "Nicht abgegeben / verweigert"
DIAGNOSTIC_SYMBOL = "Beteiligung"
PAST_DATE = "2020-01-01"
TODAY = date.today().isoformat()


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


def _grid_window(*, students, cell=(0, 0), selection=None) -> KartographMainWindow:
    """Raster mit Einzelauswahl auf *cell* (oder der uebergebenen *selection*)."""
    window = _window(plan=make_plan(students=students))
    window.__dict__["_editor_surface"] = "grid"
    window.__dict__["selection"] = selection or RectSelection(*cell)
    window.__dict__["selected_cell"] = cell
    return window


def _docs_window(*, dates: list[str], selected_index: int) -> KartographMainWindow:
    """Dokuansicht mit einer benannten Zeile und Datumsanker auf *selected_index*."""
    window = _window(plan=make_plan(students=[make_student(x=0, y=0)]))
    window.__dict__["_editor_surface"] = "docs"
    window.__dict__["_doc_student_coords"] = [(0, 0)]
    window.__dict__["_doc_selected_student_index"] = 0
    window.__dict__["_doc_dates"] = dates
    window.__dict__["_doc_selected_date_index"] = selected_index
    return window


class TestDocActionTarget:
    """Die eine Regel: wer und welches Datum, je nach aktiver Oberflaeche."""

    def test_docs_uses_selected_past_date_column(self):
        window = _docs_window(dates=[PAST_DATE, TODAY], selected_index=0)

        target = window._doc_action_target("Symbole")

        assert target == DocActionTarget(window.current_plan.student_at(0, 0).student_id, PAST_DATE)

    def test_docs_without_date_columns_has_no_target(self):
        window = _docs_window(dates=[], selected_index=0)

        assert window._doc_action_target("Symbole") is None

    def test_grid_uses_selected_desk_today(self):
        student = make_student(x=2, y=3)
        window = _grid_window(students=[student], cell=(2, 3))

        assert window._doc_action_target("Symbole") == DocActionTarget(student.student_id, TODAY)

    def test_grid_without_single_selection_reports_status(self):
        selection = RectSelection(0, 0)
        selection.set_focus(1, 0)
        window = _grid_window(students=[make_student(x=0, y=0)], selection=selection)

        assert window._doc_action_target("Mitarbeit-Bewertung") is None
        assert window.status_var.value == "Mitarbeit-Bewertung nur bei Einzelauswahl"

    def test_grid_empty_desk_reports_status(self):
        window = _grid_window(students=[])

        assert window._doc_action_target("Symbole") is None
        assert window.status_var.value == "Symbole nur für Schülertische"


class TestToggleDocumentationSymbolAt:
    """Der gemeinsame Toggle-Kern, unabhaengig von Raster/Dokuansicht."""

    def test_documentation_symbol_zero_to_one(self):
        student = make_student()
        window = _window(plan=make_plan(students=[student]))

        window._toggle_documentation_symbol_at(DocActionTarget(student.student_id, "2026-01-15"), DOC_SYMBOL)

        intent = window._controller.dispatched[-1]
        assert intent.strength == 1
        assert intent.date == "2026-01-15"
        assert intent.symbol == DOC_SYMBOL
        assert intent.student_id == student.student_id

    def test_documentation_symbol_one_to_zero(self):
        student = make_student()
        plan = record_symbol(make_plan(students=[student]), student.student_id, "2026-01-15", DOC_SYMBOL, 1)
        window = _window(plan=plan)

        window._toggle_documentation_symbol_at(DocActionTarget(student.student_id, "2026-01-15"), DOC_SYMBOL)

        assert window._controller.dispatched[-1].strength == 0

    def test_diagnostic_symbol_cycles_instead_of_toggling_binary(self):
        student = make_student()
        plan = record_symbol(make_plan(students=[student]), student.student_id, "2026-01-15", DIAGNOSTIC_SYMBOL, 2)
        window = _window(plan=plan, diagnostic_symbol_catalog=[DIAGNOSTIC_SYMBOL])

        window._toggle_documentation_symbol_at(DocActionTarget(student.student_id, "2026-01-15"), DIAGNOSTIC_SYMBOL)

        assert window._controller.dispatched[-1].strength == 3


class TestToggleDocumentationSymbolPerSurface:
    """Raster wirkt auf heute, Dokuansicht auf die dort gewaehlte Datumsspalte."""

    def test_grid_toggles_for_today(self):
        student = make_student(x=2, y=3)
        window = _grid_window(students=[student], cell=(2, 3))

        window._toggle_documentation_symbol(DOC_SYMBOL)

        intent = window._controller.dispatched[-1]
        assert (intent.date, intent.student_id, intent.strength) == (TODAY, student.student_id, 1)

    def test_grid_no_toggle_for_empty_desk(self):
        window = _grid_window(students=[])

        window._toggle_documentation_symbol(DOC_SYMBOL)

        assert window._controller.dispatched == []

    def test_docs_uses_selected_past_date_column_not_today(self):
        window = _docs_window(dates=[PAST_DATE, TODAY], selected_index=0)

        window._toggle_documentation_symbol(DOC_SYMBOL)

        assert window._controller.dispatched[-1].date == PAST_DATE

    def test_docs_uses_today_column_when_that_column_is_selected(self):
        window = _docs_window(dates=[PAST_DATE, TODAY], selected_index=1)

        window._toggle_documentation_symbol(DOC_SYMBOL)

        assert window._controller.dispatched[-1].date == TODAY


class TestParticipationRatingPerSurface:
    """Mitarbeit (+/o/-) folgt derselben Regel wie Symbole.

    Regression: in der Dokuansicht landete die Bewertung immer in der heutigen
    (= neuesten) Spalte, weil der Doku-Pfad heute statt des Datumsankers nutzte.
    """

    def test_docs_uses_selected_past_date_column_not_today(self):
        window = _docs_window(dates=[PAST_DATE, TODAY], selected_index=0)

        window._set_participation_rating("+")

        intent = window._controller.dispatched[-1]
        assert (intent.date, intent.rating) == (PAST_DATE, "+")

    def test_grid_rates_today(self):
        student = make_student(x=1, y=1)
        window = _grid_window(students=[student], cell=(1, 1))

        window._set_participation_rating("o")

        intent = window._controller.dispatched[-1]
        assert (intent.date, intent.student_id) == (TODAY, student.student_id)

    def test_no_dispatch_without_date_columns(self):
        window = _docs_window(dates=[], selected_index=0)

        window._set_participation_rating("o")

        assert window._controller.dispatched == []


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
