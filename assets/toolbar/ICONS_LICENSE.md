# Toolbar-Icons: Quelle und Lizenz

Alle PNGs in diesem Ordner stammen aus **Tabler Icons** (https://tabler.io/icons,
https://github.com/tabler/tabler-icons), Variante "outline", 24x24px.

Lizenz: **MIT** (siehe Volltext unten). Kommerzielle Nutzung, Modifikation und
Weiterverbreitung sind ohne Namensnennungspflicht erlaubt; die Namensnennung
hier erfolgt freiwillig zur Nachvollziehbarkeit.

Die Original-SVGs wurden mit Kopie des Original-`color`-Werts (Schwarz) auf
24x24px gerendert und 1:1 als PNG mit Alphakanal exportiert. Das Einfaerben
auf die jeweilige Theme-Vordergrundfarbe passiert danach zur Laufzeit durch
`bw_gui.theming.icon_button()` (siehe `app/adapters/gui/toolbar_icon_styler.py`).

## Datei -> Tabler-Icon-Name

| Datei                          | Tabler-Icon           |
|---------------------------------|------------------------|
| tb_new_plan.png                 | layout-grid-add        |
| tb_open_plan.png                | folder-open            |
| tb_rename_plan.png              | pencil                 |
| tb_delete.png                   | trash                  |
| tb_duplicate_plan.png           | copy                   |
| tb_back_to_list.png             | arrow-left             |
| tb_add_symbol.png               | star                   |
| tb_tablegroup_settings.png      | table                  |
| tb_export_pdf.png               | file-type-pdf          |
| tb_teacher_desk.png             | crown                  |
| tb_toggle_docs.png              | notes                  |
| tb_symbol_filter.png            | filter                 |
| tb_zoom_out.png                 | zoom-out               |
| tb_zoom_in.png                  | zoom-in                |

## MIT-Lizenztext (Tabler Icons)

```
MIT License

Copyright (c) 2020-2026 Paweł Kuna

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
