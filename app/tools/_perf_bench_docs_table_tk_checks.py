"""Tk-Mechanismus-Checks für den Doku-Tabellen-Benchmark (siehe ``perf_bench_docs_table.py``).

Ausgelagert aus dem Hauptskript, damit dieses unter dem 300-Zeilen-Limit
bleibt. Prüft ausschließlich die generische ``ttk.Treeview``-API (keine
Kartograph-Domänenobjekte nötig) — das ist die Tk-seitige Voraussetzung
dafür, dass der Fast Path in ``_refresh_documentation_table`` (Werte per
``item()`` aktualisieren statt aller Zeilen neu einzufügen) zum selben
sichtbaren Ergebnis führt wie der alte Full-Rebuild-Pfad, und wie viele
Tcl-Aufrufe dabei tatsächlich eingespart werden.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def check_treeview_item_update_matches_reinsert() -> bool:
    """Regressionscheck für den Diff-Update-Mechanismus (Item 1, Kartograph-Fix).

    Bestätigt: Ein ``Treeview.item(iid, values=...)``-Update auf einer bereits
    vorhandenen Zeile liefert exakt denselben Endzustand wie ``delete`` +
    frisches ``insert`` mit denselben Werten.
    """
    root = tk.Tk()
    root.withdraw()
    try:
        tree_a = ttk.Treeview(root, columns=("a", "b"))
        tree_b = ttk.Treeview(root, columns=("a", "b"))

        rows = [(f"row{i}", f"text{i}", (f"a{i}", f"b{i}")) for i in range(20)]
        for iid, text, values in rows:
            tree_a.insert("", "end", iid=iid, text=text, values=values)
            tree_b.insert("", "end", iid=iid, text=text, values=values)

        updated_rows = [
            (f"row{i}", f"text{i}-neu", (f"a{i}-neu", f"b{i}-neu"))
            for i in range(0, 20, 3)
        ]

        # Weg A (neuer Fast Path): vorhandene Zeilen per item() aktualisieren.
        for iid, text, values in updated_rows:
            tree_a.item(iid, text=text, values=values)

        # Weg B (alter Full-Rebuild-Pfad): löschen und mit denselben Zielwerten neu einfügen.
        updated_by_iid = {iid: (text, values) for iid, text, values in updated_rows}
        for iid, _text, _values in rows:
            tree_b.delete(iid)
        for iid, text, values in rows:
            final_text, final_values = updated_by_iid.get(iid, (text, values))
            tree_b.insert("", "end", iid=iid, text=final_text, values=final_values)

        for iid, _text, _values in rows:
            a_state = (tree_a.item(iid, "text"), tuple(tree_a.item(iid, "values")))
            b_state = (tree_b.item(iid, "text"), tuple(tree_b.item(iid, "values")))
            if a_state != b_state:
                return False
        return True
    finally:
        root.destroy()


def count_tcl_calls_for_single_cell_edit(num_students: int) -> tuple[int, int]:
    """Zählt Tk-API-Aufrufe für Full-Rebuild vs. Fast-Path bei EINER geänderten Zeile.

    Simuliert den realistischsten Fall — ein einzelner Noten-/Symbol-Edit
    ändert genau eine Zeile.

    Args:
        num_students: Anzahl bereits vorhandener Zeilen in der Tabelle.

    Returns:
        Tupel (Tcl-Aufrufe alter Full-Rebuild-Pfad, Tcl-Aufrufe neuer Fast Path).
    """
    root = tk.Tk()
    root.withdraw()
    try:
        rows = [(f"row{i}", f"text{i}", (f"a{i}", f"b{i}")) for i in range(num_students)]

        tree_old = ttk.Treeview(root, columns=("a", "b"))
        for iid, text, values in rows:
            tree_old.insert("", "end", iid=iid, text=text, values=values)

        tree_new = ttk.Treeview(root, columns=("a", "b"))
        for iid, text, values in rows:
            tree_new.insert("", "end", iid=iid, text=text, values=values)

        # Ein einzelner Edit ändert genau eine Zeile.
        changed_iid = rows[num_students // 2][0]
        new_values = ("a-geaendert", "b-geaendert")

        old_calls = 0
        for iid, _text, _values in rows:
            tree_old.delete(iid)
            old_calls += 1
        for iid, text, values in rows:
            final_values = new_values if iid == changed_iid else values
            tree_old.insert("", "end", iid=iid, text=text, values=final_values)
            old_calls += 1

        new_calls = 0
        for iid, text, values in rows:
            final_values = new_values if iid == changed_iid else values
            if iid == changed_iid:
                tree_new.item(iid, text=text, values=final_values)
                new_calls += 1
            # unveränderte Zeilen: kein Tk-Aufruf (Cache-Vergleich schlägt vorher fehl)

        return old_calls, new_calls
    finally:
        root.destroy()
