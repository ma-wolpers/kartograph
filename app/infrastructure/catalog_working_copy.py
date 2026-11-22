"""Lokale Arbeitskopien versionierter Katalog-Standarddateien (``symbols.json``, ``competences.json``).

Eine Regel für beide Kataloge: Die Standarddatei in ``app/infrastructure`` ist
die einzige Quelle der eingebauten Einträge; ``config/<name>.json`` ist die
lokale Arbeitskopie. Sie wird bei Fehlen oder Defekt aus der Standarddatei
erzeugt und beim Start um **neue** eingebaute Einträge ergänzt, ohne eigene
Änderungen anzutasten:

1. vorhandene Einträge werden nie überschrieben;
2. ein bewusst gelöschter Standardeintrag kommt nicht zurück, weil die
   Arbeitskopie in ``spec.known_key`` festhält, welche Standards schon angeboten
   wurden (fehlt die Liste, gelten die vorhandenen Einträge als bekannt);
3. ``spec.admit_new`` darf einen neuen Eintrag vor dem Ergänzen anpassen und
   einen Hinweis liefern (Symbole: schon vergebenes Kürzel weglassen);
4. ein Standardeintrag, der nur seine Identität gewechselt hat
   (``spec.previous_identities``, z. B. neues Zeichen eines Symbols), wird nicht
   neu ergänzt, sondern übernimmt die neue Identität im vorhandenen Eintrag
   (``_adopt_renamed``).

Die Funktionen schreiben nur beim Erzeugen/Reparieren selbst; Ergänzungen
werden als ``dirty`` gemeldet und vom Aufrufer zusammen mit der Migration
einmal geschrieben (:func:`write_working_copy`).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bw_libs.app_paths import atomic_write_json

ItemIdentity = Callable[[dict], "str | None"]
AdmitNew = Callable[[dict, list], "str | None"]


@dataclass(frozen=True)
class WorkingCopySpec:
    """Beschreibt einen Katalog für die gemeinsame Arbeitskopie-Logik.

    Attributes:
        label: Name für Warnungen, z. B. „Symbol-Konfiguration“.
        list_key: Schlüssel der Eintragsliste (``"symbols"`` / ``"competences"``).
        known_key: Schlüssel der Liste bekannter Standard-Identitäten.
        default_path: Versionierte Standarddatei.
        identity: Identität eines Eintrags (Codepoint bzw. ID), ``None`` bei ungültigen.
        admit_new: Optional; passt einen neuen Standardeintrag an die Arbeitskopie an
            (bekommt Eintrag und vorhandene Liste) und liefert ggf. einen Hinweis.
        previous_identities: Optional; frühere Identitäten eines Standardeintrags
            (z. B. alter Codepoint nach einem Glyphenwechsel). Siehe ``_adopt_renamed``.
        adopt_identity: Optional; überträgt die neue Identität aus dem Standardeintrag
            (zweites Argument) auf den vorhandenen Eintrag der Arbeitskopie (erstes Argument).
    """

    label: str
    list_key: str
    known_key: str
    default_path: Path
    identity: ItemIdentity
    admit_new: AdmitNew | None = None
    previous_identities: Callable[[dict], "tuple[str, ...]"] | None = None
    adopt_identity: Callable[[dict, dict], None] | None = None


@dataclass
class WorkingCopy:
    """Geladener Inhalt einer Arbeitskopie.

    Attributes:
        payload: JSON-Inhalt (wird von Migration und Merge verändert).
        warnings: Hinweise für die Statuszeile.
        dirty: ``True``, wenn ``payload`` vom Stand auf der Platte abweicht.
    """

    payload: dict
    warnings: list[str]
    dirty: bool = False

    def items(self, spec: WorkingCopySpec) -> list:
        """Die Eintragsliste von *spec* (Referenz, nicht Kopie).

        Args:
            spec: Katalogbeschreibung.
        """
        return self.payload[spec.list_key]


def read_default_items(spec: WorkingCopySpec) -> list:
    """Liest die Standardeinträge aus ``spec.default_path``.

    Args:
        spec: Katalogbeschreibung.
    """
    return json.loads(spec.default_path.read_text(encoding="utf-8"))[spec.list_key]


def _identities(items: list, spec: WorkingCopySpec) -> set[str]:
    """Gültige Identitäten aller Einträge in *items*.

    Args:
        items: Rohliste.
        spec: Katalogbeschreibung.
    """
    return {key for item in items if isinstance(item, dict) and (key := spec.identity(item)) is not None}


def write_working_copy(path: Path, payload: dict, spec: WorkingCopySpec) -> None:
    """Schreibt *payload* atomar nach *path*.

    Args:
        path: Arbeitskopie.
        payload: Vollständiger Inhalt inklusive Liste bekannter Standards.
        spec: Katalogbeschreibung (nur zur Absicherung gegen die Standarddatei).
    """
    _reject_default_path(path, spec)
    atomic_write_json(path, payload)


def reset_working_copy(path: Path, spec: WorkingCopySpec) -> dict:
    """Ersetzt die Arbeitskopie durch die Standards (alle als bekannt markiert) und gibt sie zurück.

    Args:
        path: Arbeitskopie.
        spec: Katalogbeschreibung.
    """
    items = read_default_items(spec)
    payload = {spec.list_key: items, spec.known_key: sorted(_identities(items, spec))}
    write_working_copy(path, payload, spec)
    return payload


def load_working_copy(path: Path, spec: WorkingCopySpec) -> WorkingCopy:
    """Lädt die Arbeitskopie, repariert sie bei Bedarf und ergänzt neue Standardeinträge.

    Args:
        path: Arbeitskopie.
        spec: Katalogbeschreibung.

    Raises:
        ValueError: *path* ist die Standarddatei selbst (Invariante).
    """
    _reject_default_path(path, spec)
    if not path.exists():
        return _merged(WorkingCopy(reset_working_copy(path, spec), []), spec)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    if not isinstance(payload, dict) or not isinstance(payload.get(spec.list_key), list):
        warning = f"{spec.label} war ungültig; Standardwerte wurden nach {path} geschrieben."
        return _merged(WorkingCopy(reset_working_copy(path, spec), [warning]), spec)
    return _merged(WorkingCopy(payload, []), spec)


def _merged(copy: WorkingCopy, spec: WorkingCopySpec) -> WorkingCopy:
    """Ergänzt in *copy* Standardeinträge, die die Arbeitskopie noch nie gesehen hat.

    Args:
        copy: Geladene Arbeitskopie (wird verändert).
        spec: Katalogbeschreibung.
    """
    items = copy.items(spec)
    present = _identities(items, spec)
    known_raw = copy.payload.get(spec.known_key)
    known = {k for k in known_raw if isinstance(k, str)} if isinstance(known_raw, list) else set(present)
    defaults = read_default_items(spec)
    notes: list[str] = []
    for item in defaults:
        key = spec.identity(item) if isinstance(item, dict) else None
        if key is None or key in known or key in present:
            continue
        if _adopt_renamed(item, items, known | present, spec):
            copy.dirty = True
            continue
        added = dict(item)
        note = spec.admit_new(added, items) if spec.admit_new else None
        if note:
            notes.append(note)
        items.append(added)
        copy.dirty = True
    all_known = sorted(known | _identities(defaults, spec))
    if copy.payload.get(spec.known_key) != all_known:
        copy.payload[spec.known_key] = all_known
        copy.dirty = True
    if notes:
        copy.warnings.append(f"{spec.label}: " + ", ".join(notes))
    return copy


def _adopt_renamed(default_item: dict, items: list, seen: set[str], spec: WorkingCopySpec) -> bool:
    """Behandelt einen Standardeintrag mit neuer Identität, den die Arbeitskopie unter einer früheren kennt.

    Regel 4 zu den Regeln oben: Ein Standardeintrag, der nur seine Identität
    gewechselt hat (z. B. neues Zeichen), ist kein neuer Eintrag.

    - Steht er unter einer früheren Identität in der Arbeitskopie, bekommt dieser
      Eintrag die neue Identität (``spec.adopt_identity``); alles andere -- auch
      eigene Änderungen an Name, Kürzel, Kompetenzen -- bleibt.
    - Ist eine frühere Identität nur bekannt (bewusst gelöscht), bleibt er gelöscht.

    Args:
        default_item: Standardeintrag mit (noch) unbekannter Identität.
        items: Einträge der Arbeitskopie (werden ggf. verändert).
        seen: Bekannte und vorhandene Identitäten der Arbeitskopie.
        spec: Katalogbeschreibung.

    Returns:
        ``True``, wenn der Eintrag damit erledigt ist (umbenannt oder gelöscht geblieben).
    """
    previous = set(spec.previous_identities(default_item)) if spec.previous_identities else set()
    if not previous & seen:
        return False
    old_item = next((i for i in items if isinstance(i, dict) and spec.identity(i) in previous), None)
    if old_item is not None and spec.adopt_identity is not None:
        spec.adopt_identity(old_item, default_item)
    return True


def _reject_default_path(path: Path, spec: WorkingCopySpec) -> None:
    """Invariante: die versionierte Standarddatei wird nie als Arbeitskopie gelesen oder beschrieben.

    Args:
        path: Zu prüfender Pfad.
        spec: Katalogbeschreibung.

    Raises:
        ValueError: *path* ist ``spec.default_path``.
    """
    if path.resolve() == spec.default_path.resolve():
        raise ValueError(f"{path} ist die Standarddatei, nicht die Arbeitskopie")
