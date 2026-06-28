#!/usr/bin/env python3
"""Generiert eine interaktive HTML-Architekturkarte für Kartograph.

Analysiert ``app/`` und ``bw_libs/`` ausschließlich per ``ast`` (kein Import von
``app``/``bw_libs`` selbst, damit das Skript ohne Tkinter/reportlab etc. läuft)
und schreibt eine einzelne, selbstständige HTML-Datei mit eingebetteten
JSON-Daten nach ``docs/architecture-map.html``. Bei Strukturänderungen am Code
einfach erneut ausführen:

    python tools/docs/generate_architecture_map.py
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"
BW_LIBS_DIR = ROOT / "bw_libs"
DEFAULT_OUT = ROOT / "docs" / "architecture-map.html"

# ---------------------------------------------------------------------------
# Datenmodell für die gesammelten Informationen
# ---------------------------------------------------------------------------


@dataclass
class FunctionInfo:
    name: str
    args: list[str]
    doc: str


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    doc: str
    is_dataclass: bool
    fields: list[list[str]]  # [name, type-string]
    methods: list[FunctionInfo]


@dataclass
class ModuleInfo:
    path: str
    layer: str
    group: str
    status: str  # "current" | "legacy" | "neutral"
    doc: str
    classes: list[ClassInfo]
    functions: list[FunctionInfo]


# ---------------------------------------------------------------------------
# AST-Hilfsfunktionen
# ---------------------------------------------------------------------------


def _node_text(node: ast.AST) -> str:
    """Rendert einen AST-Knoten (Basisklasse, Typannotation, ...) als Quelltext."""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _call_target_name(node: ast.AST) -> str | None:
    """Liefert den Funktions-/Klassennamen eines Name- oder Attribute-Knotens."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_dataclass_decorator(decorators: list[ast.expr]) -> bool:
    for dec in decorators:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = _call_target_name(target)
        if name == "dataclass":
            return True
    return False


