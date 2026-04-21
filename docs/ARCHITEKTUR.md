# Architektur (kartograph)

Dieses Dokument beschreibt den aktuellen Ist-Zustand.

## Architekturueberblick
- Einstiegspunkt ist `kartograph.py`.
- Die Anwendung ist in Schichten unter `app/` organisiert:
  - `app/core`: Domainmodell und Use-Cases.
  - `app/infrastructure`: Dateisystem-/Persistenzzugriffe.
  - `app/adapters/gui`: GUI-Adapter und Fensterlogik.
- Sitzplaene werden als JSON-Dateien in `plans/` abgelegt.
- Symboldefinitionen werden aus `config/symbols.json` gelesen und validiert.
- PDF-Export wird ueber einen dedizierten Infrastructure-Exporter umgesetzt.

## Datenfluss
- GUI-Interaktionen werden in Use-Cases ueberfuehrt.
- Use-Cases lesen/schreiben ueber Repository-Schnittstellen.
- Persistenz erfolgt ueber JSON-Repository-Implementierungen.
- Symbolkonfiguration wird beim App-Start geladen und in der GUI als Katalog/Legende genutzt.
- Exportaktionen werden in der GUI angestossen und durch den Infrastructure-Exporter als PDF geschrieben.

## Build- und Laufzeitkontext
- Start lokal ueber `start-kartograph.bat` oder `python kartograph.py`.
- Abhaengigkeiten sind in `requirements.txt` definiert.
