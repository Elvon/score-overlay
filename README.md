# Score-Overlay

Kleines, immer im Vordergrund liegendes Fenster mit Uhrzeit und Fußball-Spielständen:

- An Bundesliga-Spieltagen alle Spiele des Tages, auf Wunsch auch an Champions-League-Abenden
- VfB Stuttgart (Bundesliga, DFB-Pokal, Champions/Europa/Conference League)
- VfB Stuttgart Frauen (Frauen-Bundesliga)
- TSV 1860 München (Regionalliga Bayern, DFB-Pokal)

Spiele deiner Teams erscheinen 3 h vor Anpfiff und bleiben bis ca. 3 h nach Abpfiff stehen.

- Unter der Uhr steht pro Team (VfB, VfB Frauen, 1860) das nächste Spiel, solange gerade keins angezeigt wird.
- Fällt in einem Spiel deiner Teams ein Tor, blinkt die Zeile ~10 s (grün = eigenes Tor, rot = Gegentor),
  optional mit Ton. Standard ist `C:\Windows\Media\tada.wav`; eine andere WAV-Datei lässt sich
  in `config.json` unter `"sound_file"` eintragen (Backslashes doppelt, z.B. `"D:\\Sounds\\tor.wav"`).
  Der Ton spielt unabhängig vom Windows-Soundschema.
- Es läuft immer nur ein Overlay; ein zweiter Start beendet sich sofort.
- Liefert eine Quelle keine Spielminute (Bundesliga, Frauen, 1860), wird sie aus der Anstoßzeit
  geschätzt und mit `~` markiert (z.B. `~67'`, `HZ`, `~90+'`).
- Schlägt der letzte Abruf einer Quelle fehl, werden ihre Spiele grau mit `?` hinter dem Stand angezeigt.

## Starten

Doppelklick auf `start.pyw` (benötigt Python 3.13, keine weiteren Pakete).

- Linke Maustaste: Fenster verschieben (Position wird in `config.json` gespeichert)
- Rechte Maustaste: „Aktualisieren“, Schalter (werden gespeichert), „Beenden“
  - „Vorschau“ – nächstes Spiel pro Team unter der Uhr
  - „Alle Bundesliga-Spiele“ – an Spieltagen auch die Spiele ohne deine Teams (Standard: an)
  - „Alle Champions-League-Spiele“ – an CL-Abenden auch die übrigen Spiele (Standard: aus)
  - „Ton bei Tor“

Spiele vom VfB (Männer/Frauen) und von 1860 werden immer angezeigt und stehen immer oben,
danach folgen Bundesliga- und Champions-League-Spiele nach Anstoßzeit.

### Autostart

`Win + R` → `shell:startup` → Verknüpfung zu `start.pyw` in den Ordner legen.

## Datenquellen

| Quelle | Wofür |
|---|---|
| [OpenLigaDB](https://www.openligadb.de) | Bundesliga, DFB-Pokal, Frauen-Bundesliga |
| ESPN (inoffizielle Scoreboard-API) | Champions League, Europa League, Conference League, VfB-Spielplan Champions League |
| [TheSportsDB](https://www.thesportsdb.com) (Free-Key „123“) | TSV 1860 München |
| [goal-api.com](https://goal-api.com) (optional, eigener Key) | Live-Stände des Tages: Bundesliga, DFB-Pokal, Frauen-Bundesliga, Regionalliga |

### Optional: goal-api.com für zuverlässige Live-Stände

OpenLigaDB wird von Freiwilligen gepflegt; Live-Stände fehlen dort manchmal. Mit einem kostenlosen Key von
[goal-api.com](https://goal-api.com) (1.000 Abfragen/Tag) kommen die heutigen Spiele von Bundesliga, DFB-Pokal,
Frauen-Bundesliga und Regionalliga (1860) mit echter Spielminute von dort. In `config.json` eintragen:

```json
"goal_api_key": "DEIN_KEY"
```

Abgefragt wird nur, wenn ein Wettbewerb heute spielt: jede Minute, solange ein Spiel läuft, sonst alle 30 Minuten.
Fällt goal-api.com länger als 5 Minuten aus (oder ist das Tageslimit erreicht), springen die anderen Quellen ein.
`config.json` ist nicht im Repository; das Overlay ändert beim Speichern nur seine eigenen Einträge.

Bekannte Lücken: DFB-Pokal/Champions League der Frauen, Toto-Pokal. Live-Stände von 1860 können verzögert sein.
Fehler beim Abruf werden in `overlay.log` protokolliert.

## Entwicklung

```
py -m pip install --user pytest
py -m pytest -q
```