def _function_args(node: ast.FunctionDef) -> list[str]:
    names = [a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
    return [n for n in names if n not in ("self", "cls")]


def _scan_class(node: ast.ClassDef) -> ClassInfo:
    is_dc = _is_dataclass_decorator(node.decorator_list)
    fields: list[list[str]] = []
    methods: list[FunctionInfo] = []
    for stmt in node.body:
        if is_dc and isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append([stmt.target.id, _node_text(stmt.annotation)])
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(FunctionInfo(
                name=stmt.name,
                args=_function_args(stmt),
                doc=ast.get_docstring(stmt, clean=True) or "",
            ))
    return ClassInfo(
        name=node.name,
        bases=[_node_text(b) for b in node.bases],
        doc=ast.get_docstring(node, clean=True) or "",
        is_dataclass=is_dc,
        fields=fields,
        methods=methods,
    )


def scan_python_file(path: Path) -> tuple[str, list[ClassInfo], list[FunctionInfo]]:
    """Parst eine Python-Datei und liefert (Modul-Docstring, Klassen, Top-Level-Funktionen)."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    classes = [_scan_class(n) for n in tree.body if isinstance(n, ast.ClassDef)]
    functions = [
        FunctionInfo(name=n.name, args=_function_args(n), doc=ast.get_docstring(n, clean=True) or "")
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    doc = ast.get_docstring(tree, clean=True) or ""
    return doc, classes, functions


# ---------------------------------------------------------------------------
# Schicht-/Status-Klassifikation
# ---------------------------------------------------------------------------

_REPO_LEGACY_FILES = {"json_desk_serializer.py", "json_desk_deserializer.py", "json_plan_repository.py"}
_DOMAIN_LEGACY_FILES = {"models.py"}
_DOMAIN_CURRENT_FILES = {"models_v4.py"}


def classify(rel_path: str) -> tuple[str, str, str]:
    """Ordnet einen repo-relativen Pfad einer (Layer, Gruppe, Status) zu.

    Status ist "current" (v4/aktuell), "legacy" (v3, im Auslaufen) oder
    "neutral" (versionsunabhängig/geteilt).
    """
    p = rel_path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]

    if p.startswith("app/core/intents/"):
        return "Intents", "Intent", "current"
    if p.startswith("app/core/usecases/v4/"):
        return "Usecases", "v4", "current"
    if p.startswith("app/core/usecases/"):
        return "Usecases", "v3 (Legacy)", "legacy"
    if p.startswith("app/core/domain/"):
        if name in _DOMAIN_LEGACY_FILES:
            return "Domain", "v3 (Legacy)", "legacy"
        if name in _DOMAIN_CURRENT_FILES:
            return "Domain", "v4", "current"
        return "Domain", "Geteilt", "neutral"
    if p.startswith("app/core/ports/"):
        return "Ports", "Protocol", "neutral"
    if p.startswith("app/application/handlers/"):
        return "Application", "Handler", "current"
    if p.startswith("app/application/"):
        return "Application", "Kern", "current"
    if p.startswith("app/infrastructure/repositories/v4/"):
        return "Infrastructure", "Repository v4", "current"
    if p.startswith("app/infrastructure/repositories/"):
        if name in _REPO_LEGACY_FILES:
            return "Infrastructure", "Repository v3 (Legacy)", "legacy"
        return "Infrastructure", "Repository (geteilt)", "neutral"
    if p.startswith("app/infrastructure/exporters/"):
        return "Infrastructure", "PDF-Export", "current"
    if p.startswith("app/infrastructure/"):
        return "Infrastructure", "Konfiguration", "neutral"
    if p.startswith("app/adapters/gui/_mixin_"):
        return "GUI", "Mixin", "current"
    if p.startswith("app/adapters/gui/"):
        return "GUI", "Kern", "current"
    if p.startswith("app/adapters/bootstrap/"):
        return "Bootstrap", "Wiring", "current"
    if p.startswith("app/tools/"):
        return "Tools", "Migration", "neutral"
    if p in ("app/app.py", "app/app_info.py"):
        return "Entry", "Einstieg", "neutral"
    if p.startswith("bw_libs/ui_contract/"):
        return "Shared", "UI-Contract", "neutral"
    if p.startswith("bw_libs/"):
        return "Shared", "App-Utilities", "neutral"
    return "Sonstige", "", "neutral"


LAYER_ORDER = ["GUI", "Application", "Intents", "Usecases", "Domain", "Ports", "Infrastructure", "Bootstrap", "Entry", "Tools", "Shared", "Sonstige"]

LAYER_SUMMARY = {
    "GUI": "Tkinter-Adapter: main_window.py + 30 Mixins. Liest nur AppState, sendet nur dispatch(Intent).",
    "Application": "KartographAppController, IntentRegistry, AppState, HandlerContext, Handler-Funktionen.",
    "Intents": "40 unveränderliche Dataclasses — eine pro UI-Aktion, Basis Intent in base.py.",
    "Usecases": "Reine Funktionen, die einen SeatingPlan transformieren (v4 aktuell, v3 im Auslaufen).",
    "Domain": "Persistenz-agnostische Entitäten: SeatingPlan, Student, Session, TableGroup, ...",
    "Ports": "Repository-Protocols — entkoppeln Domäne von Persistenz-Implementierung.",
    "Infrastructure": "JSON-Repositories (v3/v4), PDF-Export, Settings-/Symbol-Konfiguration.",
    "Bootstrap": "Dependency-Injection: verdrahtet Repositories, Controller und GUI beim Start.",
    "Entry": "Anwendungs-Einstiegspunkt.",
    "Tools": "Eigenständige, app-interne Skripte (z. B. v3→v4-Migration).",
    "Shared": "bw_libs — projektübergreifende UI-Contracts (Keybinding/Popup/HSM/LaufKern) + App-Utilities.",
    "Sonstige": "Nicht eindeutig zugeordnete Module.",
}

MIXIN_GROUPS: dict[str, str] = {
    "_mixin_canvas_events.py": "Grid-Editing",
    "_mixin_grid_render.py": "Grid-Editing",
    "_mixin_grid_helpers.py": "Grid-Editing",
    "_mixin_selection.py": "Grid-Editing",
    "_mixin_viewport.py": "Grid-Editing",
    "_mixin_tablegroup_logic.py": "Grid-Editing",
    "_mixin_plan_list.py": "Plan-Verwaltung",
    "_mixin_plan_crud.py": "Plan-Verwaltung",
    "_mixin_undo_redo.py": "Plan-Verwaltung",
    "_mixin_details.py": "Detailpanel",
    "_mixin_details_layout.py": "Detailpanel",
    "_mixin_docs_view.py": "Dokumentationsansicht",
    "_mixin_docs_table.py": "Dokumentationsansicht",
    "_mixin_docs_nav.py": "Dokumentationsansicht",
    "_mixin_docs_events.py": "Dokumentationsansicht",
    "_mixin_docs_edit.py": "Dokumentationsansicht",
    "_mixin_docs_dialogs.py": "Dokumentationsansicht",
    "_mixin_layout_docs.py": "Dokumentationsansicht",
    "_mixin_menu.py": "Menü & Einstellungen",
    "_mixin_settings.py": "Menü & Einstellungen",
    "_mixin_theme.py": "Menü & Einstellungen",
    "_mixin_tablegroup.py": "Menü & Einstellungen",
    "_mixin_popup.py": "Menü & Einstellungen",
    "_mixin_laufkern.py": "Shortcuts & Export",
    "_mixin_shortcuts.py": "Shortcuts & Export",
    "_mixin_shortcut_handlers.py": "Shortcuts & Export",
    "_mixin_export.py": "Shortcuts & Export",
    "_mixin_pdf.py": "Shortcuts & Export",
    "_mixin_layout.py": "Layout & Edit",
    "_mixin_edit.py": "Layout & Edit",
}
MIXIN_GROUP_ORDER = ["Grid-Editing", "Plan-Verwaltung", "Detailpanel", "Dokumentationsansicht", "Menü & Einstellungen", "Shortcuts & Export", "Layout & Edit"]


# ---------------------------------------------------------------------------
# Verzeichnis-Scan
# ---------------------------------------------------------------------------


def _meaningful(name: str, doc: str, classes: list[ClassInfo], functions: list[FunctionInfo]) -> bool:
    if name != "__init__.py":
        return True
    return bool(doc or classes or functions)


def walk_layers(dirs: list[Path]) -> tuple[list[ModuleInfo], dict[str, str]]:
    """Scannt alle .py-Dateien unter *dirs* und liefert (Module, Klassen-Index).

    Der Klassen-Index bildet jeden gefundenen Klassennamen auf seinen
    repo-relativen Modulpfad ab (für Cross-Referenzen wie Mixin-Komposition).
    """
    modules: list[ModuleInfo] = []
    class_index: dict[str, str] = {}
    for base in dirs:
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            doc, classes, functions = scan_python_file(path)
            if not _meaningful(path.name, doc, classes, functions):
                continue
            layer, group, status = classify(rel)
            modules.append(ModuleInfo(path=rel, layer=layer, group=group, status=status, doc=doc, classes=classes, functions=functions))
            for cls in classes:
                class_index.setdefault(cls.name, rel)
    return modules, class_index


# ---------------------------------------------------------------------------
# Intent -> Handler -> Usecase
# ---------------------------------------------------------------------------


def _register_calls(controller_path: Path) -> list[tuple[str, str | None]]:
    tree = ast.parse(controller_path.read_text(encoding="utf-8-sig"))
    register_func = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_register_handlers"
    )
    pairs: list[tuple[str, str | None]] = []
    for node in ast.walk(register_func):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register"):
            continue
        if len(node.args) < 2:
            continue
        intent_name = _call_target_name(node.args[0])
        handler_name = None
        lam = node.args[1]
        if isinstance(lam, ast.Lambda) and isinstance(lam.body, ast.Call):
            handler_name = _call_target_name(lam.body.func)
        if intent_name:
            pairs.append((intent_name, handler_name))
    return pairs


def _handler_usecase_calls(handler_path: Path) -> dict[str, list[str]]:
    tree = ast.parse(handler_path.read_text(encoding="utf-8-sig"))
    usecase_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and "usecases" in node.module:
            for alias in node.names:
                usecase_names.add(alias.asname or alias.name)
    result: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("handle_"):
            called = {
                sub.func.id
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in usecase_names
            }
            result[node.name] = sorted(called)
    return result


def build_intent_map(modules: list[ModuleInfo], class_index: dict[str, str]) -> list[dict]:
    """Baut die Intent -> Handler -> Usecase-Zuordnung per AST-Analyse von app_controller.py."""
    controller_path = APP_DIR / "application" / "app_controller.py"
    handlers_dir = APP_DIR / "application" / "handlers"

    handler_func_to_file: dict[str, str] = {}
    usecase_calls_by_file: dict[str, dict[str, list[str]]] = {}
    for path in sorted(handlers_dir.glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        calls = _handler_usecase_calls(path)
        usecase_calls_by_file[rel] = calls
        for fname in calls:
            handler_func_to_file[fname] = rel

    usecase_name_to_file: dict[str, str] = {}
    for mod in modules:
        if mod.layer == "Usecases":
            for fn in mod.functions:
                usecase_name_to_file.setdefault(fn.name, mod.path)

    intent_domain_by_name: dict[str, str] = {}
    for mod in modules:
        if mod.layer == "Intents" and mod.group == "Intent":
            domain = mod.path.rsplit("/", 1)[-1].removesuffix("_intents.py").replace("_", " ").title()
            for cls in mod.classes:
                intent_domain_by_name[cls.name] = domain

    rows = []
    for intent_name, handler_name in _register_calls(controller_path):
        handler_file = handler_func_to_file.get(handler_name or "")
        usecases = usecase_calls_by_file.get(handler_file, {}).get(handler_name or "", []) if handler_file else []
        rows.append({
            "intent": intent_name,
            "domain": intent_domain_by_name.get(intent_name, "?"),
            "intent_path": class_index.get(intent_name),
            "handler": handler_name,
            "handler_path": handler_file,
            "usecases": usecases,
            "usecase_paths": {u: usecase_name_to_file.get(u) for u in usecases},
        })
    rows.sort(key=lambda r: (r["domain"], r["intent"]))
    return rows


# ---------------------------------------------------------------------------
# GUI-Mixin-Komposition
# ---------------------------------------------------------------------------


def build_mixin_list(class_index: dict[str, str], modules_by_path: dict[str, ModuleInfo]) -> list[dict]:
    main_window_path = APP_DIR / "adapters" / "gui" / "main_window.py"
    tree = ast.parse(main_window_path.read_text(encoding="utf-8-sig"))
    cls_node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "KartographMainWindow")
    base_names = [_node_text(b) for b in cls_node.bases]

    rows = []
    for base in base_names:
        file_path = class_index.get(base)
        if not file_path or "_mixin_" not in file_path:
            continue  # TkRootHost & andere Nicht-Mixin-Basen (bw_libs) auslassen
        file_name = file_path.rsplit("/", 1)[-1]
        group = MIXIN_GROUPS.get(file_name, "Sonstige")
        doc = ""
        mod = modules_by_path.get(file_path)
        if mod:
            for cls in mod.classes:
                if cls.name == base:
                    doc = cls.doc
                    break
        rows.append({"cls": base, "file": file_path, "group": group, "doc": doc})
    return rows


# ---------------------------------------------------------------------------
# Domänenmodell-Baum (v4) + Legacy-Liste (v3)
# ---------------------------------------------------------------------------


def build_domain_model(modules_by_path: dict[str, ModuleInfo]) -> dict:
    v4_path = "app/core/domain/models_v4.py"
    v3_path = "app/core/domain/models.py"
    v4 = modules_by_path.get(v4_path)
    classes: dict[str, dict] = {}
    if v4:
        for cls in v4.classes:
            if cls.is_dataclass:
                classes[cls.name] = {"doc": cls.doc, "fields": cls.fields}
    legacy = []
    v3 = modules_by_path.get(v3_path)
    if v3:
        legacy = [{"name": c.name, "doc": c.doc} for c in v3.classes]
    return {"root": "SeatingPlan", "classes": classes, "legacy": legacy}


EXAMPLE_JSON_V4 = """{
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
          "color_tags": ["gelb", "rot"],
          "accommodations": ["Zeitzuschlag 25 %"]
        }
      }
    ]
  },
  "tablegroups": [
    { "group_id": 1, "seats": [
      { "x": 1, "y": 0, "shift_x": 0.03, "shift_y": -0.02, "rotation": 1.5 }
    ] }
  ],
  "color_palette": {
    "gelb": { "label": "Gelb", "hex": "#f4d35e", "meaning": "Förderbedarf" }
  },
  "documentation": {
    "grade_columns": [
      { "column_id": "3f8a1c2d", "category": "schriftlich", "title": "Mathearbeit 1", "created_at": "2025-09-01" }
    ],
    "grade_weighting": { "written_percent": 60, "sonstige_percent": 40 },
    "sessions": [
      { "date": "2025-09-01", "entries": {
        "f47ac10b-58cc-4372-a567-0e02b2c3d479": {
          "symbols": { "Beteiligung": 2 }, "grades": { "3f8a1c2d": 2.5 }, "note": "Sehr konzentriert"
        }
      } }
    ]
  }
}"""


# ---------------------------------------------------------------------------
# Datenfluss (statischer, kuratierter Ablauf — siehe app_controller.py/intent_registry.py)
# ---------------------------------------------------------------------------

DATA_FLOW_STEPS = [
    ("GUI-Mixin", "Eine Mixin-Methode reagiert auf Klick/Tastatur und ruft ausschließlich self._controller.dispatch(SomeIntent(...)) auf — kein Usecase-Import, keine direkte State-Mutation."),
    ("AppController.dispatch()", "Reicht den Intent an die IntentRegistry weiter und merkt sich den bisherigen AppState zum Vergleich."),
    ("IntentRegistry.dispatch()", "Sucht den für den Intent-Typ registrierten Handler; ohne Treffer oder bei einer Exception bleibt der State unverändert (geloggt)."),
    ("Handler-Funktion", "handle_xxx(intent, state, ctx) prüft Vorbedingungen, ruft eine oder mehrere Usecase-Funktionen auf und schreibt über ctx.history/ctx.plan_repository."),
    ("Usecase-Funktion", "Reine Funktion, die aus dem aktuellen SeatingPlan einen neuen SeatingPlan ableitet (Immutable-Update, kein In-Place-Mutieren)."),
    ("Repository / Persistenz", "JsonSeatingPlanRepositoryV4 schreibt die Plandatei + Backup; PlanHistory zeichnet den Undo/Redo-Schritt auf."),
    ("Neuer AppState", "Der Handler gibt einen neuen, unveränderlichen AppState zurück (dataclasses.replace)."),
    ("on_state_changed-Callback", "AppController ruft den Callback nur auf, wenn sich der State tatsächlich geändert hat."),
    ("apply_state() in der GUI", "main_window.py verteilt den neuen State an alle Mixins; diese lesen nur state.* und rendern neu — keine Logik in der GUI-Schicht."),
]


# ---------------------------------------------------------------------------
# HTML-Rendering
# ---------------------------------------------------------------------------


def render_html(data: dict) -> str:
    json_blob = json.dumps(data, ensure_ascii=False)
    html = _HTML_TEMPLATE.replace("__ARCH_DATA_JSON__", json_blob)
    html = html.replace("__GENERATED_AT__", data["generated_at"])
    return html


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Kartograph — Architektur-Karte</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
  --bg: #f6f5f1; --panel: #ffffff; --ink: #2a2a28; --muted: #6b6a64;
  --line: #ddd9d0; --accent: #2f6f5e; --accent-soft: #e4f0ec;
  --legacy: #b5793a; --legacy-soft: #f6e9d8; --current: #2f6f5e;
  --mono: "SF Mono", Consolas, "Cascadia Mono", monospace;
}
:root[data-theme="dark"] {
  --bg: #1c1d1b; --panel: #25261f; --ink: #ece9e2; --muted: #9b9a92;
  --line: #3a3b34; --accent: #6fbfa4; --accent-soft: #243b34; --legacy: #d9a25c; --legacy-soft: #3a2f1c;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  background: var(--bg); color: var(--ink); display: flex; height: 100vh; overflow: hidden;
}
#sidebar {
  width: 230px; flex: none; background: var(--panel); border-right: 1px solid var(--line);
  display: flex; flex-direction: column; padding: 14px 10px; overflow-y: auto;
}
#sidebar h1 { font-size: 15px; margin: 4px 8px 2px; }
#sidebar .sub { font-size: 11px; color: var(--muted); margin: 0 8px 14px; }
.navbtn {
  display: block; width: 100%; text-align: left; padding: 9px 10px; margin-bottom: 3px;
  border: none; background: none; border-radius: 8px; font-size: 13.5px; color: var(--ink); cursor: pointer;
}
.navbtn:hover { background: var(--accent-soft); }
.navbtn.active { background: var(--accent); color: white; }
#search {
  margin: 10px 8px; padding: 7px 9px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); color: var(--ink); font-size: 13px;
}
#themeToggle {
  margin: auto 8px 0; padding: 7px 9px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); color: var(--ink); cursor: pointer; font-size: 12px;
}
#main { flex: 1; overflow-y: auto; padding: 26px 34px 60px; }
.section { display: none; max-width: 1100px; }
.section.active { display: block; }
h2 { font-size: 19px; margin-top: 0; }
.hint { color: var(--muted); font-size: 13px; margin-bottom: 18px; }
.badge {
  display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 999px; margin-left: 6px;
  vertical-align: middle; font-weight: 600;
}
.badge.current { background: var(--accent-soft); color: var(--accent); }
.badge.legacy { background: var(--legacy-soft); color: var(--legacy); }
.badge.neutral { background: var(--line); color: var(--muted); }

/* Überblick */
.layerbox {
  border: 1px solid var(--line); background: var(--panel); border-radius: 10px; padding: 12px 16px;
  margin-bottom: 10px; cursor: pointer; transition: border-color .15s;
}
.layerbox:hover { border-color: var(--accent); }
.layerbox .name { font-weight: 600; font-size: 14px; }
.layerbox .desc { font-size: 12.5px; color: var(--muted); margin-top: 3px; }
.arrowdown { text-align: center; color: var(--muted); font-size: 13px; margin: 2px 0; }
#crosscut { border: 1px dashed var(--line); border-radius: 10px; padding: 10px 16px; margin-top: 14px; font-size: 12.5px; color: var(--muted); }

/* Datenfluss */
.flowstep { display: flex; gap: 14px; margin-bottom: 4px; }
.flowstep .num {
  flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: white;
  display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
}
.flowstep .body { padding-bottom: 18px; border-left: 2px solid var(--line); margin-left: 13px; padding-left: 20px; }
.flowstep:last-child .body { border-left: none; }
.flowstep .title { font-weight: 600; font-size: 13.5px; margin-bottom: 2px; font-family: var(--mono); }
.flowstep .desc { font-size: 12.5px; color: var(--muted); }

/* Module-Explorer */
#moduleLayout { display: flex; gap: 22px; }
#tree { flex: 1; min-width: 320px; font-size: 13px; }
#tree details { margin-bottom: 1px; }
#tree summary { cursor: pointer; padding: 3px 4px; border-radius: 5px; }
#tree summary:hover { background: var(--accent-soft); }
#tree .dirname { font-weight: 600; }
.filerow {
  display: block; width: 100%; text-align: left; padding: 3px 6px 3px 22px; border: none; background: none;
  color: var(--ink); cursor: pointer; border-radius: 5px; font-family: var(--mono); font-size: 12.5px;
}
.filerow:hover { background: var(--accent-soft); }
.filerow.flash { background: var(--accent); color: white; }
#detail { flex: 1; min-width: 360px; border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; background: var(--panel); align-self: flex-start; max-height: 80vh; overflow-y: auto; }
#detail .path { font-family: var(--mono); font-size: 12px; color: var(--muted); margin-bottom: 10px; }
#detail .moddoc { font-size: 13px; white-space: pre-wrap; margin-bottom: 14px; }
#detail .entry { margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
#detail .entry .sig { font-family: var(--mono); font-size: 12.5px; font-weight: 600; }
#detail .entry .doc { font-size: 12px; color: var(--muted); white-space: pre-wrap; margin-top: 2px; }
#detail .field { font-family: var(--mono); font-size: 12px; margin: 2px 0 2px 10px; }
#detailEmpty { color: var(--muted); font-size: 13px; }

/* Tabellen */
table.datatable { width: 100%; border-collapse: collapse; font-size: 12.5px; }
table.datatable th { text-align: left; padding: 6px 8px; border-bottom: 2px solid var(--line); color: var(--muted); font-size: 11.5px; text-transform: uppercase; }
table.datatable td { padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
table.datatable tr:hover td { background: var(--accent-soft); }
.codelink { font-family: var(--mono); color: var(--accent); cursor: pointer; background: none; border: none; padding: 0; text-decoration: underline; font-size: 12.5px; }
.usecasepill { display: inline-block; margin: 1px 3px 1px 0; padding: 1px 6px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-family: var(--mono); font-size: 11.5px; cursor: pointer; }

/* Mixins */
.mixingroup { margin-bottom: 20px; }
.mixingroup h3 { font-size: 13.5px; margin: 0 0 8px; color: var(--accent); }
.mixinrow { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; cursor: pointer; }
.mixinrow:hover { border-color: var(--accent); }
.mixinrow .cls { font-family: var(--mono); font-weight: 600; font-size: 12.5px; }
.mixinrow .doc { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* Domänenmodell */
.modeltree { font-size: 13px; }
.modelnode { border-left: 2px solid var(--line); padding-left: 14px; margin: 6px 0; }
.modelnode .cname { font-family: var(--mono); font-weight: 700; }
.modelnode .cdoc { font-size: 12px; color: var(--muted); margin: 2px 0 4px; }
.modelnode .f { font-family: var(--mono); font-size: 12px; margin: 1px 0; }
.modelnode .f .ftype { color: var(--accent); }
pre.jsonexample { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; font-size: 11.5px; overflow-x: auto; }
.legacylist .item { font-family: var(--mono); font-size: 12.5px; margin: 4px 0; }
.legacylist .item .doc { color: var(--muted); font-family: system-ui; font-size: 12px; }

.hidden-by-search { display: none !important; }
</style>
</head>
<body>

<nav id="sidebar">
  <h1>Kartograph</h1>
  <p class="sub">Architektur-Karte &middot; generiert __GENERATED_AT__</p>
  <input id="search" type="text" placeholder="Suchen…">
  <button class="navbtn active" data-section="overview">Überblick</button>
  <button class="navbtn" data-section="flow">Datenfluss</button>
  <button class="navbtn" data-section="modules">Module</button>
  <button class="navbtn" data-section="intents">Intents</button>
  <button class="navbtn" data-section="mixins">GUI-Mixins</button>
  <button class="navbtn" data-section="model">Domänenmodell</button>
  <button id="themeToggle">Hell/Dunkel</button>
</nav>

<main id="main">

  <section class="section active" id="sec-overview">
    <h2>Überblick</h2>
    <p class="hint">Schichten von oben (Benutzer-Interaktion) nach unten (Persistenz). Klick auf eine Schicht filtert den Modul-Explorer.</p>
    <div id="layerBoxes"></div>
    <div id="crosscut">bw_libs/ (UI-Contracts: Keybinding/Popup/HSM/LaufKern) und bw-gui/ (Tkinter-Widget-Submodul) werden von mehreren Schichten quer genutzt, v. a. von GUI und Application.</div>
  </section>

  <section class="section" id="sec-flow">
    <h2>Datenfluss: Intent-Dispatch-Zyklus</h2>
    <p class="hint">Jede Benutzeraktion läuft denselben neunstufigen Zyklus durch — keine GUI-Mixin-Methode mutiert den Plan direkt.</p>
    <div id="flowSteps"></div>
  </section>

  <section class="section" id="sec-modules">
    <h2>Module</h2>
    <p class="hint">Echte Verzeichnisstruktur von app/ und bw_libs/. Klick auf eine Datei zeigt Docstrings, Klassen und Funktionen.</p>
    <div id="moduleLayout">
      <div id="tree"></div>
      <div id="detail"><p id="detailEmpty">Datei auswählen…</p></div>
    </div>
  </section>

  <section class="section" id="sec-intents">
    <h2>Intent-Katalog</h2>
    <p class="hint">Alle Intent-Klassen, gruppiert nach Domäne, mit ihrem registrierten Handler und den davon aufgerufenen Usecase-Funktionen (per AST aus app_controller.py + den Handler-Dateien extrahiert).</p>
    <div id="intentTable"></div>
  </section>

  <section class="section" id="sec-mixins">
    <h2>GUI-Mixins</h2>
    <p class="hint">KartographMainWindow setzt sich aus 30 Mixins zusammen (Reihenfolge wie im Quelltext), hier nach Verantwortungsbereich gruppiert. Klick springt zur Datei im Modul-Explorer.</p>
    <div id="mixinGroups"></div>
  </section>

  <section class="section" id="sec-model">
    <h2>Domänenmodell (Format v4)</h2>
    <p class="hint">Feldbaum aus models_v4.py, ausgehend vom Aggregat-Root SeatingPlan. Daneben: das v3-Legacy-Modell (models.py), das nur noch vom Migrationsskript benötigt wird.</p>
    <div style="display:flex; gap:28px; flex-wrap:wrap;">
      <div style="flex:1; min-width:340px;">
        <h3>Aktuell (v4)</h3>
        <div class="modeltree" id="modelTree"></div>
      </div>
      <div style="flex:1; min-width:260px;">
        <h3>Legacy (v3)</h3>
        <div class="legacylist" id="legacyList"></div>
      </div>
    </div>
    <h3 style="margin-top:26px;">Beispiel: v4-JSON-Wireformat</h3>
    <pre class="jsonexample" id="jsonExample"></pre>
  </section>

</main>

<script>
window.__ARCH_DATA__ = __ARCH_DATA_JSON__;
(function () {
  const data = window.__ARCH_DATA__;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---- Theme ----
  const root = document.documentElement;
  root.setAttribute("data-theme", localStorage.getItem("archmap-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  $("#themeToggle").addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("archmap-theme", next);
  });

  // ---- Navigation ----
  $$(".navbtn[data-section]").forEach(btn => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
  });
  function showSection(key) {
    $$(".navbtn[data-section]").forEach(b => b.classList.toggle("active", b.dataset.section === key));
    $$(".section").forEach(s => s.classList.toggle("active", s.id === "sec-" + key));
  }

  // ---- Überblick ----
  const layerHost = $("#layerBoxes");
  data.layers.forEach((l, i) => {
    const box = document.createElement("div");
    box.className = "layerbox";
    box.innerHTML = '<div class="name">' + l.label + '</div><div class="desc">' + l.summary + '</div>';
    box.addEventListener("click", () => { showSection("modules"); filterTreeByLayer(l.label); });
    layerHost.appendChild(box);
    if (i < data.layers.length - 1) {
      const arrow = document.createElement("div");
      arrow.className = "arrowdown";
      arrow.textContent = "↓";
      layerHost.appendChild(arrow);
    }
  });

  // ---- Datenfluss ----
  const flowHost = $("#flowSteps");
  data.flow.forEach((step, i) => {
    const div = document.createElement("div");
    div.className = "flowstep";
    div.innerHTML = '<div class="num">' + (i + 1) + '</div><div class="body"><div class="title">' + step[0] + '</div><div class="desc">' + step[1] + '</div></div>';
    flowHost.appendChild(div);
  });

  // ---- Modul-Baum ----
  function buildTree(modules) {
    const root = {};
    modules.forEach(m => {
      const parts = m.path.split("/");
      let node = root;
      parts.forEach((part, i) => {
        if (i === parts.length - 1) {
          node.__files = node.__files || [];
          node.__files.push(m);
        } else {
          node[part] = node[part] || {};
          node = node[part];
        }
      });
    });
    return root;
  }
  const moduleByPath = {};
  data.modules.forEach(m => { moduleByPath[m.path] = m; });
  const treeData = buildTree(data.modules);

  function renderTree(node, host) {
    Object.keys(node).filter(k => k !== "__files").sort().forEach(dirName => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.innerHTML = '<span class="dirname">' + dirName + '/</span>';
      details.appendChild(summary);
      const childHost = document.createElement("div");
      childHost.style.marginLeft = "14px";
      details.appendChild(childHost);
      renderTree(node[dirName], childHost);
      host.appendChild(details);
    });
    (node.__files || []).sort((a, b) => a.path.localeCompare(b.path)).forEach(m => {
      const btn = document.createElement("button");
      btn.className = "filerow";
      btn.dataset.modulePath = m.path;
      const fname = m.path.split("/").pop();
      const badge = m.status === "current" ? " ●v4" : m.status === "legacy" ? " ●v3" : "";
      btn.textContent = fname + badge;
      btn.addEventListener("click", () => showModuleDetail(m.path));
      host.appendChild(btn);
    });
  }
  renderTree(treeData, $("#tree"));

  function showModuleDetail(path) {
    const m = moduleByPath[path];
    const host = $("#detail");
    if (!m) { host.innerHTML = '<p id="detailEmpty">Datei auswählen…</p>'; return; }
    let html = '<div class="path">' + m.path + '<span class="badge ' + m.status + '">' + m.group + '</span></div>';
    if (m.doc) html += '<div class="moddoc">' + escapeHtml(m.doc) + '</div>';
    m.classes.forEach(c => {
      html += '<div class="entry"><div class="sig">class ' + c.name + (c.bases.length ? '(' + c.bases.join(", ") + ')' : '') + '</div>';
      if (c.doc) html += '<div class="doc">' + escapeHtml(c.doc) + '</div>';
      c.fields.forEach(f => { html += '<div class="field">' + f[0] + ': ' + escapeHtml(f[1]) + '</div>'; });
      c.methods.forEach(meth => {
        html += '<div class="field">def ' + meth.name + '(' + meth.args.join(", ") + ')' + (meth.doc ? ' — ' + escapeHtml(meth.doc.split("\n")[0]) : '') + '</div>';
      });
      html += '</div>';
    });
    m.functions.forEach(fn => {
      html += '<div class="entry"><div class="sig">def ' + fn.name + '(' + fn.args.join(", ") + ')</div>';
      if (fn.doc) html += '<div class="doc">' + escapeHtml(fn.doc) + '</div>';
      html += '</div>';
    });
    host.innerHTML = html;
  }

  function revealModule(path) {
    if (!path) return;
    showSection("modules");
    const btn = $('.filerow[data-module-path="' + path + '"]');
    if (!btn) return;
    let el = btn;
    while (el) {
      const det = el.closest ? el.closest("details") : null;
      if (!det) break;
      det.open = true;
      el = det.parentElement;
    }
    btn.scrollIntoView({ block: "center" });
    btn.classList.add("flash");
    setTimeout(() => btn.classList.remove("flash"), 900);
    showModuleDetail(path);
  }

  function filterTreeByLayer(layerLabel) {
    $$(".filerow").forEach(btn => {
      const m = moduleByPath[btn.dataset.modulePath];
      const match = !layerLabel || m.layer === layerLabel;
      btn.classList.toggle("hidden-by-search", !match);
    });
  }

  // ---- Intent-Tabelle ----
  const intentHost = $("#intentTable");
  let tableHtml = '<table class="datatable"><thead><tr><th>Domäne</th><th>Intent</th><th>Handler</th><th>Usecase(s)</th></tr></thead><tbody>';
  data.intents.forEach(row => {
    const intentCell = row.intent_path
      ? '<button class="codelink" data-jump="' + row.intent_path + '">' + row.intent + '</button>'
      : row.intent;
    const handlerCell = row.handler_path
      ? '<button class="codelink" data-jump="' + row.handler_path + '">' + row.handler + '</button>'
      : (row.handler || "—");
    const usecaseCell = row.usecases.length
      ? row.usecases.map(u => '<span class="usecasepill" data-jump="' + (row.usecase_paths[u] || "") + '">' + u + '</span>').join("")
      : '<span style="color:var(--muted)">— (direkt im Handler)</span>';
    tableHtml += '<tr data-search="' + (row.domain + " " + row.intent + " " + (row.handler || "") + " " + row.usecases.join(" ")).toLowerCase() + '">' +
      '<td>' + row.domain + '</td><td>' + intentCell + '</td><td>' + handlerCell + '</td><td>' + usecaseCell + '</td></tr>';
  });
  tableHtml += "</tbody></table>";
  intentHost.innerHTML = tableHtml;
  intentHost.addEventListener("click", e => {
    const t = e.target.closest("[data-jump]");
    if (t && t.dataset.jump) revealModule(t.dataset.jump);
  });

  // ---- Mixins ----
  const mixinHost = $("#mixinGroups");
  data.mixin_group_order.forEach(group => {
    const rows = data.mixins.filter(m => m.group === group);
    if (!rows.length) return;
    const wrap = document.createElement("div");
    wrap.className = "mixingroup";
    wrap.innerHTML = "<h3>" + group + " (" + rows.length + ")</h3>";
    rows.forEach(m => {
      const div = document.createElement("div");
      div.className = "mixinrow";
      div.dataset.search = (m.cls + " " + m.doc).toLowerCase();
      div.innerHTML = '<div class="cls">' + m.cls + '</div><div class="doc">' + escapeHtml(m.doc) + '</div>';
      div.addEventListener("click", () => revealModule(m.file));
      wrap.appendChild(div);
    });
    mixinHost.appendChild(wrap);
  });

  // ---- Domänenmodell ----
  function renderModelNode(name, visited) {
    if (visited.has(name) || !data.model.classes[name]) return "";
    visited.add(name);
    const cls = data.model.classes[name];
    let html = '<div class="modelnode"><div class="cname">' + name + '</div>';
    if (cls.doc) html += '<div class="cdoc">' + escapeHtml(cls.doc) + '</div>';
    cls.fields.forEach(f => {
      html += '<div class="f">' + f[0] + ': <span class="ftype">' + escapeHtml(f[1]) + '</span></div>';
      const refs = (f[1].match(/[A-Z][A-Za-z0-9]+/g) || []).filter(r => data.model.classes[r] && r !== name);
      refs.forEach(r => { html += renderModelNode(r, visited); });
    });
    html += "</div>";
    return html;
  }
  $("#modelTree").innerHTML = renderModelNode(data.model.root, new Set());

  let legacyHtml = "";
  data.model.legacy.forEach(c => {
    legacyHtml += '<div class="item">' + c.name + (c.doc ? '<div class="doc">' + escapeHtml(c.doc) + '</div>' : '') + '</div>';
  });
  $("#legacyList").innerHTML = legacyHtml || '<p class="hint">Keine Klassen gefunden.</p>';
  $("#jsonExample").textContent = data.example_json;

  // ---- Suche ----
  $("#search").addEventListener("input", e => {
    const q = e.target.value.trim().toLowerCase();
    // Modul-Baum
    $$(".filerow").forEach(btn => {
      const hay = btn.textContent.toLowerCase() + " " + (moduleByPath[btn.dataset.modulePath]?.doc || "").toLowerCase();
      const match = !q || hay.includes(q);
      btn.classList.toggle("hidden-by-search", !match);
      if (match && q) { let det = btn.closest("details"); while (det) { det.open = true; det = det.parentElement.closest ? det.parentElement.closest("details") : null; } }
    });
    // Intent-Tabelle
    $$("#intentTable tbody tr").forEach(tr => {
      tr.classList.toggle("hidden-by-search", !(!q || tr.dataset.search.includes(q)));
    });
    // Mixins
    $$(".mixinrow").forEach(row => {
      row.classList.toggle("hidden-by-search", !(!q || row.dataset.search.includes(q)));
    });
  });

  function escapeHtml(s) {
    return (s || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def build_data() -> dict:
    """Sammelt alle Architekturdaten per AST-Scan und liefert sie als JSON-fähiges dict."""
    modules, class_index = walk_layers([APP_DIR, BW_LIBS_DIR])
    modules_by_path = {m.path: m for m in modules}

    layers = [
        {"label": layer, "summary": LAYER_SUMMARY.get(layer, "")}
        for layer in LAYER_ORDER
        if any(m.layer == layer for m in modules)
    ]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "layers": layers,
        "modules": [asdict(m) for m in modules],
        "intents": build_intent_map(modules, class_index),
        "mixins": build_mixin_list(class_index, modules_by_path),
        "mixin_group_order": MIXIN_GROUP_ORDER,
        "model": build_domain_model(modules_by_path),
        "flow": DATA_FLOW_STEPS,
        "example_json": EXAMPLE_JSON_V4,
    }


def generate(out_path: Path) -> Path:
    """Erzeugt die Architekturdaten und schreibt die gerenderte HTML-Karte nach *out_path*."""
    data = build_data()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(data), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generiert die interaktive Kartograph-Architekturkarte (HTML).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Ausgabepfad der HTML-Datei.")
    args = parser.parse_args()
    out = generate(args.out)
    print(f"Architekturkarte geschrieben: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
