# Kartograph — Architekturplan v2

> Ziel: Strikte GUI/Logik-Trennung, typisiertes Intent-System mit sauberem Wiring,
> neue JSON-Struktur (v4) mit Studenten-IDs und Session-basierter Dokumentation.
> Rückwärtskompatibilität ausschließlich über ein Migrationsskript.

---

## 0. Ausgangslage & Probleme der aktuellen Architektur

### 0.1 GUI/Logik-Vermischung in den Mixins

Jede Mixin-Methode enthält heute vier Belange in einem Block:

```python
# _mixin_edit.py — aktueller Zustand (Beispiel)
def _toggle_selected_color(self, color_key: str) -> None:
    # 1. Input-Guard (Logik)
    if not self.selection.is_single():
        self.status_var.set("Farbpunkte nur bei Einzelauswahl")
        return
    # 2. Usecase-Aufruf (Logik)
    next_plan = toggle_color_marker(self.current_plan, x, y, color_key)
    # 3. Persistenz + History (Logik)
    self._record_and_save(next_plan, "color.toggle", ...)
    # 4. UI-Update (Präsentation)
    self.redraw_grid()
    self._refresh_details_panel()
```

**Problem:** GUI-Widget kennt Domänenregeln; Usecase-Aufrufe sind über 30 Mixins
verstreut; kein zentraler Ort für "was passiert wenn Intent X ausgelöst wird".

### 0.2 Intent-System: String-Konstanten + if/elif-Kette

```python
# ui_intent_controller.py — 128-zeiliger if/elif-Block
def handle_intent(self, intent: str) -> str | None:
    if intent == UiIntent.DELETE_DESK:
        self.app.delete_selected_desk()
    elif intent == UiIntent.UNDO:
        self.app.undo_last_change()
    elif ...  # × 54 Zweige
```

**Problem:** Keine Typsicherheit, keine Parameter in Intents, keine Registry
(kein Hinzufügen ohne Änderung der Kette), keine Testbarkeit.

### 0.3 JSON-Struktur (v3): Dokumentation im Desk, Geometrie im Desk

```json
// v3 — Dokumentation ist tief im Desk vergraben
{
  "desks": [
    {
      "x": 3, "y": 1,
      "documentation_entries": {          // ← nested 3 Ebenen tief
        "2025-09-01": { "symbols": {}, "grades": {}, "note": "" }
      },
      "tablegroup_shift_x": 0.05,         // ← Tischgruppen-Geometrie im Desk
      "tablegroup_shift_y": -0.03,
      "tablegroup_rotation": 2.5
    }
  ]
}
```

**Probleme:**
- „Was passierte am 01.09.?" → alle Desks iterieren
- Schüler haben keine stabile ID → Sitzwechsel invalidiert gesamte Dokumentation
- Tischgruppen-Geometrie redundant pro Desk statt einmal pro Gruppe
- Keine Plan-Metadaten (Schuljahr, Erstelldatum)
- Farbe + Bedeutung in getrennten Strukturen statt eines kohärenten Palette-Eintrags

---

## 1. Neue JSON-Struktur (Format v4)

### 1.1 Designziele

| Ziel | Mechanismus |
|------|-------------|
| Schüler mit stabiler ID | `student_id: UUID` unabhängig vom Sitzplatz |
| Dokumentation als Sessions | `sessions[].entries[student_id]` statt `desk.documentation_entries[date]` |
| Tischgruppen-Geometrie einmalig | `tablegroups[].seats[]` mit x/y + offset |
| Farb-Palette kohärent | `color_palette[key] = {label, hex, meaning}` |
| Plan-Metadaten | `meta.created_at`, `meta.school_year` |

### 1.2 Schema

```json
{
  "format_version": 4,
  "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",

  "meta": {
    "name": "Klasse 5a",
    "school_year": "2025/2026",
    "created_at": "2025-08-15T09:00:00",
    "last_modified": "2025-09-03T14:30:00"
  },

  "classroom": {
    "teacher_seat": { "x": 0, "y": 0 },
    "students": [
      {
        "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "first_name": "Anna",
        "last_name": "Müller",
        "seat": { "x": 1, "y": 0 },
        "diagnostic": {
          "symbols": { "Laptop": 2, "Tablet": 1 },
          "color_tags": ["gelb", "rot"]
        }
      }
    ]
  },

  "tablegroups": [
    {
      "group_id": 1,
      "seats": [
        { "x": 1, "y": 0, "shift_x": 0.03, "shift_y": -0.02, "rotation": 1.5 },
        { "x": 2, "y": 0, "shift_x": -0.03, "shift_y": 0.02, "rotation": -1.5 }
      ]
    }
  ],

  "color_palette": {
    "gelb":   { "label": "Gelb",    "hex": "#f4d35e", "meaning": "Förderbedarf" },
    "orange": { "label": "Orange",  "hex": "#ee964b", "meaning": "" },
    "rot":    { "label": "Rot",     "hex": "#f95738", "meaning": "Hochbegabt" }
  },

  "documentation": {
    "grade_columns": [
      {
        "column_id": "3f8a1c2d",
        "category": "schriftlich",
        "title": "Mathearbeit 1",
        "created_at": "2025-09-01"
      }
    ],
    "grade_weighting": {
      "written_percent": 60,
      "sonstige_percent": 40
    },
    "sessions": [
      {
        "date": "2025-09-01",
        "entries": {
          "f47ac10b-58cc-4372-a567-0e02b2c3d479": {
            "symbols": { "Beteiligung": 2, "Kooperation": 3 },
            "grades":  { "3f8a1c2d": 2.5 },
            "note": "Sehr konzentriert"
          }
        }
      }
    ]
  }
}
```

### 1.3 Schlüsseleigenschaften

- **Schüler bewegen sich:** `seat` ändert sich, `student_id` bleibt.
- **Session-Abfrage:** `plan.documentation.sessions` direkt iterierbar ohne Desk-Lookup.
- **Tischgruppen:** `tablegroups` ist eine flache Liste; Geometrie pro Platz (x/y), nicht pro Desk.
- **Farb-Palette:** `color_palette[key].meaning` — kombiniert was bisher `color_meanings` + `COLOR_MARKER_PALETTE` war.
- **Lehrertisch:** `classroom.teacher_seat` — separater Eintrag, keine Desk-Instanz.

---

## 2. Neue Domänen-Modelle

### 2.1 Modell-Hierarchie

```
SeatingPlan (Aggregat-Root)
├── PlanMeta
├── Classroom
│   ├── TeacherSeat
│   └── list[Student]
│       ├── StudentId (UUID-Wrapper)
│       ├── Seat (x, y)
│       └── DiagnosticProfile
│           ├── dict[symbol, strength]
│           └── list[color_tag]
├── list[TableGroup]
│   └── list[GroupSeat]  (x, y, shift_x, shift_y, rotation)
├── ColorPalette
│   └── dict[key, PaletteEntry]  (label, hex, meaning)
└── DocumentationBlock
    ├── list[GradeColumn]
    ├── GradeWeighting
    └── list[Session]
        └── dict[StudentId, SessionEntry]
            ├── dict[symbol, strength]
            ├── dict[column_id, grade]
            └── note: str
```

### 2.2 Wichtige Invarianten

- `Student.student_id` ist immutabel und UUID v4.
- `Session.date` ist ISO-8601 (YYYY-MM-DD), innerhalb des Plans eindeutig.
- `GradeColumn.column_id` ist 8 Hex-Zeichen, unveränderlich nach Erstellung.
- `ColorPalette` enthält nur Farben, die tatsächlich auf Schülern gesetzt sind.
- `TableGroup` enthält alle Seats die zusammen eine Gruppe bilden — kein Desk-Feld mehr.

### 2.3 Usecase-Signaturen (bleiben gleich, Innereien ändern sich)

```python
# Schüler-Operationen
create_student(plan, x, y) → SeatingPlan          # erzeugt student_id intern
move_student(plan, student_id, new_x, new_y) → SeatingPlan
rename_student(plan, student_id, first, last) → SeatingPlan
delete_student(plan, student_id) → SeatingPlan

# Dokumentation
add_session(plan, date) → SeatingPlan
record_symbol(plan, student_id, date, symbol, strength) → SeatingPlan
record_grade(plan, student_id, date, column_id, grade) → SeatingPlan

# Abfragen (read-only)
student_at(plan, x, y) → Student | None           # ersetzt desk_at()
session_for_date(plan, date) → Session | None
```

---

## 3. Application Service Layer (AppController)

### 3.1 Rolle

Der `AppController` ist die einzige Klasse, die:
- Usecases aufruft
- History schreibt
- Persistenz auslöst
- `AppState` produziert

Die GUI **liest nur** `AppState` und **sendet** Intents.

```
GUI (Mixins)
    ↓  emit(Intent)
AppController
    ↓  call
Usecases (pure functions)
    ↓  return new SeatingPlan
AppController
    ↓  history.record() + repository.save()
    ↓  → new AppState
GUI
    ↓  on_state_changed(AppState) → re-render
```

### 3.2 AppState

```python
@dataclass(frozen=True)
class AppState:
    # Plan
    current_plan: SeatingPlan | None
    current_plan_path: Path | None
    plan_list: list[PlanListEntry]           # (path, name, student_count)

    # Selektion & Modus
    selection: RectSelection
    interaction_mode: InteractionMode         # Enum: LIST | GRID | NAME_EDIT
    editor_surface: EditorSurface             # Enum: GRID | DOCS

    # Docs-Ansicht
    doc_selected_student_id: StudentId | None
    doc_selected_date: str | None
    doc_selected_column_id: str | None
    doc_sort: DocSortState

    # Status
    status_message: str
    can_undo: bool
    can_redo: bool
```

### 3.3 AppController-Schnittstelle

```python
class KartographAppController:
    def __init__(
        self,
        plan_repository: SeatingPlanRepository,
        settings_repository: SettingsRepository,
        on_state_changed: Callable[[AppState], None],
    ) -> None: ...

    def dispatch(self, intent: Intent) -> None:
        """Zentraler Einstiegspunkt für alle UI-Aktionen."""
        ...

    @property
    def state(self) -> AppState: ...
```

### 3.4 Intent → Handler-Registry

```python
class IntentRegistry:
    def register(
        self,
        intent_type: type[Intent],
        handler: Callable[[Intent, AppState], AppState],
    ) -> None: ...

    def dispatch(self, intent: Intent, state: AppState) -> AppState: ...
```

**Beispiel-Registrierungen:**

```python
registry.register(DeleteStudentIntent,   handle_delete_student)
registry.register(ToggleColorIntent,     handle_toggle_color)
registry.register(RecordSymbolIntent,    handle_record_symbol)
registry.register(UndoIntent,            handle_undo)
registry.register(OpenPlanIntent,        handle_open_plan)
```

---

## 4. Typisiertes Intent-System

### 4.1 Intent-Klassenhierarchie

```python
# app/core/intents/base.py
@dataclass(frozen=True)
class Intent:
    """Basisklasse für alle UI-Aktionen."""

# app/core/intents/plan_intents.py
@dataclass(frozen=True)
class OpenPlanIntent(Intent):
    plan_path: Path

@dataclass(frozen=True)
class CreatePlanIntent(Intent):
    name: str

@dataclass(frozen=True)
class RenamePlanIntent(Intent):
    plan_path: Path
    new_name: str

@dataclass(frozen=True)
class DeletePlanIntent(Intent):
    plan_path: Path

# app/core/intents/student_intents.py
@dataclass(frozen=True)
class CreateStudentIntent(Intent):
    x: int
    y: int

@dataclass(frozen=True)
class MoveStudentIntent(Intent):
    student_id: StudentId
    new_x: int
    new_y: int

@dataclass(frozen=True)
class RenameStudentIntent(Intent):
    student_id: StudentId
    first_name: str
    last_name: str

@dataclass(frozen=True)
class DeleteStudentIntent(Intent):
    student_id: StudentId

# app/core/intents/symbol_intents.py
@dataclass(frozen=True)
class ToggleDiagnosticSymbolIntent(Intent):
    student_id: StudentId
    symbol: str

@dataclass(frozen=True)
class RecordDocumentationSymbolIntent(Intent):
    student_id: StudentId
    date: str
    symbol: str
    strength: int  # 0 = löschen

# app/core/intents/navigation_intents.py
@dataclass(frozen=True)
class SelectCellIntent(Intent):
    x: int
    y: int

@dataclass(frozen=True)
class MoveSelectionIntent(Intent):
    dx: int
    dy: int
    expand: bool = False

# app/core/intents/edit_intents.py
@dataclass(frozen=True)
class UndoIntent(Intent):
    steps: int = 1

@dataclass(frozen=True)
class RedoIntent(Intent):
    steps: int = 1

@dataclass(frozen=True)
class CopySelectionIntent(Intent): ...
@dataclass(frozen=True)
class CutSelectionIntent(Intent): ...
@dataclass(frozen=True)
class PasteSelectionIntent(Intent): ...
```

