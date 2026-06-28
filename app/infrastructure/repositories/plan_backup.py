"""Backup-Schreiber für Sitzplandateien.

Sichert Pläne als versionierte Snapshots in einem plattformspezifischen
App-Daten-Verzeichnis. Ältere Snapshots werden automatisch rotiert,
sobald das Limit pro Plan überschritten wird.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.app_info import APP_INFO
from bw_libs.app_paths import atomic_write_json


class PlanBackupWriter:
    """Schreibt Backup-Snapshots von Sitzplandaten auf die Festplatte.

    Snapshots werden als Zeitstempel-benannte JSON-Dateien in einem
    planspezifischen Unterverzeichnis gespeichert. Pro Plan werden maximal
    ``_BACKUP_LIMIT_PER_PLAN`` Snapshots aufbewahrt; ältere werden gelöscht.
    """

    _BACKUP_LIMIT_PER_PLAN = 20

    def backup_root_dir(self) -> Path:
        """Gibt das plattformspezifische Wurzelverzeichnis für Backups zurück.

        Unter Windows wird ``%APPDATA%/<app>/backups`` verwendet; auf anderen
        Systemen ``~/.{app}/backups``.

        Returns:
            Pfad zum Backup-Wurzelverzeichnis (muss nicht existieren).
        """
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_INFO.appdata_folder / "backups"
        return Path.home() / f".{APP_INFO.appdata_folder.lower()}" / "backups"

    def write_backup(self, plan_path: Path, payload: dict, root_dir: Path | None = None) -> None:
        """Schreibt einen Snapshot von *payload* als Backup-Datei.

        Der Snapshot wird im Unterverzeichnis ``<backup_root>/<plan_stem>/``
        gespeichert. Schlägt das Schreiben fehl, wird die Ausnahme still
        unterdrückt, damit normale Speicheroperationen nicht blockiert werden.

        Args:
            plan_path: Pfad der Plandatei (Dateiname dient als Backup-Ordnername).
            payload: Serialisiertes Plan-Dict (bereits JSON-kompatibel).
            root_dir: Überschreibt das Backup-Wurzelverzeichnis (für Tests/Repository-Hooks).
        """
        try:
            backup_dir = (root_dir if root_dir is not None else self.backup_root_dir()) / plan_path.stem
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = backup_dir / f"{timestamp}.json"
            atomic_write_json(backup_path, payload)

            backups = sorted(backup_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
            for stale in backups[self._BACKUP_LIMIT_PER_PLAN:]:
                stale.unlink(missing_ok=True)
        except Exception:
            return
