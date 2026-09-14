from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class CreateSnapshotIntent(Intent):
    """Legt einen neuen Snapshot aus den aktuellen Tischkoordinaten an."""

    name: str


@dataclass(frozen=True)
class DeleteSnapshotIntent(Intent):
    """Entfernt einen Snapshot; der aktuelle Sitzplan bleibt unverändert."""

    snapshot_id: str


@dataclass(frozen=True)
class RenameSnapshotIntent(Intent):
    """Benennt einen Snapshot um."""

    snapshot_id: str
    new_name: str


@dataclass(frozen=True)
class RestoreSnapshotIntent(Intent):
    """Stellt die Tischkoordinaten eines Snapshots wieder her."""

    snapshot_id: str