### 4.2 Vorteile gegenüber String-Konstanten

| Merkmal | Alt (String) | Neu (Typed Intent) |
|---------|-------------|-------------------|
| Parameter | Keine (alles aus `self`) | Im Intent-Objekt enthalten |
| Typsicherheit | Keine | `mypy`-prüfbar |
| Testbarkeit | Muss GUI instanziieren | `controller.dispatch(intent)` direkt testbar |
| Erweiterbarkeit | `elif`-Kette anpassen | Neuen Handler registrieren |
| Serialisierbar | Nur als String | Als Dataclass speicherbar (Makro-Recording) |

---

## 5. Wiring-Diagramm (Gesamtübersicht)

```
┌────────────────────────────────────────────────────────────────┐
│  GUI-Schicht (app/adapters/gui/)                               │
│                                                                │
│  ┌──────────────────┐   state.current_plan                    │
│  │  GridMixin       │◄──────────────────────────────┐         │
│  │  DocsMixin       │                               │         │
│  │  DetailsMixin    │  dispatch(Intent)             │         │
│  │  ...             │──────────────────────────┐   │         │
│  └──────────────────┘                          │   │         │
│                                                ▼   │         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  KartographAppController                               │ │
│  │                                                        │ │
│  │  IntentRegistry                                        │ │
│  │  ┌───────────────────────────────────────────────┐    │ │
│  │  │ OpenPlanIntent     → handle_open_plan         │    │ │
│  │  │ CreateStudentIntent→ handle_create_student    │    │ │
│  │  │ ToggleColorIntent  → handle_toggle_color      │    │ │
│  │  │ RecordSymbolIntent → handle_record_symbol     │    │ │
│  │  │ UndoIntent         → handle_undo              │    │ │
│  │  │ ...                                           │    │ │
│  │  └───────────────────────────────────────────────┘    │ │
│  │                                                        │ │
│  │  PlanHistory ◄── record()                             │ │
│  │  Repository  ◄── save()                               │ │
│  │  AppState    ──► on_state_changed()  ─────────────────┘ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                  │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Core Usecases (app/core/usecases/)                    │ │
│  │  create_student(), record_symbol(), toggle_color() ... │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                  │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Infrastructure (app/infrastructure/)                  │ │
│  │  JsonSeatingPlanRepository v4                          │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 5.1 Bootstrap / Wiring

```python
# app/adapters/bootstrap/wiring.py

def build_app(workspace_root: Path) -> KartographMainWindow:
    settings_repo = JsonSettingsRepository(...)
    plan_repo     = JsonSeatingPlanRepositoryV4()

    controller = KartographAppController(
        plan_repository=plan_repo,
        settings_repository=settings_repo,
        on_state_changed=...,   # wird nach Window-Erstellung gesetzt
    )

    window = KartographMainWindow(controller=controller)
    controller.on_state_changed = window.apply_state   # Callback-Wiring

    return window
```

### 5.2 GUI-Mixin-Vertrag

```python
class GridMixin:
    """Rendert den Rasterbereich; sendet nur Intents; liest nur AppState."""

    # ❌ VERBOTEN in Mixins:
    #   self.current_plan = ...
    #   save_plan(...)
    #   history.record(...)

    # ✅ ERLAUBT:
    def _on_canvas_click(self, event) -> None:
        x, y = self._pixel_to_cell(event.x, event.y)
        self._controller.dispatch(SelectCellIntent(x=x, y=y))

    def _render(self, state: AppState) -> None:
        plan = state.current_plan
        # nur lesen + zeichnen
        ...
```

---

## 6. Neue Verzeichnisstruktur

```
app/
├── core/
│   ├── domain/
│   │   ├── models.py               # SeatingPlan v4, Student, Session, ...
│   │   ├── student_id.py           # StudentId UUID-Wrapper
│   │   ├── table_groups.py         # Geometrie (unverändert)
│   │   ├── desk_clipboard.py       # Clipboard (student_id-basiert)
│   │   └── plan_history.py         # Unverändert
│   ├── intents/                    # NEU
│   │   ├── __init__.py
│   │   ├── base.py                 # Intent-Basisklasse
│   │   ├── plan_intents.py
│   │   ├── student_intents.py
│   │   ├── symbol_intents.py
│   │   ├── color_intents.py
│   │   ├── grade_intents.py
│   │   ├── navigation_intents.py
│   │   └── edit_intents.py
│   ├── ports/
│   │   └── repositories.py         # Protokolle (unverändert)
│   └── usecases/
│       ├── student_usecases.py     # create/move/rename/delete (neu: student_id)
│       ├── symbol_usecases.py      # toggle_diagnostic, record_doc_symbol
│       ├── color_usecases.py       # Unverändert
│       ├── grade_usecases.py       # Unverändert
│       ├── session_usecases.py     # NEU: add_session, ensure_session
│       └── __init__.py             # Re-export-Shim
│
├── application/                    # NEU (Application Service Layer)
│   ├── app_controller.py           # KartographAppController
│   ├── app_state.py                # AppState dataclass
│   ├── intent_registry.py          # IntentRegistry
│   └── handlers/                   # NEU: je eine Datei pro Domänenbereich
│       ├── plan_handlers.py        # handle_open_plan, handle_create_plan, ...
│       ├── student_handlers.py
│       ├── symbol_handlers.py
│       ├── color_handlers.py
│       ├── grade_handlers.py
│       ├── session_handlers.py
│       ├── edit_handlers.py        # undo, redo, copy, cut, paste
│       └── navigation_handlers.py
│
├── infrastructure/
│   ├── repositories/
│   │   ├── v4/                     # NEU: v4-Serialisierer
│   │   │   ├── json_plan_repository_v4.py
│   │   │   ├── serializer_v4.py
│   │   │   └── deserializer_v4.py
│   │   ├── v3/                     # ALT: für Migrationsscript
│   │   │   ├── deserializer_v3.py  # (aus bestehenden Dateien extrahiert)
│   │   │   └── ...
│   │   ├── settings_repository.py
│   │   └── plan_backup.py
│   ├── exporters/                  # Unverändert
│   └── symbol_config_loader.py     # Unverändert
│
├── adapters/
│   ├── bootstrap/
│   │   └── wiring.py               # Erweitert um Controller-Wiring
│   └── gui/
│       ├── main_window.py          # Nimmt controller: AppController entgegen
│       ├── _mixin_*.py             # Nur render + dispatch; kein Usecase-Import
│       └── ...
│
└── tools/
    └── migrate_v3_to_v4.py         # Migrationsskript (eigenständig ausführbar)
```

---

## 7. Implementierungsplan (Schritte)

### Phase A — Neue Domänenmodelle & v4-JSON

**Schritt A1: StudentId-Typ einführen**
- `app/core/domain/student_id.py` erstellen
- `StudentId = NewType("StudentId", str)` (UUID v4, hex ohne Bindestriche)
- Konstruktor: `StudentId.new() → StudentId`

**Schritt A2: SeatingPlan v4-Modell**
- `app/core/domain/models.py` komplett neu schreiben
- `Student` mit `student_id`, `seat`, `DiagnosticProfile`
- `Session` mit `date`, `entries: dict[StudentId, SessionEntry]`
- `TableGroup` mit `group_id`, `seats: list[GroupSeat]`
- `PaletteEntry` mit `label`, `hex`, `meaning`
- `SeatingPlan` als Aggregat-Root (keine `Desk`-Klasse mehr)

**Schritt A3: v4-Serialisierer**
- `app/infrastructure/repositories/v4/serializer_v4.py`
- `app/infrastructure/repositories/v4/deserializer_v4.py`
- `app/infrastructure/repositories/v4/json_plan_repository_v4.py`

**Schritt A4: Usecases auf v4-Modelle umstellen**
- `desk_usecases.py` → `student_usecases.py`
- `create_student_desk()` → `create_student(plan, x, y) → SeatingPlan`
- Alle desk-basierten Lookups auf `student_at(plan, x, y)` umstellen
- `session_usecases.py` neu: `add_session`, `record_symbol`, `record_grade`

**Schritt A5: Migrationsskript** (s. Abschnitt 8)

**Schritt A6: Tests für v4-Modelle & Usecases**
- Unit-Tests für alle neuen Usecases
- Roundtrip-Test: `serialize → deserialize → compare`
- Migrations-Test: v3-Fixture → migriert → korrekte v4-Struktur

---

### Phase B — Application Service Layer

**Schritt B1: Intent-Klassen**
- `app/core/intents/` Verzeichnis mit allen Intent-Dataclasses (s. Abschnitt 4.1)

**Schritt B2: AppState**
- `app/application/app_state.py` schreiben
- Alle flüchtigen GUI-Zustände (selected date, sort, etc.) in `AppState` aufnehmen

**Schritt B3: Handler-Funktionen**
- `app/application/handlers/` — je Bereich eine Datei
- Jeder Handler: `(intent: T, state: AppState, ctx: HandlerContext) → AppState`
- `HandlerContext` enthält `plan_repository`, `settings_repository`, `history`

**Schritt B4: IntentRegistry**
- `app/application/intent_registry.py`
- `register(type, handler)` + `dispatch(intent, state) → AppState`

**Schritt B5: KartographAppController**
- `app/application/app_controller.py`
- Hält `state`, `registry`, `ctx`
- `dispatch(intent)`: `state = registry.dispatch(intent, state)` → `on_state_changed(state)`

**Schritt B6: Tests für Controller + Handler**
- Handler isoliert ohne GUI testbar
- `controller.dispatch(OpenPlanIntent(path)) → assert state.current_plan is not None`

---

### Phase C — GUI-Refactoring (strikte Trennung)

**Schritt C1: `main_window.py` auf Controller umstellen**
- `__init__(controller: AppController)` statt der bisherigen Repositories
- `apply_state(state: AppState)` als zentraler Render-Callback
- `self._controller = controller`

**Schritt C2: Mixin-Vertrag etablieren**
- Alle Mixin-Imports von Usecases entfernen
- Stattdessen: `self._controller.dispatch(SomeIntent(...))`
- Alle direkten Zuweisungen auf `self.current_plan` entfernen
- Render-Methoden erhalten `state: AppState` als Parameter

**Schritt C3: Mixins einzeln migrieren**
Reihenfolge: unten (einfachstes) → oben (komplexestes):
1. `_mixin_viewport.py` — kein Usecase, nur State lesen
2. `_mixin_theme.py` — kein Usecase, nur Settings-State
3. `_mixin_selection.py` → `SelectCellIntent`, `MoveSelectionIntent`
4. `_mixin_edit.py` → `DeleteStudentIntent`, `ToggleColorIntent`, etc.
5. `_mixin_details.py` → `RenameStudentIntent`, `CreateStudentIntent`
6. `_mixin_docs_*.py` → `RecordDocumentationSymbolIntent`, `RecordGradeIntent`
7. `_mixin_plan_list.py` → `OpenPlanIntent`, `CreatePlanIntent`
8. `_mixin_plan_crud.py` → `RenamePlanIntent`, `DeletePlanIntent`

**Schritt C4: `UiIntentController` entfernen**
- Wird durch `IntentRegistry` im Controller ersetzt
- `ui_intent_controller.py` löschen
- `ui_intents.py` durch `app/core/intents/` ersetzen

**Schritt C5: Shortcut-Wiring**
- Shortcuts binden `dispatch(SomeIntent(...))` direkt
- Kein Zwischenstop über String-Intent mehr
- `_mixin_shortcuts.py` + `_mixin_shortcut_handlers.py` nutzen neue Intents

---

### Phase D — Wiring, Bootstrap, Settings

**Schritt D1: Settings als AppState-Teil**
- `AppState.settings: KartographSettings` hinzufügen
- `KartographSettings` als Dataclass (kein freies Dict mehr)
- `OpenSettingsIntent` → Handler liest + schreibt Settings-Repository

**Schritt D2: `wiring.py` erweitern**
- `build_app()` erstellt `AppController`, registriert alle Handler, verkabelt GUI

**Schritt D3: Symbols-Konfiguration**
- Symbol-Definitionen beim Start in `AppState.symbol_catalog` laden
- GUI liest nur noch aus State

---

## 8. Migrationsskript v3 → v4

**Datei:** `app/tools/migrate_v3_to_v4.py`

Das Skript ist eigenständig ausführbar (kein GUI-Import) und idempotent (v4-Pläne werden übersprungen).

### 8.1 Nutzung

```bash
# Einzelne Datei
python -m app.tools.migrate_v3_to_v4 --input plans/klasse5a.json

