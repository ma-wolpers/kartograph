"""JSON-basiertes Repository für Sitzplandateien.

Koordiniert Lade-, Speicher-, Backup- und Verwaltungsoperationen auf
Sitzplänen im Dateisystem. Die eigentliche Serialisierung und das Backup-
Schreiben werden an spezialisierte Module delegiert.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path

from bw_libs.app_paths import atomic_write_json

from app.core.domain.models import Desk, SeatingPlan
from app.infrastructure.repositories.json_desk_deserializer import deserialize_plan
from app.infrastructure.repositories.json_desk_serializer import serialize_plan
from app.infrastructure.repositories.plan_backup import PlanBackupWriter

import json


class JsonSeatingPlanRepository:
    """Liest und schreibt Sitzpläne als JSON-Dateien auf der Festplatte.

    Jede Plandatei entspricht einem ``SeatingPlan``-Objekt. Beim Speichern
    wird automatisch ein Backup-Snapshot angelegt.
    """

    def __init__(self) -> None:
        """Initialisiert das Repository mit einem frischen Backup-Schreiber."""
        self._backup = PlanBackupWriter()

    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        """Gibt alle gültigen Pläne im Verzeichnis *plans_dir* zurück.

        Dateien, die nicht geladen werden können, werden still übersprungen.

        Args:
            plans_dir: Verzeichnis mit ``*.json``-Plandateien.

        Returns:
            Liste von (Pfad, Plan)-Tupeln, alphabetisch nach Dateiname sortiert.
        """
        plans_dir.mkdir(parents=True, exist_ok=True)
        plans: list[tuple[Path, SeatingPlan]] = []
        for path in sorted(plans_dir.glob("*.json")):
            try:
                plans.append((path, self.load_plan(path)))
            except Exception:
                continue
        return plans

    def load_plan(self, plan_path: Path) -> SeatingPlan:
        """Lädt und deserialisiert einen Plan aus *plan_path*.

        Args:
            plan_path: Pfad zur JSON-Plandatei.

        Returns:
            Deserialisierter ``SeatingPlan``.

        Raises:
            ValueError: Bei strukturellen Fehlern in der Datei.
            json.JSONDecodeError: Wenn die Datei kein gültiges JSON enthält.
        """
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        return deserialize_plan(payload)

    def save_plan(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Serialisiert *plan* und schreibt ihn atomar nach *plan_path*.

        Erstellt danach automatisch einen Backup-Snapshot.

        Args:
            plan: Zu speichernder Sitzplan.
            plan_path: Zieldatei.
        """
        payload = serialize_plan(plan)
        atomic_write_json(plan_path, payload)
        self._backup.write_backup(plan_path, payload, root_dir=self._backup_root_dir())

    def backup_plan_snapshot(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Erstellt einen Backup-Snapshot von *plan*, ohne die Hauptdatei zu ändern.

        Args:
            plan: Plan, der gesichert werden soll.
            plan_path: Referenz-Pfad der Plandatei (bestimmt den Backup-Ordner).
        """
        payload = serialize_plan(plan)
        self._backup.write_backup(plan_path, payload, root_dir=self._backup_root_dir())

    def _backup_root_dir(self) -> Path:
        """Liefert das Backup-Wurzelverzeichnis; in Tests überschreibbar."""
        return self._backup.backup_root_dir()

    def create_new_plan(
        self, plans_dir: Path, plan_name: str, overwrite: bool = False
    ) -> tuple[Path, SeatingPlan]:
        """Legt einen neuen leeren Sitzplan an.

        Args:
            plans_dir: Zielverzeichnis.
            plan_name: Anzeigename des Plans; leer ergibt ``"Neuer Sitzplan"``.
            overwrite: Überschreibt eine bestehende Datei, wenn True.

        Returns:
            Tupel aus (Pfad zur neuen Datei, erstellter Plan).

        Raises:
            FileExistsError: Wenn die Datei bereits existiert und *overwrite* False ist.
        """
        plans_dir.mkdir(parents=True, exist_ok=True)
        clean_name = plan_name.strip() or "Neuer Sitzplan"
        plan_path = plans_dir / f"{self._slugify(clean_name)}.json"
        if plan_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {plan_path.name}")
        plan = SeatingPlan(
            version=3,
            plan_id=uuid.uuid4().hex,
            name=clean_name,
            desks=[Desk(x=0, y=0, desk_type="teacher")],
        )
        self.save_plan(plan, plan_path)
        return plan_path, plan

    def rename_plan(
        self, source_path: Path, new_name: str, overwrite: bool = False
    ) -> tuple[Path, SeatingPlan]:
        """Benennt einen Plan um und verschiebt ggf. die Datei.

        Args:
            source_path: Aktuelle Plandatei.
            new_name: Neuer Anzeigename; leer behält den bisherigen Namen.
            overwrite: Überschreibt eine Zieldatei, wenn True.

        Returns:
            Tupel aus (neuem Pfad, umbenanntem Plan).

        Raises:
            FileExistsError: Wenn die Zieldatei existiert und *overwrite* False ist.
        """
        source_plan = self.load_plan(source_path)
        target_name = new_name.strip() or source_plan.name
        target_path = source_path.with_name(f"{self._slugify(target_name)}.json")
        source_plan.name = target_name

        if target_path != source_path and target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")

        if target_path == source_path:
            self.save_plan(source_plan, source_path)
            return source_path, source_plan

        self.save_plan(source_plan, target_path)
        source_path.unlink(missing_ok=True)
        return target_path, source_plan

    def delete_plan(self, plan_path: Path) -> None:
        """Löscht die Plandatei unwiderruflich.

        Args:
            plan_path: Zu löschende Datei.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
        """
        if not plan_path.exists():
            raise FileNotFoundError(f"Plandatei nicht gefunden: {plan_path.name}")
        plan_path.unlink()

    def duplicate_plan(
        self, source_path: Path, target_name: str, overwrite: bool = False
    ) -> tuple[Path, SeatingPlan]:
        """Dupliziert einen Plan unter einem neuen Namen.

        Der Klon erhält eine neue ``plan_id``; alle Inhalte werden übernommen.

        Args:
            source_path: Quelldatei.
            target_name: Anzeigename des Duplikats; leer übernimmt den Quellnamen.
            overwrite: Überschreibt eine bestehende Zieldatei, wenn True.

        Returns:
            Tupel aus (Pfad der neuen Datei, duplizierter Plan).

        Raises:
            FileExistsError: Wenn die Zieldatei existiert und *overwrite* False ist.
        """
        source_plan = self.load_plan(source_path)
        duplicated = SeatingPlan(
            version=source_plan.version,
            plan_id=uuid.uuid4().hex,
            name=target_name.strip() or source_plan.name,
            desks=deepcopy(source_plan.desks),
            color_meanings=dict(source_plan.color_meanings),
            documentation_dates=list(source_plan.documentation_dates),
            grade_columns=deepcopy(source_plan.grade_columns),
            written_weight_percent=int(source_plan.written_weight_percent),
            sonstige_weight_percent=int(source_plan.sonstige_weight_percent),
        )
        target_path = source_path.with_name(f"{self._slugify(duplicated.name)}.json")
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")
        self.save_plan(duplicated, target_path)
        return target_path, duplicated

    def _slugify(self, text: str) -> str:
        """Wandelt *text* in einen dateinamensicheren Kleinbuchstaben-Slug um.

        Args:
            text: Beliebiger Anzeigename.

        Returns:
            Slug aus Kleinbuchstaben, Ziffern und Bindestrichen; mindestens ``"sitzplan"``.
        """
        clean = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
        clean = "-".join(chunk for chunk in clean.split("-") if chunk)
        return clean or "sitzplan"
