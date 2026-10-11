# Score-Overlay

Kleines, immer im Vordergrund liegendes Fenster mit Uhrzeit und Fußball-Spielständen:

- An Bundesliga-Spieltagen alle Spiele des Tages
- VfB Stuttgart (Bundesliga, DFB-Pokal, Champions/Europa/Conference League)
- VfB Stuttgart Frauen (Frauen-Bundesliga)
- TSV 1860 München (Regionalliga Bayern, DFB-Pokal)

Spiele deiner Teams erscheinen 3 h vor Anpfiff und bleiben bis ca. 3 h nach Abpfiff stehen.

## Starten

Doppelklick auf `start.pyw` (benötigt Python 3.13, keine weiteren Pakete).

- Linke Maustaste: Fenster verschieben (Position wird in `config.json` gespeichert)
- Rechte Maustaste: „Aktualisieren“ / „Beenden“

### Autostart

`Win + R` → `shell:startup` → Verknüpfung zu `start.pyw` in den Ordner legen.

## Datenquellen

| Quelle | Wofür |
|---|---|
| [OpenLigaDB](https://www.openligadb.de) | Bundesliga, DFB-Pokal, Frauen-Bundesliga |
| ESPN (inoffizielle Scoreboard-API) | Champions League, Europa League, Conference League |
| [TheSportsDB](https://www.thesportsdb.com) (Free-Key) | TSV 1860 München |

Bekannte Lücken: DFB-Pokal/Champions League der Frauen, Toto-Pokal. Live-Stände von 1860 können verzögert sein.
Fehler beim Abruf werden in `overlay.log` protokolliert.

## Entwicklung

```
py -m pip install --user pytest
py -m pytest -q
```