# Ganzes Verzeichnis
python -m app.tools.migrate_v3_to_v4 --dir plans/ --dry-run
python -m app.tools.migrate_v3_to_v4 --dir plans/ --backup-suffix .v3.bak
```

### 8.2 Mapping v3 → v4

| v3-Feld | v4-Ziel | Transformationsregel |
|---------|---------|---------------------|
| `version: 3` | `format_version: 4` | Fest |
| `plan_id` | `plan_id` | Übernehmen |
| `name` | `meta.name` | Verschieben |
| — | `meta.created_at` | `datetime.now()` beim Migrieren |
| — | `meta.school_year` | `""` (leer) |
| `desks[type=teacher].{x,y}` | `classroom.teacher_seat` | Extrahieren |
| `desks[type=student]` | `classroom.students[]` | Konvertieren |
| desk.`name` | `student.first_name` | |
| desk.`last_name` | `student.last_name` | |
| desk.`{x,y}` | `student.seat.{x,y}` | |
| desk.`symbols` | `student.diagnostic.symbols` | |
| desk.`color_markers` | `student.diagnostic.color_tags` | |
| desk.`tablegroup_number` | `tablegroups[group_id].seats[].{x,y}` | Gruppieren |
| desk.`tablegroup_shift_*` | `tablegroups[].seats[].shift_*` | Verschieben |
| desk.`tablegroup_rotation` | `tablegroups[].seats[].rotation` | Verschieben |
| `color_meanings` | `color_palette[key].meaning` | Mergen mit Palette |
| `documentation.dates` | (implizit in `sessions`) | Aus entries ableiten |
| `documentation.grade_columns` | `documentation.grade_columns` | `id` → `column_id` |
| `documentation.grade_weighting` | `documentation.grade_weighting` | Übernehmen |
| desk.`documentation_entries[date]` | `documentation.sessions[date].entries[student_id]` | Schlüssel: neu generierte student_id |

### 8.3 Kern-Implementierung

```python
"""tools/migrate_v3_to_v4.py — Kartograph JSON v3 → v4 Migrationsskript."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


COLOR_PALETTE_DEFAULTS = {
    "gelb":    {"label": "Gelb",    "hex": "#f4d35e"},
    "orange":  {"label": "Orange",  "hex": "#ee964b"},
    "rot":     {"label": "Rot",     "hex": "#f95738"},
    "magenta": {"label": "Magenta", "hex": "#d81159"},
    "lila":    {"label": "Lila",    "hex": "#7b2cbf"},
    "marine":  {"label": "Marine",  "hex": "#1d3557"},
    "cyan":    {"label": "Cyan",    "hex": "#4cc9f0"},
    "tuerkis": {"label": "Türkis",  "hex": "#2a9d8f"},
    "gruen":   {"label": "Grün",    "hex": "#6a994e"},
}


def migrate_plan(v3: dict) -> dict:
    """Konvertiert einen v3-Plan-Dict in das v4-Format."""
    if v3.get("format_version") == 4:
        return v3  # Bereits migriert

    color_meanings: dict[str, str] = v3.get("color_meanings", {})
    desks: list[dict] = v3.get("desks", [])
    teacher = next((d for d in desks if d.get("type") == "teacher"), None)
    students_raw = [d for d in desks if d.get("type") == "student"]

    # Stabile IDs für Schüler generieren (deterministisch per Name+Koordinate)
    student_id_map: dict[tuple[int, int], str] = {}
    students_v4 = []
    for desk in students_raw:
        sid = str(uuid.uuid4())
        student_id_map[(desk["x"], desk["y"])] = sid
        students_v4.append({
            "student_id": sid,
            "first_name":  desk.get("name", ""),
            "last_name":   desk.get("last_name", ""),
            "seat":        {"x": desk["x"], "y": desk["y"]},
            "diagnostic":  {
                "symbols":    desk.get("symbols", {}),
                "color_tags": desk.get("color_markers", []),
            },
        })

    # Tischgruppen aus Desk-Geometrie aufbauen
    groups: dict[int, list[dict]] = {}
    for desk in students_raw:
        group_num = desk.get("tablegroup_number", 0)
        if group_num == 0:
            continue
        groups.setdefault(group_num, []).append({
            "x":        desk["x"],
            "y":        desk["y"],
            "shift_x":  desk.get("tablegroup_shift_x", 0.0),
            "shift_y":  desk.get("tablegroup_shift_y", 0.0),
            "rotation": desk.get("tablegroup_rotation", 0.0),
        })
    tablegroups_v4 = [
        {"group_id": gid, "seats": seats}
        for gid, seats in sorted(groups.items())
    ]

    # Farb-Palette: Basis + Bedeutungen einmergen
    color_palette: dict[str, dict] = {}
    for key, defaults in COLOR_PALETTE_DEFAULTS.items():
        used = any(key in d.get("color_markers", []) for d in students_raw)
        if not used:
            continue
        color_palette[key] = {
            **defaults,
            "meaning": color_meanings.get(key, ""),
        }

    # Sessions aus documentation_entries aller Desks aufbauen
    docs_raw: dict = v3.get("documentation", {})
    sessions_by_date: dict[str, dict] = {}
    for desk in students_raw:
        sid = student_id_map[(desk["x"], desk["y"])]
        for date, entry in desk.get("documentation_entries", {}).items():
            sessions_by_date.setdefault(date, {})[sid] = {
                "symbols": entry.get("symbols", {}),
                "grades":  entry.get("grades", {}),
                "note":    entry.get("note", ""),
            }
    sessions_v4 = [
        {"date": date, "entries": entries}
        for date, entries in sorted(sessions_by_date.items())
    ]

    # grade_columns: "id" → "column_id"
    grade_columns_v4 = [
        {
            "column_id":  col.get("id", col.get("column_id", "")),
            "category":   col.get("category", "sonstig"),
            "title":      col.get("title", ""),
            "created_at": "",
        }
        for col in docs_raw.get("grade_columns", [])
    ]

    weighting = docs_raw.get("grade_weighting", {})

    return {
        "format_version": 4,
        "plan_id":        v3.get("plan_id", str(uuid.uuid4())),
        "meta": {
            "name":          v3.get("name", ""),
            "school_year":   "",
            "created_at":    datetime.now().isoformat(timespec="seconds"),
            "last_modified": datetime.now().isoformat(timespec="seconds"),
        },
        "classroom": {
            "teacher_seat": {"x": teacher["x"], "y": teacher["y"]} if teacher else {"x": 0, "y": 0},
            "students":     students_v4,
        },
        "tablegroups":   tablegroups_v4,
        "color_palette": color_palette,
        "documentation": {
            "grade_columns":    grade_columns_v4,
            "grade_weighting":  {
                "written_percent":  weighting.get("written_percent", 50),
                "sonstige_percent": weighting.get("sonstige_percent", 50),
            },
            "sessions": sessions_v4,
        },
    }


def migrate_file(
    input_path: Path,
    output_path: Path | None = None,
    backup_suffix: str | None = ".v3.bak",
    dry_run: bool = False,
) -> None:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if raw.get("format_version") == 4:
        print(f"  SKIP (already v4): {input_path.name}")
        return

    v4 = migrate_plan(raw)
    target = output_path or input_path

    if dry_run:
        print(f"  DRY-RUN: {input_path.name} → {target.name}")
        return

    if backup_suffix and input_path == target:
        shutil.copy2(input_path, input_path.with_suffix(backup_suffix))

    target.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  OK: {input_path.name} → {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kartograph JSON v3 → v4 Migration")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="Einzelne .json-Datei")
    group.add_argument("--dir",   type=Path, help="Verzeichnis mit .json-Dateien")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--backup-suffix", default=".v3.bak")
    parser.add_argument("--output",        type=Path, help="Ausgabepfad (nur bei --input)")
    args = parser.parse_args()

    files = [args.input] if args.input else sorted(args.dir.glob("*.json"))
    for f in files:
        try:
            migrate_file(f, args.output, args.backup_suffix, args.dry_run)
        except Exception as exc:
            print(f"  ERROR: {f.name}: {exc}")


if __name__ == "__main__":
    main()
```

---

## 9. Checkliste (Implementierungsreihenfolge)

```
Phase A — Neue Modelle & JSON
[x] A1  student_id.py — StudentId-Typ
[x] A2  models.py v4 — SeatingPlan, Student, Session, TableGroup, PaletteEntry
[x] A3  serializer_v4.py + deserializer_v4.py + json_plan_repository_v4.py
[x] A4  student_usecases.py, session_usecases.py (alle auf v4 umstellen)
[x] A5  migrate_v3_to_v4.py — Migrationsskript (s. Abschnitt 8)
[x] A6  Tests: Roundtrip, Migration, Usecases

Phase B — Application Service Layer
[x] B1  core/intents/ — alle Intent-Dataclasses
[x] B2  application/app_state.py — AppState
[x] B3  application/handlers/*.py — Handler-Funktionen
[x] B4  application/intent_registry.py — IntentRegistry
[x] B5  application/app_controller.py — KartographAppController
[x] B6  Tests: Handler isoliert, Controller-Integration

Phase C — GUI-Refactoring
[x] C1  main_window.py auf controller: AppController umstellen
[x] C2  Mixin-Vertrag: kein Usecase-Import, nur dispatch() + apply_state()
[x] C3  Mixins einzeln migrieren (alle _mixin_*.py inkl. docs_*, tablegroup_logic,
        canvas_events, export — auf v4-Modell + Intent-Dispatch umgestellt;
        neu: app/core/usecases/v4/tablegroup_usecases.py für Tischgruppen-Logik,
        da es dafür noch kein Intent gibt — Mixin ruft Usecase direkt + speichert
        über plan_repository + controller.replace_plan_in_state)
[x] C4  ui_intent_controller.py entfernt (s. Begründung unten zu ui_intents.py)
[x] C5  Shortcuts dispatchen über eine echte Registry (`_build_ui_action_registry()`
        in `_mixin_shortcuts.py`, `dict[str, Callable]`) statt über die alte
        if/elif-Klasse `MainWindowUiIntentController`

Phase D — Wiring & Settings
[x] D1  AppState.settings: KartographSettings (typisiert)
[x] D2  wiring.py erweitern
[x] D3  Symbol-Katalog in AppState

**Bewusste Abweichung bei C4 (ui_intents.py bleibt bestehen):** Die String-
Konstanten aus `ui_intents.py` sind weiterhin die stabilen IDs für das
HSM-Contract (`bw_gui/contracts/hsm.py`), die Laufkern-Telemetrie
(`_mixin_laufkern.py`) und `KeyBindingDefinition.intent` — Subsysteme, die
es noch nicht gab, als dieser Plan ursprünglich verfasst wurde (s. Notiz zu
C3 oben). Diese Subsysteme behandeln den Intent nur als rohen String und
sind unabhängig vom hier ersetzten Application-Layer-Intent-System
(`app/core/intents/`). Nur `ui_intent_controller.py` (die if/elif-Kette,
das eigentlich kritisierte Muster aus Abschnitt 0.2) wurde entfernt;
`tools/ci/check_ai_guardrails.py` wurde entsprechend angepasst.

**Vorbestehende, in dieser Session entdeckte Lücke (nicht Teil von C4/C5):**
`add_symbol_to_selected_desk_dialog` (Toolbar-Button "★ S") existierte im
letzten committeten v3-Stand vollständig implementiert, ging aber beim
(unkommittierten) Mixin-Split/v4-Umzug einer vorherigen Session verloren.
Der Button ist aktuell wirkungslos (kein Absturz dank
`report_callback_exception`). Eigener, separater Task.

**Bekannte Lücke (Backup-Rotation, nicht Teil dieser Session):**
`JsonSeatingPlanRepository` (v3, Backup-Rotation) ist nicht auf v4 migriert.
Zugehörige Tests (`tests/test_backup_rotation.py`,
`tests/test_backup_snapshot_api.py`) waren bereits vor dieser Session rot
und sind unverändert rot geblieben. Die PDF-Export-Pipeline ist seit
Phase E (Abschnitt 9a) vollständig auf v4 migriert — die ursprüngliche
Notiz dazu an dieser Stelle war veraltet und wurde entfernt.
```

---

## 9a. Phase E — PDF-Export-Migration auf v4

Die PDF-Export-Pipeline wurde bei der C3-Migration bewusst ausgeklammert
(siehe Lücke in Abschnitt 9). Sie ist die letzte Stelle im Produktionscode,
die noch direkt auf v3-Modelle (`Desk`, `plan.desks`, `plan.color_meanings`)
zugreift. `_mixin_pdf.py` übergibt inzwischen einen v4-Plan — ohne diese
Migration schlägt der PDF-Export zur Laufzeit fehl.

### 9a.1 Betroffene Dateien

| Datei | v3-Abhängigkeit | v4-Ersatz |
|-------|-----------------|-----------|
| `pdf_exporter.py` | `models.SeatingPlan`, `normalize_tablegroups_in_place`, `build_desk_geometries`, `plan.name` | `models_v4.SeatingPlan`, `tablegroup_usecases.normalize_tablegroups`, `table_groups.build_seat_geometries_v4`, `plan.meta.name` |
| `pdf_desk_renderer.py` | `Desk`, `desk.desk_type`, `desk.student_name/last_name`, `desk.color_markers`, `desk.symbols`, `compute_grade_display_for_student`, `summarize_latest_symbols_for_student` | `SeatGeometryV4` (`is_teacher`, `student`), `Student.first_name/last_name`, `student.diagnostic.color_tags/symbols`, `grade_usecases.compute_grade_display`, `symbol_usecases.summarize_latest_symbols` |
| `pdf_legend_renderer.py` | `models.SeatingPlan`, `plan.color_meanings.get(key)` | `models_v4.SeatingPlan`, `plan.color_palette.get(key).meaning` |
| `pdf_font_utils.py` | — (modellunabhängig, reine Funktionen) | keine Änderung nötig |
| `tests/test_pdf_exporter_legend.py` | v3-`SeatingPlan(version=2, ...)`, ruft nicht-existente `exporter._legend_symbol_tables`/`_draw_legend_page` direkt auf `PdfSeatingPlanExporter` auf (Methoden liegen tatsächlich auf `PdfLegendRenderer`) | v4-Plan-Fixtures aus `tests/conftest.py` (`make_plan`/`make_student`), Aufrufe über `exporter._legend_renderer` |

### 9a.2 Schritte

**E1: `pdf_exporter.py` auf v4 umstellen**
- Import `models_v4.SeatingPlan` statt `models.SeatingPlan`
- `export_plan = normalize_tablegroups(plan)` statt `deepcopy` + `normalize_tablegroups_in_place`
- `build_seat_geometries_v4(export_plan)` statt `build_desk_geometries`
- `render_items` führt `SeatGeometryV4`-Objekte statt `geometry.desk`
- `export_plan.meta.name` statt `export_plan.name` (Titel + Dateititel)

**E2: `pdf_desk_renderer.py` auf v4 umstellen**
- `render_desk(..., seat: SeatGeometryV4, ...)` statt `desk: Desk`
- Lehrertisch-Erkennung über `seat.is_teacher` statt `desk.desk_type == "teacher"`
- Name/Noten/Farbpunkte/Symbole über `seat.student` (`Student`) lesen
- Notenberechnung über `compute_grade_display(plan, student.student_id, ...)`
- Symbol-Zusammenfassung über `summarize_latest_symbols(plan, student.student_id)`

**E3: `pdf_legend_renderer.py` auf v4 umstellen**
- Import `models_v4.SeatingPlan`
- Farbbedeutung über `plan.color_palette.get(color_key)` (→ `.meaning`) statt `plan.color_meanings.get(color_key)`

**E4: Tests aktualisieren**
- `tests/test_pdf_exporter_legend.py` neu schreiben: v4-Plan-Fixtures, korrekte Methodenpfade (`exporter._legend_renderer.*`)
- Bestehende Assertions (Tabellenaufbau, Leer-Hinweis bei fehlenden Farbbedeutungen) inhaltlich erhalten

**E5: Sanity-Check**
- Test-Suite grün, inkl. der zuvor roten `test_pdf_exporter_legend.py`
- Manueller Smoke-Export (reportlab, falls installiert) gegen einen echten v4-Plan mit Schüler, Notenspalte und Farbpunkt

### 9a.3 Checkliste

```
[x] E1  pdf_exporter.py auf v4 (models_v4, normalize_tablegroups, build_seat_geometries_v4, meta.name)
[x] E2  pdf_desk_renderer.py auf v4 (SeatGeometryV4, Student-Felder, v4-Grade/Symbol-Usecases)
[x] E3  pdf_legend_renderer.py auf v4 (color_palette[key].meaning)
[x] E4  tests/test_pdf_exporter_legend.py auf v4-Fixtures umgestellt
[x] E5  Test-Suite grün + manueller Smoke-Export (reportlab 4.5.1, v4-Plan mit Schüler/Note/Symbol/Farbpunkt/Legende)
```

PDF-Export ist damit vollständig auf v4 migriert. Verbleibende rote Tests
(`tests/test_backup_rotation.py`, `tests/test_backup_snapshot_api.py`)
betreffen ausschließlich die v3-Backup-Rotation von `JsonSeatingPlanRepository`
und sind von dieser Phase unberührt — eigener, separater Task.

---

## 10. Nicht-Ziele (explizit außen vor)

- **Kein Multi-Klassen-Modus** (ein Plan = eine Lerngruppe, keine Sammelansicht)
- **Kein Cloud-Sync / Backend** (lokale JSON-Datei bleibt Datenhaltung)
- **Kein reaktives UI-Framework** (Tkinter bleibt, kein React/Flutter-Ersatz)
- **Keine Breaking-API für Plugins** (kein Plugin-System geplant)
- **Keine automatische v3→v4-Migration beim Start** — nur explizit via Skript

---

## 11. Feature-Erweiterung: Nachteilsausgleiche im Details-Panel

### 11.1 Anforderung

Im Details-Panel eines Schülers (Editor-Ansicht, Einzelauswahl) sollen neben
Namen, Symbol- und Farblegende auch **Nachteilsausgleiche** erfasst und
angezeigt werden können — z. B. „Zeitzuschlag 25 %", „Nutzung Laptop",
„Mündliche Ersatzleistung". Pro Schüler können mehrere Einträge bestehen.

Wie bei `color_tags` wird zunächst **keine** strukturierte Form (Gültigkeits-
zeitraum, Fach, ausstellende Stelle) abgebildet, sondern eine einfache Liste
von Freitext-Einträgen — analog zum bisherigen Komplexitätsniveau des Modells.
Eine spätere Erweiterung um Struktur ist möglich, ohne das Grundschema zu
brechen (zusätzliche Felder statt Format-Bruch).

### 11.2 Datenmodell-Erweiterung (v4)

`DiagnosticProfile` (in `app/core/domain/models_v4.py`) erhält ein neues Feld:

```python
@dataclass(slots=True)
class DiagnosticProfile:
    symbols: dict[str, int] = field(default_factory=dict)
    color_tags: list[str] = field(default_factory=list)
    accommodations: list[str] = field(default_factory=list)  # NEU: Nachteilsausgleiche
```

JSON-Schema-Ergänzung (Abschnitt 1.2, innerhalb `classroom.students[].diagnostic`):

```json
"diagnostic": {
  "symbols": { "Laptop": 2, "Tablet": 1 },
  "color_tags": ["gelb", "rot"],
  "accommodations": ["Zeitzuschlag 25 %", "Nutzung Laptop"]
}
```

Migrationsskript (`app/tools/migrate_v3_to_v4.py`): v3 hat kein Äquivalent →
`accommodations: []` für alle migrierten Schüler (keine Mapping-Regel nötig).

### 11.3 Intent + Usecase + Handler

Neue Dateien, analog zu `color_intents.py` / `color_usecases.py` / `color_handlers.py`:

```python
# app/core/intents/accommodation_intents.py
@dataclass(frozen=True)
class SetAccommodationsIntent(Intent):
    student_id: StudentId
    accommodations: list[str]
```

```python
# app/core/usecases/v4/accommodation_usecases.py
def set_accommodations(plan: SeatingPlan, student_id: StudentId, accommodations: list[str]) -> SeatingPlan:
    """Ersetzt die Liste der Nachteilsausgleiche eines Schülers vollständig.

    Leere/nur-Leerzeichen-Einträge werden verworfen, Reihenfolge bleibt erhalten.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    student.diagnostic.accommodations = [a.strip() for a in accommodations if a.strip()]
    return next_plan
