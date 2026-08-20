from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.intents.base import Intent


@dataclass(frozen=True)
class OpenPlanIntent(Intent):
    """Öffnet den Sitzplan unter *plan_path* und macht ihn zum aktuellen Plan."""

    plan_path: Path


@dataclass(frozen=True)
class CreatePlanIntent(Intent):
    """Legt einen neuen, leeren Sitzplan mit Anzeigename *name* an und öffnet ihn."""

    name: str


@dataclass(frozen=True)
class RenamePlanIntent(Intent):
    """Benennt den Plan unter *plan_path* zu *new_name* um (verschiebt ggf. die Datei)."""

    plan_path: Path
    new_name: str


@dataclass(frozen=True)
class DeletePlanIntent(Intent):
    """Löscht die Plandatei unter *plan_path* unwiderruflich."""

    plan_path: Path


@dataclass(frozen=True)
class ArchivePlanIntent(Intent):
    """Verschiebt den Plan unter *plan_path* ins Archiv (ALT-Unterordner)."""

    plan_path: Path


@dataclass(frozen=True)
class RestorePlanIntent(Intent):
    """Verschiebt den archivierten Plan unter *plan_path* zurück in den Plan-Ordner."""

    plan_path: Path


@dataclass(frozen=True)
class DuplicatePlanIntent(Intent):
    """Dupliziert den Plan unter *plan_path* als neuen Plan mit Namen *new_name*.

    Args:
        plan_path: Quell-Plandatei.
        new_name: Anzeigename des Duplikats.
        overwrite: Überschreibt eine bereits vorhandene Zieldatei, wenn True.
    """

    plan_path: Path
    new_name: str
    overwrite: bool = False
