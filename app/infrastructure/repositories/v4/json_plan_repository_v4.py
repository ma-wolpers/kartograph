"""JSON-basiertes Repository für Sitzplandateien (Format v4).

Dieselbe Schnittstelle wie ``JsonSeatingPlanRepository`` (v3), arbeitet aber
ausschließlich mit dem v4-Domänenmodell und dem v4-Schema.
``last_modified`` wird beim Speichern automatisch aktualisiert.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from bw_libs.app_paths import atomic_write_json

from app.core.domain.models_v4 import (
    Classroom,
    PlanMeta,
    SeatingPlan,
    TeacherSeat,
)
from app.infrastructure.repositories.plan_backup import PlanBackupWriter
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class JsonSeatingPlanRepositoryV4:
    """Liest und schreibt Sitzpläne (v4) als JSON-Dateien auf der Festplatte.

    Beim Speichern wird ``plan.meta.last_modified`` auf den aktuellen UTC-Zeitstempel
    gesetzt und anschließend automatisch ein Backup-Snapshot angelegt.
    """

    ARCHIVE_DIRNAME = "ALT"

    def __init__(self) -> None:
        self._backup = PlanBackupWriter()

    def _archive_dir(self, plans_dir: Path) -> Path:
        """Liefert den Archiv-Unterordner von *plans_dir*.

        Einzige Stelle, die den Archivpfad aus ``plans_dir`` bildet — ``archive_plan``
        und ``restore_plan`` vergleichen ihre Pfadverträge ausschließlich gegen das
        Ergebnis dieser Methode, damit ``ARCHIVE_DIRNAME`` die einzige Quelle der
        Wahrheit für den Ordnernamen bleibt.

        Args:
            plans_dir: Normaler Plan-Ordner.

        Returns:
            ``plans_dir / ARCHIVE_DIRNAME``.
        """
        return plans_dir / self.ARCHIVE_DIRNAME

    # ------------------------------------------------------------------
    # Lesen
    # ------------------------------------------------------------------

    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        """Gibt alle gültigen v4-Pläne im Verzeichnis zurück.

        Dateien, die nicht geladen werden können (falsches Format, Fehler),
        werden still übersprungen.

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

    def list_archived_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        """Gibt alle archivierten v4-Pläne im ``ALT``-Unterordner von *plans_dir* zurück.

        Spiegelt ``list_plans()`` (gleiches Skip-Verhalten bei kaputten Dateien,
        gleiche alphabetische Sortierung nach Dateiname), liest aber aus dem
        Archiv-Unterordner. Anders als ``list_plans()`` legt diese Methode den
        Ordner nicht an — ein fehlendes Archiv bedeutet schlicht "noch nichts
        archiviert", kein Fehlerzustand.

        Args:
            plans_dir: Normaler Plan-Ordner (nicht der Archivordner selbst).

        Returns:
            Liste von (Pfad, Plan)-Tupeln aus dem Archiv, alphabetisch nach
            Dateiname sortiert; ``[]``, wenn kein Archiv-Unterordner existiert.
        """
        archive_dir = self._archive_dir(plans_dir)
        if not archive_dir.exists():
            return []
        plans: list[tuple[Path, SeatingPlan]] = []
        for path in sorted(archive_dir.glob("*.json")):
            try:
                plans.append((path, self.load_plan(path)))
            except Exception:
                continue
        return plans

    def load_plan(self, plan_path: Path) -> SeatingPlan:
        """Lädt und deserialisiert einen v4-Plan aus *plan_path*.

        Args:
            plan_path: Pfad zur JSON-Plandatei.

        Returns:
            Deserialisierter ``SeatingPlan`` (v4).

        Raises:
            ValueError: Bei strukturellen Fehlern.
            json.JSONDecodeError: Wenn die Datei kein gültiges JSON enthält.
        """
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        if payload.get("format_version") != 4:
            raise ValueError(
                f"{plan_path.name}: format_version muss 4 sein "
                f"(gefunden: {payload.get('format_version')!r})"
            )
        return deserialize_plan(payload)

    # ------------------------------------------------------------------
    # Schreiben
    # ------------------------------------------------------------------

    def save_plan(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Serialisiert *plan*, setzt ``last_modified`` und schreibt atomar.

        Args:
            plan: Zu speichernder Sitzplan.
            plan_path: Zieldatei.
        """
        plan.meta.last_modified = _now_iso()
        payload = serialize_plan(plan)
        atomic_write_json(plan_path, payload)
        self._backup.write_backup(plan_path, payload, root_dir=self._backup_root_dir())

    def backup_plan_snapshot(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Erstellt einen Backup-Snapshot, ohne die Hauptdatei zu ändern.

        Args:
            plan: Sitzplan, dessen aktueller Stand gesichert wird.
            plan_path: Pfad der zugehörigen Plandatei (bestimmt das Backup-Ziel).
        """
        payload = serialize_plan(plan)
        self._backup.write_backup(plan_path, payload, root_dir=self._backup_root_dir())

    def _backup_root_dir(self) -> Path:
        """Liefert das Backup-Wurzelverzeichnis; in Tests überschreibbar."""
        return self._backup.backup_root_dir()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_new_plan(
        self, plans_dir: Path, plan_name: str, overwrite: bool = False
    ) -> tuple[Path, SeatingPlan]:
        """Legt einen neuen leeren v4-Sitzplan an.

        Args:
            plans_dir: Zielverzeichnis.
            plan_name: Anzeigename; leer ergibt ``"Neuer Sitzplan"``.
            overwrite: Überschreibt eine bestehende Datei, wenn True.

        Returns:
            Tupel aus (Pfad, erstellter Plan).

        Raises:
            FileExistsError: Wenn die Datei bereits existiert und *overwrite* False ist.
        """
        plans_dir.mkdir(parents=True, exist_ok=True)
        clean_name = plan_name.strip() or "Neuer Sitzplan"
        plan_path = plans_dir / f"{self._slugify(clean_name)}.json"
        if plan_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {plan_path.name}")
        now = _now_iso()
        plan = SeatingPlan(
            format_version=4,
            plan_id=uuid.uuid4().hex,
            meta=PlanMeta(name=clean_name, created_at=now, last_modified=now),
            classroom=Classroom(teacher_seat=TeacherSeat(x=0, y=0)),
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
        plan = self.load_plan(source_path)
        target_name = new_name.strip() or plan.meta.name
        target_path = source_path.with_name(f"{self._slugify(target_name)}.json")
        plan.meta.name = target_name

        if target_path != source_path and target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")

        if target_path == source_path:
            self.save_plan(plan, source_path)
            return source_path, plan

        self.save_plan(plan, target_path)
        source_path.unlink(missing_ok=True)
        return target_path, plan

    def delete_plan(self, plan_path: Path) -> None:
        """Löscht die Plandatei unwiderruflich.

        Args:
            plan_path: Pfad der zu löschenden Plandatei.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
        """
        if not plan_path.exists():
            raise FileNotFoundError(f"Plandatei nicht gefunden: {plan_path.name}")
        plan_path.unlink()

    def archive_plan(self, plan_path: Path) -> Path:
        """Verschiebt *plan_path* in den ``ALT``-Archiv-Unterordner desselben Plan-Ordners.

        Reines Verschieben (``Path.rename``) — der Planinhalt (``plan_id``,
        ``last_modified``, alle Felder) bleibt dabei unverändert; es wird kein
        ``save_plan()`` aufgerufen.

        Args:
            plan_path: Pfad der zu archivierenden Plandatei; muss im normalen
                Plan-Ordner liegen (nicht bereits im Archiv).

        Returns:
            Neuer Pfad der Datei im Archiv-Unterordner.

        Raises:
            ValueError: Wenn *plan_path* bereits im Archiv-Unterordner liegt.
            FileNotFoundError: Wenn *plan_path* nicht existiert.
            FileExistsError: Wenn im Archiv bereits eine Datei mit demselben
                Namen liegt.
        """
        if plan_path.parent.name == self.ARCHIVE_DIRNAME:
            raise ValueError(f"Plan liegt bereits im Archiv: {plan_path.name}")
        if not plan_path.exists():
            raise FileNotFoundError(f"Plandatei nicht gefunden: {plan_path.name}")

        archive_dir = self._archive_dir(plan_path.parent)
        archive_dir.mkdir(parents=True, exist_ok=True)
        target_path = archive_dir / plan_path.name
        if target_path.exists():
            raise FileExistsError(f"Im Archiv liegt bereits eine Datei mit diesem Namen: {target_path.name}")

        plan_path.rename(target_path)
        return target_path

    def restore_plan(self, plan_path: Path) -> Path:
        """Verschiebt den archivierten Plan *plan_path* zurück in den normalen Plan-Ordner.

        Gegenstück zu ``archive_plan()``; ebenfalls ein reines ``Path.rename()``
        ohne Inhaltsänderung.

        Args:
            plan_path: Pfad der archivierten Plandatei; muss direkt im
                ``ALT``-Unterordner liegen.

        Returns:
            Neuer Pfad der Datei im übergeordneten Plan-Ordner.

        Raises:
            ValueError: Wenn *plan_path* nicht direkt im Archiv-Unterordner liegt.
            FileNotFoundError: Wenn *plan_path* nicht existiert.
            FileExistsError: Wenn im Plan-Ordner bereits eine Datei mit demselben
                Namen liegt.
        """
        plans_dir = plan_path.parent.parent
        if self._archive_dir(plans_dir) != plan_path.parent:
            raise ValueError(f"Plan liegt nicht im Archiv: {plan_path.name}")
        if not plan_path.exists():
            raise FileNotFoundError(f"Plandatei nicht gefunden: {plan_path.name}")

        target_path = plans_dir / plan_path.name
        if target_path.exists():
            raise FileExistsError(f"Es existiert bereits ein Plan mit diesem Namen: {target_path.name}")

        plan_path.rename(target_path)
        return target_path

    def duplicate_plan(
        self, source_path: Path, target_name: str, overwrite: bool = False
    ) -> tuple[Path, SeatingPlan]:
        """Dupliziert einen Plan unter einem neuen Namen mit neuer ``plan_id``.

        Args:
            source_path: Quelldatei.
            target_name: Anzeigename des Duplikats; leer übernimmt Quellnamen.
            overwrite: Überschreibt eine bestehende Zieldatei, wenn True.

        Returns:
            Tupel aus (Pfad der neuen Datei, duplizierter Plan).

        Raises:
            FileExistsError: Wenn die Zieldatei existiert und *overwrite* False ist.
        """
        source = self.load_plan(source_path)
        clone = deepcopy(source)
        clone.plan_id = uuid.uuid4().hex
        clone.meta.name = target_name.strip() or source.meta.name
        target_path = source_path.with_name(f"{self._slugify(clone.meta.name)}.json")
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")
        self.save_plan(clone, target_path)
        return target_path, clone

    def plan_name_taken(self, source_path: Path, name: str) -> bool:
        """Prüft, ob *name* bereits eine andere Plandatei neben *source_path* belegt.

        Reine Lesefunktion für Konflikt-Vorabprüfungen (z. B. vor ``duplicate_plan``/
        ``rename_plan``), löst selbst keine Mutation aus.

        Args:
            source_path: Plandatei, neben der der Zielname geprüft wird.
            name: Zu prüfender Anzeigename.

        Returns:
            True, wenn eine andere Datei mit dem aus *name* abgeleiteten
            Dateinamen bereits existiert.
        """
        target_path = source_path.with_name(f"{self._slugify(name)}.json")
        return target_path != source_path and target_path.exists()

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    def _slugify(self, text: str) -> str:
        clean = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
        clean = "-".join(chunk for chunk in clean.split("-") if chunk)
        return clean or "sitzplan"