```

```python
# app/application/handlers/accommodation_handlers.py
def handle_set_accommodations(intent: SetAccommodationsIntent, state: AppState, ctx: HandlerContext) -> AppState:
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = set_accommodations(state.current_plan, intent.student_id, intent.accommodations)
    _record_and_save(next_plan, state.current_plan_path, "accommodation.set", ctx)
    return _with_plan(state, next_plan, ctx)
```

Registrierung in `app_controller.py._register_handlers()`:
```python
r.register(SetAccommodationsIntent, lambda i, s: handle_set_accommodations(i, s, ctx))
```

Ein einziges „Set"-Intent (statt Add/Remove/Update einzeln) passt zur GUI:
die Liste wird als Mehrzeilen-Text editiert und bei jeder Änderung komplett
neu gesetzt — analog zu `RenameStudentIntent`, das ebenfalls beide Namen
gemeinsam ersetzt statt einzelner Buchstaben-Patches.

### 11.4 GUI: Details-Panel-Erweiterung

- **`_mixin_details_layout.py`**: neuer `accommodations_frame` unterhalb von
  `color_legend_frame`, mit Überschrift „Nachteilsausgleiche" und einem
  mehrzeiligen Eingabefeld (`tui.Text`, ca. 3 Zeilen) — eine Zeile pro Eintrag.
- **`_mixin_details.py`**:
  - `_refresh_details_panel()` befüllt das Feld aus
    `student.diagnostic.accommodations` (zeilenweise) und (de)aktiviert es
    analog zu `name_entry`/`last_name_entry` (nur bei Einzelauswahl eines
    benannten Schülers editierbar).
  - Neuer Callback `_on_accommodations_changed()` (gebunden an `<FocusOut>`
    bzw. analoges Pattern wie `_on_name_changed`) parst die Zeilen und
    dispatcht `SetAccommodationsIntent(student_id=..., accommodations=lines)`.
  - Anzeige folgt damit dem gleichen Lese-Schreib-Muster wie Name/Farben/
    Symbole: GUI zeigt nur `state.current_plan`, jede Änderung geht über
    `dispatch()`.

### 11.5 Persistenz

- `app/infrastructure/repositories/v4/serializer_v4.py`: `accommodations`
  beim Serialisieren von `diagnostic` mit aufnehmen.
- `app/infrastructure/repositories/v4/deserializer_v4.py`: `accommodations`
  beim Deserialisieren lesen, Default `[]` falls im JSON nicht vorhanden
  (Abwärtskompatibilität mit v4-Plänen, die vor dieser Erweiterung gespeichert wurden).

### 11.6 Offene Entscheidung (vor Implementierung zu klären)

**Sollen Nachteilsausgleiche im PDF-Export erscheinen?**
Empfehlung: **Nein, standardmäßig nicht.** Es sind sensible, teils
diagnosebezogene Daten (vgl. besondere Kategorien personenbezogener Daten,
Art. 9 DSGVO) — anders als Symbole/Farbpunkte, die frei konfigurierbare,
pädagogisch neutrale Marker sind. Der PDF-Export bleibt GUI-only-Anzeige;
falls später doch benötigt, analog zum bestehenden Sichtbarkeits-Dialog
(`open_grid_symbol_filter_dialog`) als explizit opt-in Checkbox ergänzen,
nicht als Standardverhalten.

### 11.7 Checkliste

```
[x] F1  models_v4.py — DiagnosticProfile.accommodations: list[str]
[x] F2  core/intents/accommodation_intents.py — SetAccommodationsIntent
[x] F3  core/usecases/v4/accommodation_usecases.py — set_accommodations
[x] F4  application/handlers/accommodation_handlers.py — handle_set_accommodations
[x] F5  app_controller.py — Intent registriert
[x] F6  serializer_v4.py / deserializer_v4.py — accommodations lesen/schreiben
        (Default [] bei fehlendem Feld für Abwärtskompatibilität)
[x] F7  _mixin_details_layout.py — accommodations_frame mit bw_gui.widgets.WrappedTextField
        (erster Verwender dieser Shared-Primitive in Kartograph)
[x] F8  _mixin_details.py — Anzeige + _on_accommodations_changed() (FocusOut) + Dispatch
[x] F9  Tests: tests/test_accommodation_usecases.py, Handler-Test in
        tests/test_app_controller.py, Roundtrip-Tests in tests/test_v4_roundtrip.py
[x] F10 Entscheidung zu Abschnitt 11.6 bestätigt (kein PDF-Export der Nachteilsausgleiche)
```

---

## 12. Nächste Tasks (offene Lücken außerhalb dieser Checkliste)

Während der C4/C5/D1/D3/F-Session entdeckt, zunächst bewusst nicht mitgelöst
(jeweils eigener, separater Task) — alle drei in einer Folgesession abgearbeitet:

**T1: Backup-Rotation (v3) auf v4 migrieren — [x] gelöst**
- Ursache war eine Regression aus "modulization phase 1": `_backup_root_dir`
  wanderte beim Extrahieren der Backup-Logik nach `PlanBackupWriter`, ohne
  dass Repositories diesen Pfad noch überschreiben konnten.
- Fix: `PlanBackupWriter.write_backup()` akzeptiert jetzt ein optionales
  `root_dir`-Override; `JsonSeatingPlanRepository` (v3) und
  `JsonSeatingPlanRepositoryV4` implementieren wieder eine
  `_backup_root_dir()`-Methode, die in Tests überschreibbar ist.
- `tests/test_backup_rotation.py`/`tests/test_backup_snapshot_api.py` wurden
  auf `JsonSeatingPlanRepositoryV4` (die produktiv verkabelte Implementierung)
  + `tests/conftest.py`-Fixtures umgestellt, statt gegen das tote
  v3-Repository zu testen.

**T2: `tools/ci/check_ai_guardrails.py` an den Mixin-Split anpassen — [x] gelöst**
- Fix: neuer Helper `_read_entry_candidate_group()` kombiniert ein
  GUI-Entry-File (z. B. `main_window.py`) mit allen `_mixin_*.py`-
  Geschwisterdateien im selben Verzeichnis; `_check_shared_ui_contracts`,
  `_check_runtime_shortcut_integration` und `_check_future_gui_entry_contracts`
  prüfen jetzt gegen diese kombinierte Textbasis statt nur gegen
  `main_window.py`.
- Die 7 verbliebenen `_check_repo_wide_gui_contracts`-Verstöße wurden durch
  echte Migration behoben: `_mixin_docs_dialogs.py`, `_mixin_edit.py`,
  `_mixin_pdf.py`, `_mixin_plan_crud.py`, `_mixin_plan_list.py`,
  `_mixin_settings.py`, `_mixin_undo_redo.py` importieren `messagebox`/
  `simpledialog` jetzt aus dem bereits vorhandenen
  `app/adapters/gui/dialog_services.py` (API-kompatibler Shared-Wrapper mit
  Popup-Policy-Tracking) statt direkt aus `tkinter`.
- `python tools/ci/check_ai_guardrails.py` läuft wieder grün (nur
  vorbestehende, nicht-blockierende Shortcut-Coverage-Warnings bleiben).

**T3: `add_symbol_to_selected_desk_dialog` wiederherstellen — [x] gelöst**
- Dialog wurde vom letzten committeten v3-Stand
  (`git show HEAD:app/adapters/gui/main_window.py`, Zeile ~5015) nach
  `_mixin_edit.py` portiert: `student_at()` statt `desk_at()`,
  `student.is_named()` statt `desk_type == "student"`, Anwenden über das
  bereits vorhandene `_toggle_selected_symbol()` (dispatcht intern
  `ToggleDiagnosticSymbolIntent` + `RecordDocumentationSymbolIntent`) statt
  direkter Desk-Mutation.
- Mit isoliertem Tk-Smoke-Test gegen einen temporären Workspace verifiziert
  (Dialog öffnet, Symbolliste korrekt befüllt, "Übernehmen" setzt das Symbol
  auf dem Schüler und schließt den Dialog).

---

## 13. Entdeckte Lücken: Typisierte Intents ohne GUI-Anbindung

### 13.0 Hintergrund / Methodik

Bei der T3-Recherche fiel auf, dass `add_symbol_to_selected_desk_dialog`
nicht der einzige Fall ist, in dem ein Intent registriert, aber von der GUI
nie gesendet wird. Audit-Methode: für jede der 43 Intent-Klassen unter
`app/core/intents/` wurde geprüft, ob `KlassenName(` irgendwo unter
`app/adapters/gui/` als Konstruktoraufruf vorkommt (nicht nur als Import).

**Ergebnis: 24 von 43 Intents haben keine Dispatch-Stelle in der GUI.**
Pro Fall wurde zusätzlich geprüft, *warum* — daraus ergeben sich zwei klar
unterschiedliche Kategorien (Tabelle in 13.1).

### 13.1 Klassifizierung

| Intent | Handler-Status | Tatsächlicher Weg in der GUI | Kategorie |
|---|---|---|---|
| `ZoomInIntent`/`ZoomOutIntent` | No-Op (`view_handlers.py`) | `UiIntent.ZOOM_IN/OUT` → `_mixin_canvas_events.py.zoom_in()/zoom_out()` | A — funktioniert, Altsystem |
| `ResetViewIntent` | No-Op | `UiIntent.RESET_VIEW` → `reset_viewport()` | A |
| `ToggleThemeIntent` | No-Op | `UiIntent.TOGGLE_THEME` → `_mixin_theme.py.toggle_theme()` | A |
| `ExportPdfIntent` | No-Op | `UiIntent.EXPORT_PDF` → `_mixin_pdf.py.export_plan_pdf_dialog()` | A |
| `OpenSettingsIntent` | Echte Logik, nie gesendet | `UiIntent.OPEN_SETTINGS` → `open_settings_dialog()` | A |
| `OpenTablegroupSettingsIntent` | No-Op | `UiIntent.OPEN_TABLEGROUP_SETTINGS` → `open_tablegroup_settings_overlay()` | A |
| `SetEditorSurfaceIntent`/`ToggleEditorSurfaceIntent` | Echte Logik, nie gesendet | `_mixin_docs_view.py` setzt `self._editor_surface` direkt | A |
| `SelectCellIntent`/`MoveSelectionIntent`/`ClearSelectionIntent` | — (kein Handler-Registry-Eintrag nötig, da nie gesendet) | `_mixin_selection.py`/`_mixin_canvas_events.py` mutieren `self.selection`/`self.selected_cell` direkt; `AppState.selection` existiert, wird aber von der GUI nie gelesen | A |
| `DuplicatePlanIntent` | — | `_mixin_plan_crud.py`/`_mixin_plan_list.py` rufen `self.plan_repository.duplicate_plan()` direkt (eigener Plan-Listen-Undo-Stack) | A |
| `AddSessionIntent` | Echte Logik, nie gesendet | `_mixin_docs_dialogs.py` ruft `ensure_session()`-Usecase direkt | A |
| `NavigateSessionIntent`/`GoToTodayIntent` | Echte Logik, nie gesendet | `_mixin_docs_view.py`/`_mixin_shortcut_handlers.py` mutieren `self._doc_selected_date_index` direkt | A |
| `CopySelectionIntent`/`CutSelectionIntent`/`PasteSelectionIntent` | No-Op (`# TODO(C-Phase)`) | **keiner** — `_mixin_undo_redo.py` zeigt nur `status_var.set("... noch nicht implementiert")` | **B — echte Lücke** |
| `MoveStudentIntent` | Echte Logik (`move_student`-Usecase), nie gesendet | **keiner** — Canvas-Drag bewegt nur die Auswahl-Box, nie einen Schüler | **B** |
| `DeleteGradeColumnIntent` | Echte Logik (`_delete_grade_column`), nie gesendet | **keiner** — Notenspalten können angelegt, aber nie gelöscht werden | **B** |
| `DeleteSessionIntent` | Echte Logik (`_delete_session`), nie gesendet | **keiner** — Doku-Termine können umbenannt, aber nie gelöscht werden | **B** |

**Kategorie A (12 von 24, Architektur-Schulden, keine Nutzer-Auswirkung):**
Die Funktion arbeitet korrekt, aber über den alten String-`UiIntent` (s.
Abschnitt 0.2 — exakt das Muster, das Architekturplan v2 eigentlich ablösen
sollte) oder über lokale, nie in `AppState` gespiegelte Mixin-Attribute. Kein
Bugfix nötig, aber jede dieser Stellen widerspricht dem in Abschnitt 5.2
festgelegten Mixin-Vertrag ("GUI liest nur State, sendet nur Intents").

**Kategorie B (5 von 24 + Copy/Cut/Paste, echte fehlende Funktionen):**
Handler und Usecase sind vollständig fertig implementiert — es fehlt
ausschließlich der GUI-Trigger (Button/Menüeintrag/Shortcut). Diese Lücken
sind für Endnutzer real spürbar, auch wenn sie (wie T3 vor der Behebung)
nicht abstürzen, sondern nur wirkungslos bleiben oder ein Feature schlicht
nicht anbieten.

### 13.2 Bucket B — priorisierte Folge-Tasks (noch nicht umgesetzt)

**T4: Copy/Cut/Paste für Schülerplätze implementieren — [x] gelöst**
- `app/application/handlers/edit_handlers.py:58-70` — drei No-Op-Handler mit
  `# TODO(C-Phase): v4-Clipboard implementieren`.
- `app/adapters/gui/_mixin_undo_redo.py:135,138-139,142-143` — zeigt aktuell
  nur Status-Meldungen "... ist in v4 noch nicht implementiert".
- Die alte v3-`DeskClipboard`-Klasse (`app/core/domain/desk_clipboard.py`)
  wird in `main_window.py` zwar noch instanziiert (`self._desk_clipboard`),
  aber von nirgends mehr aufgerufen — toter Code, arbeitet ohnehin auf dem
  v3-`Desk`-Modell.
- Fix: neue v4-native Clipboard-Logik (z. B. `app/core/domain/v4/student_clipboard.py`
  mit `StudentId`-Listen statt `Desk`-Objekten), darauf aufbauend die drei
  Handler implementieren; alte `DeskClipboard`-Instanziierung entfernen.
- **Umsetzung:** `app/core/domain/student_clipboard.py` (neue `StudentClipboard`-
  Klasse) speichert nur `StudentId` + relativen Versatz, keine Datenkopien.
  Kopieren/Ausschneiden verändert den Plan **nicht** sofort — auf
  ausdrücklichen Wunsch markiert Ausschneiden nur, gelöscht/verschoben wird
  erst beim tatsächlichen Einfügen. Beim Einfügen: Ausschneiden verschiebt
  unter Beibehaltung von `StudentId`, Diagnoseprofil, Tischgruppen-Mitgliedschaft
  und Dokumentationshistorie (intern über koordinatenbasierte Tischgruppen-
  Umschreibung, kollisionsfrei auch bei Platztausch innerhalb derselben
  Operation); Kopieren erzeugt pro Einfügung eine frische `StudentId` ohne
  Dokumentationshistorie. `HandlerContext.clipboard` hält die Instanz
  (analog zu `HandlerContext.history`). `handle_copy_selection`/
  `handle_cut_selection`/`handle_paste_selection` in `edit_handlers.py`
  implementiert; `CopySelectionIntent`/`CutSelectionIntent` tragen jetzt die
  Selektionszellen, `PasteSelectionIntent` die Zielzelle. GUI-Methoden in
  `_mixin_undo_redo.py` dispatchen die Intents statt Platzhalter-Meldungen
  zu zeigen; Ctrl+C/X/V sind jetzt auf den Raster-Scope beschränkt
  (`GRID_ONLY_INTENTS`). Alte `DeskClipboard`-Instanziierung und die v3-Datei
  `desk_clipboard.py` entfernt. Tests: `tests/test_student_clipboard.py`
  (Domänenlogik inkl. Selbstüberlappung und Platztausch-Edgecase) und neue
  `TestHandleClipboardHandlers` in `tests/test_app_controller.py`.

**T5: `MoveStudentIntent` — kein Drag-to-Move geplant — [x] entschieden**
- `MoveStudentIntent`/`handle_move_student`/`move_student`-Usecase sind
  fertig, aber nirgends in der GUI aufgerufen.
- **Korrektur:** Drag auf dem Canvas ist und bleibt für Mehrfachauswahl
  reserviert (`_on_canvas_drag`/`_on_canvas_release` in
  `_mixin_canvas_events.py` erweitern die Auswahl-Box, analog zu
  Shift+Pfeiltasten/`expand_selection`) — das ist die vorgesehene Funktion
  und darf nicht für einen Verschiebe-Modus umgewidmet werden. Der ursprüngliche
  Fix-Vorschlag (Drag mit Modifier-Taste löst `MoveStudentIntent` aus) ist
  damit verworfen.
- **Entscheidung:** Kein eigener GUI-Trigger für `MoveStudentIntent`.
  Cut+Paste (T4) ist der einzige Verschiebe-Weg für benannte Schüler.
  `MoveStudentIntent`/`handle_move_student` bleiben als ungenutzter,
  fertiger Baustein bestehen (kein toter Code im strengen Sinne — weiterhin
  über `tests/test_student_usecases.py` abgedeckt), bekommen aber keinen
  Button/Shortcut. Der eigentliche Verschiebe-Pfad läuft über
  `StudentClipboard.paste_into_plan()` (direkte Sitzplatz-Mutation, nicht
  über den `move_student`-Usecase selbst, s. T4-Umsetzung) und erfüllt damit
  die Anforderung "beim Ausschneiden wird noch nichts gelöscht, nur zum
  Verschieben markiert".

**T6: Notenspalte löschen — [x] gelöst**
- `DeleteGradeColumnIntent`/`handle_delete_grade_column` sind fertig, aber
  `_mixin_layout_docs.py`/`_mixin_docs_dialogs.py` bieten nur "Notenspalte
  anlegen", keinen Löschen-Pfad.
- Fix: Lösch-Aktion ergänzen (z. B. Kontextmenü auf der Spaltenüberschrift
  in `docs_right_tree`, oder Button neben "Neue Notenspalte anlegen").
- **Umsetzung:** Neuer Toolbar-Button "Notenspalte loeschen" neben "Notenspalte
  hinzufuegen" (`_mixin_layout_docs.py`), neuer `UiIntent.DELETE_GRADE_COLUMN`
  (`view.documentation.grade_column.delete`) in `DOCS_ONLY_INTENTS` und in der
  `_build_ui_action_registry()`. `delete_grade_column_dialog()` in
  `_mixin_docs_dialogs.py` bestimmt die Zielspalte (markierte Spalte → einzige
  vorhandene Spalte → Auswahlliste bei Mehrdeutigkeit), fragt vor dem Löschen
  explizit nach Bestätigung (`_confirm_and_delete_grade_column()`) und
  dispatcht dann `DeleteGradeColumnIntent`. Tests: neue
  `TestHandleGradeColumnHandlers` in `tests/test_app_controller.py` (inkl.
  Add-Handler, der zuvor ebenfalls ungetestet war, und der Kaskade, die
  bereits erfasste Noten dieser Spalte aus allen Sessions entfernt).

**T7: Dokumentationstermin (Session) löschen — [x] gelöst**
- `DeleteSessionIntent`/`handle_delete_session` sind fertig, aber es gibt
  nur "Datum umbenennen" (`_mixin_docs_dialogs.py`), keinen Löschen-Pfad für
  ein komplettes Datum/Session.
- Fix: Lösch-Aktion analog zu "Datum umbenennen" ergänzen.
- **Umsetzung:** Neuer Toolbar-Button "Datum loeschen" neben "Datum
  umbenennen" (`_mixin_layout_docs.py`), neuer `UiIntent.DELETE_DOCUMENTATION_DATE`
  (`view.documentation.date.delete`) in `DOCS_ONLY_INTENTS` und in der
  `_build_ui_action_registry()`. Anders als "Datum umbenennen" (das den
  v4-Usecase direkt aufruft, weil es dafür kein eigenes Intent gibt) geht
  `delete_selected_documentation_date_dialog()` in `_mixin_docs_dialogs.py`
  über den vorhandenen Intent/Handler-Pfad: Bestätigungsabfrage (analog zu
  `_confirm_and_delete_grade_column()` aus T6), dann
  `self._controller.dispatch(DeleteSessionIntent(date=...))`.

**T8: `session.label`/`RenameSessionLabelIntent` — Absicht geprüft: unklar → löschen — [x] gelöst**
- Recherche (Docstrings, Kommentare, Git-Historie, v3-Vorbild) ergab **keine
  erkennbare Absicht**:
  - `Session.label` (`app/core/domain/models_v4.py:199`) hat keinen
    Docstring-Hinweis; die `Session`-Klassendoku beschreibt nur `entries`.
  - Das Schema-Beispiel in Abschnitt 1.2 zeigt nur `"label": null` ohne
    jede Erläuterung, wofür das Feld gedacht ist.
  - `session_intents.py`/`session_usecases.py`/`session_handlers.py` sind
    unkommittierte, neue Dateien — keine Git-Historie/Commit-Message zur
    Herkunft verfügbar.
  - v3 kannte keine Sessions (Dokumentation lag in `desk.documentation_entries[date]`,
    s. Abschnitt 0.3) — kein Vorbild-Feature, von dem `label` übernommen wurde.
- **Entscheidung: löschen, kein Zweck identifizierbar.** Betrifft:
  `RenameSessionLabelIntent` (`app/core/intents/session_intents.py`),
  `handle_rename_session_label` + `_set_session_label` (`session_handlers.py`),
  Registrierung in `app_controller.py`, `Session.label`-Feld
  (`models_v4.py`), `"label"`-Schlüssel in Serializer/Deserializer
  (`v4/serializer_v4.py:153`, `v4/deserializer_v4.py`), `"label": null` im
  Schema-Beispiel (Abschnitt 1.2) sowie der Eintrag in der Tabelle/Zeile
  oben in 13.1, sobald T8 umgesetzt ist.
- **Umsetzung:** Alle oben aufgeführten Stellen entfernt, zusätzlich
  `"label": None` im Migrationsskript (`app/tools/migrate_v3_to_v4.py`,
  Session-Konstruktion) und das jetzt überflüssige `label="Erstes Treffen"`
  in `tests/test_v4_roundtrip.py::test_session_with_entries_preserved`
  (die Assertions dieses Tests prüften ohnehin nur `entries`/`symbols`/`note`,
  nicht `label`). Re-Export in `app/core/intents/__init__.py` mitbereinigt.

**T9: `ToggleDocsModeIntent` — Absicht geprüft: unklar → löschen — [x] gelöst**
- Gleiche Prüfung wie T8: kein Docstring (`pass`-Body), Handler-Kommentar
  nur vage ("`# TODO(B5): ggf. docs-Anzeigemodus in AppState aufnehmen`"),
  keine Git-Historie (unkommittierte Datei), kein Pendant im alten
  `UiIntent`-System. Einziger Intent ohne jede erkennbare Zielfunktion —
  möglicherweise mit `ToggleEditorSurfaceIntent` (direkt daneben definiert,
  hat aber eine klare, echte Funktion) verwechselt oder als Entwurf
  begonnen und nie weitergeführt.
- **Entscheidung: löschen, kein Zweck identifizierbar.** Betrifft:
  `ToggleDocsModeIntent` (`app/core/intents/view_intents.py`),
  `handle_toggle_docs_mode` (`view_handlers.py`), Registrierung in
  `app_controller.py`, sowie der Eintrag in 13.1, sobald T9 umgesetzt ist.
- **Umsetzung:** Alle oben aufgeführten Stellen entfernt, Re-Export in
  `app/core/intents/__init__.py` mitbereinigt. Zusätzlich entdeckt und
  mitentfernt: `UiIntent.TOGGLE_DOCUMENTATION_MODE` (`view.documentation.mode.toggle`)
  in `app/adapters/gui/ui_intents.py` — ein gleichartiger Waisen-String ohne
  jede Verwendung, Rest eines laut `docs/DEVELOPMENT_LOG.md` bereits zuvor
  vollständig entfernten Features ("Navigations-Moduswechsel in der
  Dokumentationsansicht"). Kein Pendant zu `ToggleDocsModeIntent` im engeren
  Sinne (beide Systeme sind unabhängig, s. Abschnitt 13.3 Bucket A), aber
  exakt dieselbe Kategorie "kein Zweck identifizierbar".

### 13.3 Bucket A — Architektur-Schulden (funktioniert, kein Nutzer-Bug) — [x] gelöst

Niedrigere Priorität als 13.2, da nichts kaputt war — aber relevant, weil es
dem in Abschnitt 0.2/5.2 beschriebenen Kernziel von Architekturplan v2
widersprach ("kein zentraler Ort für was bei Intent X passiert",
"GUI liest nur State"). Migrationsentscheidung eingeholt: Umsetzung jetzt als
eigener Task, in den fünf unten gelisteten Gruppen, jeweils mit Tests
(Handler-Unit-Tests + isolierter Tk-Smoke-Test gegen einen temporären
Workspace, analog zu T3) verifiziert.

- **Selektion** (`SelectCellIntent`, `MoveSelectionIntent`,
  `ClearSelectionIntent`) — **gelöst.** `_set_selection_single`/
  `_set_selection_focus`/`_collapse_selection_to_anchor`/`move_selection`/
  `expand_selection` (`_mixin_selection.py`) dispatchen jetzt statt
  `self.selection` direkt zu mutieren; `apply_state()` (`main_window.py`)
  spiegelt `state.selection` zurück in `self.selection`/`self.selected_cell`.
  Canvas-Drag (`_mixin_canvas_events.py`) bleibt unverändert auf dieselben
  Methoden gestützt, läuft also automatisch mit. Escape (`handle_escape()` in
  `_mixin_edit.py`, Zweig `ESCAPE_POP_PARENT`) dispatcht zusätzlich
  `ClearSelectionIntent()`. `handle_open_plan`/`handle_create_plan` setzen
  `selection=RectSelection(0, 0)` direkt im State (ersetzt den bisherigen
  GUI-seitigen `_set_selection_single(0, 0)`-Aufruf in `apply_state()`, der
  sonst reentrant in den gerade laufenden `apply_state()`-Callback dispatcht
  hätte). Die dadurch redundante Selbst-Zuweisung in `show_editor_view()`
  wurde entfernt.
- **Editor-Oberfläche** (`SetEditorSurfaceIntent`,
  `ToggleEditorSurfaceIntent`) — **gelöst.** Toolbar-Button "Zur
  Rasteransicht" (`UiIntent.VIEW_GRID`) und `Ctrl+Shift+D`
  (`UiIntent.TOGGLE_DOCUMENTATION`) dispatchen jetzt die typisierten Intents
  (`_mixin_shortcuts.py`) statt `show_grid_surface()`/
  `show_documentation_surface()`/`toggle_documentation_surface()` direkt
  aufzurufen; letzteres ist dadurch unreachable geworden und wurde entfernt.
  `apply_state()` übersetzt `state.editor_surface` (Enum) in den von der GUI
  erwarteten String (`"grid"`/`"docs"`) und löst bei tatsächlicher Änderung
  `show_grid_surface()`/`show_documentation_surface()` aus.
- **Plan duplizieren** (`DuplicatePlanIntent`) — **gelöst.**
  `DuplicatePlanIntent` um `new_name`/`overwrite` erweitert (vorher
  hartkodierter Name "– Kopie", Nutzereingabe wurde ignoriert — ein
  zusätzlich gefundener Bug). `duplicate_selected_plan_dialog()`
  (`_mixin_plan_crud.py`) prüft Namenskonflikte vorab über die neue,
  rein lesende Repository-Methode `plan_name_taken()` (kein Rückgriff auf
  `dispatch()`-Exceptions nötig, da `IntentRegistry.dispatch()` Handler-
  Exceptions grundsätzlich abfängt und loggt statt sie weiterzuwerfen) und
  dispatcht danach einmalig `DuplicatePlanIntent`.
- **Session anlegen / Datumsnavigation** (`AddSessionIntent`,
  `NavigateSessionIntent`, `GoToTodayIntent`) — **gelöst.**
  `rename_selected_documentation_date_dialog()` (`_mixin_docs_dialogs.py`)
  ruft weiterhin `rename_session_date()` direkt (kein eigenes Intent dafür),
  übernimmt das Ergebnis aber über `replace_plan_in_state()` in den State und
  dispatcht für das Sicherstellen der Session am neuen Datum
  `AddSessionIntent` statt `ensure_session()` direkt aufzurufen. Alt+Links/
  Alt+Rechts (`_mixin_shortcut_handlers.py`) dispatchen `NavigateSessionIntent`,
  "Heute" (Button + `Ctrl+H`, `select_today_documentation_date()` in
  `_mixin_docs_view.py`) dispatcht `GoToTodayIntent`. `handle_navigate_session`
  bezieht zusätzlich das virtuelle "Heute"-Datum mit ein (analog zur
  GUI-Konstruktion von `_doc_dates`), sonst wäre die heutige Spalte beim
  Navigieren übersprungen worden, solange dafür noch keine Session existiert.
  `apply_state()` spiegelt `state.doc_selected_date` zurück in
  `self._doc_selected_date_index` und aktualisiert die Spaltenkopf-Markierung.
- **Viewport/Theme/Export/Tablegroup-Settings/Settings-Open** — **gelöst,**
  mit einer bewussten Abweichung bei `ToggleThemeIntent` (s. u.):
  - `ZoomInIntent`/`ZoomOutIntent`/`ResetViewIntent`: `AppState` um
    `cell_size` erweitert (Default/Grenzen als Literale dupliziert statt aus
    `main_window_constants.py` importiert, analog zu `settings.py` —
    Core/Application darf nicht von der GUI abhängen). Handler berechnen
    geklemmte Zellgröße; `zoom_in()`/`zoom_out()`/`reset_viewport()`
    (`_mixin_canvas_events.py`) dispatchen statt `self.cell_size` direkt zu
    setzen; `_apply_zoom()` (private Hilfsmethode) wurde dadurch obsolet und
    entfernt. `apply_state()` synct `cell_size` zurück und zentriert den
    Viewport auf die aktuelle Auswahl.
  - **`ToggleThemeIntent` entfernt** (kein `[ ]`/`[x]` als Bucket-A-Punkt,
    sondern dieselbe Behandlung wie T8/T9): die einzige sinnvolle
    Implementierung hätte `theme_names()`/`THEMES`
    (`app/adapters/gui/ui_theme.py`, reine Farbpaletten-Daten) in den
    Handler importieren müssen — ein Schichten-Verstoß (Application darf
    nicht von der GUI abhängen, s. o.). Die bereits vorhandene, funktionierende
    Lösung für "Einstellungen ändern" (`UpdateSettingsIntent`) deckt den
    eigentlichen Bedarf vollständig ab: `toggle_theme()`/`_on_theme_changed()`
    (`_mixin_theme.py`) berechnen das nächste Theme weiterhin GUI-seitig
    (legitime Präsentationsschicht-Zuständigkeit), dispatchen aber jetzt
    `UpdateSettingsIntent` statt `self.settings_repository.save_settings()`
    direkt aufzurufen. `self.theme_key` darf dabei nicht vorab gesetzt
    werden, sonst erkennt `apply_state()`s Änderungs-Vergleich keine
    Änderung mehr (Reihenfolge-Falle, beim Schreiben entdeckt). Der
    Menü-Theme-Picker (`_mixin_menu.py`) nutzt denselben `_on_theme_changed()`-
    Pfad und ist damit ohne weitere Änderung mitkorrigiert.
  - `OpenSettingsIntent`: `open_settings_dialog()` (`_mixin_settings.py`)
    dispatcht vor dem Aufbau des Dialogs, übernimmt die fünf dort
    angezeigten Felder (`plans_dir`, `canvas_radius`, `symbol_strength`,
    `viewport_follow_buffer`, `grid_name_format`) frisch aus
    `controller.state.settings`. Dabei einen vorbestehenden, separaten Bug
    gefunden und gefixt: `self.default_plans_dir` wurde nirgends gesetzt —
    `_build_settings_dialog_spec()` warf beim Öffnen des Dialogs immer einen
    `AttributeError` (über den `TkRootHost.__getattr__`-Fallback auf den
    rohen Tk-Root). Fix: `self.default_plans_dir = controller.plans_dir` in
    `main_window.py.__init__`, vor der Überschreibung von `self.plans_dir`
    durch den persistierten Wert.
  - `ExportPdfIntent`/`OpenTablegroupSettingsIntent`: bleiben echte No-Op-
    Handler (Dateidialog/-schreiben bzw. Toplevel-Overlay sind reine Tk-/IO-
    Seiteneffekte ohne AppState-Wirkung), werden aber jetzt aus
    `export_plan_pdf_dialog()` (`_mixin_pdf.py`, nach erfolgreichem Export)
    bzw. `open_tablegroup_settings_overlay()` (`_mixin_tablegroup.py`, mit
    der aktuell ausgewählten Zelle als `x`/`y`) dispatcht — für Konsistenz
    mit dem Intent-System (z. B. künftiges Makro-Recording, Abschnitt 4.2).

### 13.4 Checkliste

```
[x] T4  Copy/Cut/Paste: v4-native Clipboard-Logik + drei Handler implementieren — gelöst
[x] T5  Entschieden: kein eigener GUI-Trigger für MoveStudentIntent. Cut+Paste (T4) reicht —
        gelöst
[x] T6  Notenspalte löschen: UI-Trigger für DeleteGradeColumnIntent ergänzt — gelöst
[x] T7  Dokumentationstermin löschen: UI-Trigger für DeleteSessionIntent ergänzt —
        gelöst
[x] T8  Session-Label: kein Zweck identifizierbar — RenameSessionLabelIntent,
        Session.label-Feld und alle Referenzen ersatzlos entfernt — gelöst
[x] T9  ToggleDocsModeIntent: kein Zweck identifizierbar — Intent, Handler und
        Registrierung ersatzlos entfernt (inkl. Waisen-String
        UiIntent.TOGGLE_DOCUMENTATION_MODE) — gelöst
[x] —   Bucket A (13.3): Migrationsentscheidung eingeholt, alle fünf Gruppen
        umgesetzt (Selektion, Editor-Oberfläche, Plan duplizieren, Session-
        Navigation, Viewport/Theme/Export/Tablegroup/Settings) — gelöst.
        ToggleThemeIntent dabei ersatzlos entfernt (kein Zweck ohne
        Schichten-Verstoß umsetzbar, UpdateSettingsIntent deckt den Bedarf
        bereits ab — analog zu T8/T9). Nebenbei zwei vorbestehende Bugs
        gefunden und gefixt: DuplicatePlanIntent ignorierte den vom Nutzer
        eingegebenen Namen; self.default_plans_dir war nie gesetzt und liess
        den Einstellungen-Dialog beim Öffnen abstürzen.
```

---

## 14. Entdeckte Lücken: fehlende/unzureichende Docstrings

### 14.0 Methodik

AST-Scan über `app/`, `tools/ci/` und `bw_libs/` (kartograph-eigener Code;
das externe `bw-gui/`-Submodul und `tests/` bewusst ausgeklammert — Tests
folgen der üblichen Konvention, dass ein sprechender `test_*`-Name den
Docstring ersetzt). Für jede `class`/`def` (inkl. verschachtelter Methoden):

- **Fehlt komplett:** `ast.get_docstring()` liefert `None`.
- **Dünn:** Docstring vorhanden, Funktion hat Parameter (außer `self`), aber
  kein `Args:`-Abschnitt — also kein Parameter dokumentiert, obwohl der Rest
  der Codebasis (s. z. B. `json_plan_repository.py`, `plan_backup.py`)
  durchgehend Google-Style mit `Args:`/`Returns:`/`Raises:` verwendet.
  Triviale Dunder (`__init__`, `__repr__` u. ä.) sind ausgenommen.

**Ergebnis:** von 709 Klassen/Methoden/Funktionen haben **240 (34 %) gar
keinen Docstring** und weitere **126 (18 %)** einen Docstring ohne
Parameterdokumentation trotz vorhandener Parameter. Nur **343 (48 %)**
erfüllen den im Projekt selbst etablierten Standard.

### 14.1 Schweregrad-Einordnung

**Am schwersten wiegt das komplette Fehlen in zentralen, nicht-trivialen
Domänen-/Infrastruktur-Modulen** — hier ist die Begründung ("warum so und
nicht anders") am wertvollsten und am wenigsten aus dem Code selbst ablesbar:

| Datei | Fehlend | Anmerkung |
|---|---|---|
| `app/core/domain/table_groups.py` | 25 (2 Klassen, 23 Funktionen) | Tischgruppen-Geometrie, Komponentenerkennung, Überlappungs-Check — komplexe Algorithmen, **null** Erklärung des Warum/Wie. |
| `app/infrastructure/repositories/v4/deserializer_v4.py` | 13 | Kompletter v4-JSON-Parser ohne jeden Funktionskommentar. |
| `app/core/ports/repositories.py` | 11 (2 Klassen, 9 Funktionen) | `SeatingPlanRepository`/`SettingsRepository`-Protocols — die Vertragsklassen selbst sind undokumentiert. |
| `app/core/domain/plan_selection.py` | 10 (1 Klasse, 9 Funktionen) | `RectSelection` — zentral für die in Abschnitt 13.3 gefundene Selektions-Architektur-Schuld; ohne Doku schwer zu beurteilen, was bei einer AppState-Migration zu beachten wäre. |
| `app/core/domain/models.py` (v3) | 10 (4 Klassen, 6 Funktionen) | Noch von `desk_usecases.py` u. a. genutzt (s. Abschnitt 12, T1-Recherche). |
| `app/core/domain/models_v4.py` | 7 (nur Methoden, Dataclasses selbst haben Docstrings) | `student_at`, `student_by_id`, `session_for_date`, `all_dates`, `column_by_id`, `entry_for`, `has_content`. |
| `app/infrastructure/repositories/v4/serializer_v4.py` | 7 | Kompletter v4-JSON-Serializer ohne jeden Funktionskommentar. |
| `app/core/domain/plan_history.py` | 6 (1 Klasse, 5 Funktionen) | Undo/Redo-Kern — `record`/`undo`/`redo` komplett undokumentiert. |
| `app/infrastructure/symbol_config_loader.py` | 7 (1 Klasse, 6 Funktionen) | Lädt/parst `config/symbols.json`. |

**Zweitschwerste Kategorie: die komplette Intent- und Handler-Schicht.**
Bemerkenswert, weil das fehlende `class`-Docstring bei den Intents direkt
zur Verwechslungsgefahr aus Abschnitt 13 beigetragen hat (T8/T9 — ohne jede
Erklärung war nicht mehr feststellbar, wofür ein Intent gedacht war):

| Datei | Fehlend |
|---|---|
| `app/core/intents/view_intents.py` | 10 (alle 10 Klassen) |
| `app/core/intents/session_intents.py` | 6 (alle 6 Klassen) |
| `app/core/intents/edit_intents.py` | 5 (alle 5 Klassen) |
| `app/core/intents/plan_intents.py` | 5 (alle 5 Klassen) |
| `app/core/intents/student_intents.py` | 5 (alle 5 Klassen) |
| `app/core/intents/grade_intents.py` | 4 (alle 4 Klassen) |
| `app/core/intents/navigation_intents.py` | 3 (alle 3 Klassen) |
| `app/core/intents/symbol_intents.py` | 2 (alle 2 Klassen) |
| `app/core/intents/color_intents.py` | 1 (die einzige Klasse) |
| `app/application/handlers/session_handlers.py` | 9 (alle Funktionen) |
| `app/application/handlers/view_handlers.py` | 9 (alle Funktionen) |
| `app/application/app_controller.py` | 5 |
| `app/application/app_state.py` | 5 (alle 5 Klassen) |
| `app/application/handlers/edit_handlers.py` | 5 (alle Funktionen) |
| `app/application/handlers/grade_handlers.py` | 5 (alle Funktionen) |
| `app/application/handlers/plan_handlers.py` | 5 (alle Funktionen) |
| `app/application/handlers/student_handlers.py` | 5 (alle Funktionen) |
| `app/application/handlers/_shared.py` | 4 |
| `app/application/handlers/navigation_handlers.py` | 3 (alle Funktionen) |
| `app/application/handlers/symbol_handlers.py` | 2 (alle Funktionen) |
| `app/application/handlers/color_handlers.py` | 1 (die einzige Funktion) |
| `app/application/intent_registry.py` | 1 |

**Übrige Dateien mit fehlenden Docstrings (≤5 Treffer je Datei):**
`app/app.py` (5), `app/core/usecases/v4/_shared.py` (4),
`app/core/usecases/v4/tablegroup_usecases.py` (4),
`app/infrastructure/repositories/settings_repository.py` (4),
`app/adapters/gui/_mixin_docs_dialogs.py` (3), `app/adapters/gui/ui_theme.py` (3),
`app/infrastructure/repositories/v4/json_plan_repository_v4.py` (3),
`app/adapters/gui/_mixin_export.py` (2), `app/adapters/gui/_mixin_undo_redo.py` (2),
`app/core/domain/settings.py` (2), `app/tools/migrate_v3_to_v4.py` (2),
`bw_libs/app_paths.py` (2), `bw_libs/app_shell.py` (2),
`app/adapters/gui/_mixin_docs_table.py` (1), `app/adapters/gui/_mixin_edit.py` (1),
`app/adapters/gui/_mixin_pdf.py` (1), `app/adapters/gui/_mixin_shortcuts.py` (1),
`app/adapters/gui/ui_intents.py` (1), `app/core/domain/student_id.py` (1).

**Drittens — "dünne" Docstrings (Funktion hat Parameter, aber kein
`Args:`-Abschnitt):** überwiegend GUI-Mixins und das CI-Tooling, niedrigste
Priorität, da meist immerhin ein erklärender Einzeiler existiert.

`tools/ci/check_ai_guardrails.py` (21), `app/adapters/gui/_mixin_selection.py` (13),
`app/adapters/gui/_mixin_grid_helpers.py` (10), `app/adapters/gui/_mixin_shortcut_handlers.py` (9),
`app/adapters/gui/_mixin_canvas_events.py` (7), `app/adapters/gui/_mixin_docs_events.py` (5),
`app/core/usecases/v4/tablegroup_usecases.py` (5), `app/adapters/gui/_mixin_edit.py` (4),
`app/adapters/gui/main_window.py` (4), `app/core/domain/models_v4.py` (4),
`app/core/domain/table_groups.py` (4), `app/adapters/gui/_mixin_details.py` (3),
`app/adapters/gui/_mixin_viewport.py` (3), `app/core/usecases/_shared.py` (3),
`bw_libs/app_paths.py` (3), und 16 weitere Dateien mit je 1-2 Treffern
(vollständige Liste bei Bedarf erneut per AST-Scan reproduzierbar, s. 14.0).

### 14.2 Checkliste (priorisiert)

```
[x] T10  Domain-/Infrastruktur-Kern dokumentiert: table_groups.py,
         plan_selection.py, plan_history.py, ports/repositories.py,
         models.py/models_v4.py (fehlende Methoden), serializer_v4.py,
         deserializer_v4.py, symbol_config_loader.py — gelöst. Per AST-Scan
         verifiziert (0 fehlende Docstrings, Dunder wie __init__ bewusst
         ausgenommen, deren Args bereits auf dem Klassendocstring stehen).
[x] T11  Intent-Klassen dokumentiert (app/core/intents/*.py, alle 9
         Dateien) — gelöst. edit_intents.py war durch T4 bereits vollständig;
         die Liste unten war an drei Stellen veraltet (RenameSessionLabelIntent/
         ToggleDocsModeIntent durch T8/T9 entfernt, ToggleThemeIntent durch
         Bucket A entfernt) — entsprechend nicht mehr dokumentiert, sondern
         ersatzlos aus der Zählung gestrichen.
[x] T12  Handler-Funktionen dokumentiert (app/application/handlers/*.py,
         app_controller.py, app_state.py, intent_registry.py) — gelöst.
         Per AST-Scan verifiziert (0 fehlende Docstrings, Dunder ausgenommen).
[x] T13  "Dünne" Docstrings nachgeschärft (Args:-Abschnitte ergänzt) — gelöst.
         Ein frischer AST-Scan (nicht die ursprüngliche Audit-Liste, die durch
         T10-T12 selbst inzwischen veraltet war — viele dort als "fehlend"
         gezählte Docstrings existierten nach T10-T12 bereits, aber ohne
         Args:-Abschnitt und zählten dadurch neu als "dünn") fand 235 Treffer
         in 49 Dateien — fast doppelt so viele wie die ursprüngliche
         Schätzung von 126. Aufgeteilt in 5 an Subagenten delegierte Pakete
         (GUI-Mixins in 3 Gruppen, Core-Domäne/Usecases, Infrastruktur) plus
         ein selbst bearbeitetes Paket (Application-Handler, da dort die
         meisten Docstrings erst in T12 von mir selbst geschrieben wurden).
         Abschließend per frischem AST-Scan auf 0 verbleibende dünne
         Docstrings über den gesamten Scope (app/, tools/ci/, bw_libs/)
         verifiziert; volle Testsuite (262) und Guardrail-Check bleiben grün.
```

**Umsetzung T10-T12:** T10 (größter, algorithmisch dichtester Block) an
einen Subagenten delegiert; dieser hat table_groups.py, plan_selection.py,
plan_history.py, models_v4.py, repositories.py und serializer_v4.py
vollständig fertiggestellt, bei deserializer_v4.py und
symbol_config_loader.py sowie der `Desk`-Klasse in models.py durch ein
Sitzungslimit unterbrochen — diese drei Lücken sowie T11 und T12 wurden
danach direkt fertiggestellt. Alle drei Tickets wurden abschließend per
echtem AST-Scan (nicht nur der ursprünglichen, inzwischen teils veralteten
Audit-Liste oben) gegen 0 verbleibende fehlende Docstrings verifiziert.

Reihenfolge bewusst T10 vor T11 vor T12: Domänenlogik mit echten Algorithmen
(Geometrie, Undo/Redo, Serialisierung) profitiert am meisten von WHY-Doku;
die Intent-Klassen sind zwar zahlreich, aber pro Klasse trivial (1-2 Sätze
genügen) und beheben gleichzeitig die Unklarheit aus Abschnitt 13.

---

## 15. Entdeckte Lücke: Dokumentations-Toolbar-Aktionen ohne Tastatur-Shortcut

### 15.0 Hintergrund

Bei der T7-Umsetzung (Abschnitt 13.2) fiel auf, dass der neue
`UiIntent.DELETE_DOCUMENTATION_DATE` — wie schon zuvor `RENAME_DOCUMENTATION_DATE`
und die beiden T6-Intents `ADD_GRADE_COLUMN`/`DELETE_GRADE_COLUMN` — ausschließlich
über einen Toolbar-Button in `_mixin_layout_docs.py` ausgelöst wird.
`_build_ui_action_registry()` (`_mixin_shortcuts.py`) enthält für alle vier einen
Eintrag, aber `_bind_shortcuts()` registriert dafür keine
`_bind_runtime_shortcut(...)`-Tastenkombination — anders als z. B.
`RENAME_SELECTED_PLAN` (`<F2>`) oder `OPEN_TABLEGROUP_SETTINGS` (`<Control-t>`),
die beide Button **und** globalen Shortcut haben.

Dies ist orthogonal zu Abschnitt 13 (dort geht es um typisierte
`app/core/intents/*`-Dispatch-Lücken zwischen GUI und `AppController`) — alle
vier Aktionen hier funktionieren über den alten `UiIntent`/`_handle_intent()`-Pfad
einwandfrei per Mausklick, es fehlt nur die Tastatur-Erreichbarkeit.

### 15.1 Betroffene Intents

| UiIntent | Button (Datei) | Eingeführt in |
|---|---|---|
| `RENAME_DOCUMENTATION_DATE` | `docs_rename_date_button` (`_mixin_layout_docs.py`) | vor T6/T7 |
| `ADD_GRADE_COLUMN` | `docs_add_grade_column_button` (`_mixin_layout_docs.py`) | vor T6/T7 |
| `DELETE_GRADE_COLUMN` | `docs_delete_grade_column_button` (`_mixin_layout_docs.py`) | T6 |
| `DELETE_DOCUMENTATION_DATE` | `docs_delete_date_button` (`_mixin_layout_docs.py`) | T7 |

Bewusst nicht mit aufgenommen: eine vollständige Tastatur-Shortcut-Audit über
alle ~50 `UiIntent`-Werte (z. B. `ADD_SYMBOL`, `TOGGLE_THEME`,
`UNDO_LAST_FIVE` sind ebenfalls button-only) — das wäre eine eigene,
größere Bestandsaufnahme nach demselben Muster wie Abschnitt 13.0 und ist
hier nicht Gegenstand; dieser Abschnitt deckt nur die vier Doku-Toolbar-Aktionen
ab, die im Rahmen von T6/T7 in derselben Toolbar entstanden sind.

### 15.2 Checkliste

```
[x] T14  Tastatur-Shortcuts ergänzt — gelöst:
         RENAME_DOCUMENTATION_DATE  Ctrl+Shift+U (+u)
         DELETE_DOCUMENTATION_DATE  Ctrl+Shift+Backspace
         ADD_GRADE_COLUMN           Ctrl+Shift+N (+n)
         DELETE_GRADE_COLUMN        Ctrl+Shift+Delete
         Alle vier in _bind_shortcuts() (_mixin_shortcuts.py) registriert,
         modes=(UI_MODE_PREVIEW,) — laufen wie die Buttons über
         _handle_intent() und damit automatisch durch das bestehende
         DOCS_ONLY_INTENTS-Scope-Gating. Kollisionsfreiheit nicht nur manuell
         geprüft, sondern programmatisch über die eingebaute
         KeybindingRegistry.conflicts()-Methode verifiziert (0 Kollisionen,
         auch unter Berücksichtigung, dass UI_MODE_GLOBAL-Bindings in jedem
         Modus inkl. UI_MODE_PREVIEW mitwirken). Hover-Hilfetexte der
         betroffenen Buttons (_mixin_layout_docs.py) um die jeweilige
         Tastenkombination ergänzt, analog zu "Zur Rasteransicht"
         (Ctrl+Shift+D) und "Heute" (Ctrl+H). Mit isoliertem Tk-Smoke-Test
         verifiziert (Scope-Block im Grid, alle vier Aktionen über
         _handle_intent() ausgelöst und Plan-Wirkung geprüft).
```

---

*Erstellt: 2026-06-23 — Kartograph Architekturplan v2*
*Erweitert: 2026-06-25 — Abschnitt 9a (PDF-Migration), Abschnitt 11 (Nachteilsausgleiche)*
*Erweitert: 2026-06-25 — Abschnitt 12 (nächste Tasks: Backup-Rotation, Guardrail-Anpassung, add_symbol-Dialog)*
*Erweitert: 2026-06-25 — Abschnitt 12: T1-T3 abgearbeitet (Backup-Rotation auf v4 migriert, Guardrail-Check an Mixin-Split angepasst, add_symbol-Dialog wiederhergestellt)*
*Erweitert: 2026-06-25 — Abschnitt 13 (Audit: 24 von 43 Intents ohne GUI-Dispatch; T4-T9 als neue Folge-Tasks, Architektur-Schulden separat dokumentiert)*
*Erweitert: 2026-06-25 — Abschnitt 13 korrigiert: T5 kein Drag-to-Move (Drag bleibt für Mehrfachauswahl reserviert); T8/T9 Absicht geprüft (kein Docstring/Kommentar/Git-Historie/v3-Vorbild) → beide zur Löschung vorgesehen*
*Erweitert: 2026-06-25 — Abschnitt 14 (Docstring-Audit: 240/709 Klassen/Methoden ohne Docstring, 126 ohne Args-Dokumentation; T10-T13 als neue Folge-Tasks, priorisiert nach Domänen-Kern vor Intents vor Handlern vor Politur)*
*Erweitert: 2026-06-25 — Abschnitt 13: T7-T9 abgearbeitet (UI-Trigger für DeleteSessionIntent ergänzt, analog zu T6 mit Bestätigungsabfrage; RenameSessionLabelIntent/Session.label sowie ToggleDocsModeIntent inkl. Handler, Registrierung und Schema-Beispiel ersatzlos entfernt; zusätzlich den verwaisten String UiIntent.TOGGLE_DOCUMENTATION_MODE aus einem laut DEVELOPMENT_LOG.md bereits früher entfernten Feature mitbereinigt)*
*Erweitert: 2026-06-25 — Abschnitt 15 (neu: fehlende Tastatur-Shortcuts für die vier Doku-Toolbar-Aktionen RENAME_DOCUMENTATION_DATE/ADD_GRADE_COLUMN/DELETE_GRADE_COLUMN/DELETE_DOCUMENTATION_DATE als T14 nachgetragen)*
*Erweitert: 2026-06-26 — Abschnitt 13: Bucket A abgearbeitet (alle fünf Architektur-Schulden-Gruppen — Selektion, Editor-Oberfläche, Plan duplizieren, Session-Navigation, Viewport/Theme/Export/Tablegroup/Settings — auf AppState/Intent-Dispatch umgestellt, je mit Handler-Tests und isoliertem Tk-Smoke-Test verifiziert; ToggleThemeIntent dabei analog zu T8/T9 ersatzlos entfernt; zwei vorbestehende Bugs nebenbei gefixt: DuplicatePlanIntent ignorierte den Nutzer-Namen, self.default_plans_dir war nie gesetzt)*
*Erweitert: 2026-06-26 — Abschnitt 14: T10-T12 abgearbeitet (Domain-/Infrastruktur-Kern, alle Intent-Klassen und alle Handler-Funktionen dokumentiert, per AST-Scan auf 0 verbleibende fehlende Docstrings verifiziert)*
*Erweitert: 2026-06-26 — Abschnitt 14: T13 abgearbeitet ("dünne" Docstrings um Args:-Abschnitte ergänzt, 235 Treffer in 49 Dateien — fast doppelt so viele wie ursprünglich geschätzt, da T10-T12 selbst neue dünne Docstrings erzeugt hatten; per frischem AST-Scan auf 0 verbleibende Treffer verifiziert); Abschnitt 15: T14 abgearbeitet (Tastatur-Shortcuts für die vier Doku-Toolbar-Aktionen ergänzt, Kollisionsfreiheit über KeybindingRegistry.conflicts() verifiziert)*
