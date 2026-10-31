Deutsch: [README.de.md](README.de.md)

# Score-Overlay

A small always-on-top window with the time and football scores:

- On Bundesliga matchdays all matches of the day, optionally also on Champions League nights
- VfB Stuttgart (Bundesliga, DFB-Pokal, Champions/Europa/Conference League)
- VfB Stuttgart women (Frauen-Bundesliga; women's DFB-Pokal only with a goal-api.com key)
- TSV 1860 München (Regionalliga Bayern, DFB-Pokal)

Matches of your teams appear 3 h before kickoff and stay until about 3 h after the final whistle.

- Below the clock, the next match of each team (VfB, VfB women, 1860) is shown while none of theirs is on screen.
- When a goal is scored in a match of your teams, the row flashes for ~10 s (green = your goal, red = conceded),
  optionally with a sound. The default is `C:\Windows\Media\tada.wav`; another WAV file can be set
  in `config.json` as `"sound_file"` (double the backslashes, e.g. `"D:\\Sounds\\goal.wav"`).
  The sound plays regardless of the Windows sound scheme.
- Only one overlay runs at a time; a second start exits right away.
- If a source reports no match minute (Bundesliga, women, 1860), it is estimated from the kickoff time
  and marked with `~` (e.g. `~67'`, `HT`, `~90+'`).
- If the last request to a source failed, its matches are shown in grey with `?` after the score.
- If a source still reports a match as not started 10 minutes after kickoff, it is shown in grey with `?` after
  the kickoff time (e.g. `18:00?`): there is no live data for this match.

## Installation

1. Install [Python 3.13](https://www.python.org/downloads/) (no other packages needed).
2. Download the ZIP of the latest version from the [releases page](https://codeberg.org/ElvonMF/score-overlay/releases)
   and extract it to a folder, e.g. `%LOCALAPPDATA%\score-overlay`.
3. Double-click `start.pyw`.

## Usage

- Left mouse button: move the window (the position is saved in `config.json`)
- Right mouse button: "Refresh", switches (saved), "Sprache / Language", "About Score-Overlay…", "Quit"
  - "Preview" – next match of each team below the clock
  - "All Bundesliga matches" – on matchdays also the matches without your teams (default: on)
  - "All Champions League matches" – on CL nights also the other matches (default: off)
  - "Sound on goal"
  - "Sprache / Language" – German or English. Without a choice the language follows the Windows display
    language (German for a German Windows, otherwise English). The choice is saved as `"language": "de"` or `"en"`
    in `config.json` and can also be entered there by hand.

Matches of VfB (men/women) and 1860 are always shown and always on top,
followed by Bundesliga and Champions League matches by kickoff time.

## Updates

The overlay checks for a new version one minute after start and then daily (or via
"About Score-Overlay…" → "Check for updates"). If there is one, the right-click menu shows
"Install update to vX.Y.Z": download from Codeberg, installation, restart. `config.json` and `overlay.log`
are kept; the previous version is moved to `.update-backup/`. If the overlay runs from a Git clone,
it only points out the update (`git pull`).

### Autostart

`Win + R` → `shell:startup` → put a shortcut to `start.pyw` into that folder.

## Data sources

| Source | Used for |
|---|---|
| [OpenLigaDB](https://www.openligadb.de) | Bundesliga, DFB-Pokal, Frauen-Bundesliga |
| ESPN (unofficial scoreboard API) | Champions League, Europa League, Conference League, VfB Champions League schedule |
| [TheSportsDB](https://www.thesportsdb.com) (free key "123") | TSV 1860 München |
| [goal-api.com](https://goal-api.com) (optional, own key) | Today's live scores: Bundesliga, DFB-Pokal, Frauen-Bundesliga, Regionalliga |

### Optional: goal-api.com for reliable live scores

OpenLigaDB is maintained by volunteers; live scores are sometimes missing there. With a free key from
[goal-api.com](https://goal-api.com) (1,000 requests/day), today's matches of Bundesliga, DFB-Pokal,
Frauen-Bundesliga, women's DFB-Pokal and Regionalliga (1860) come from there, with the real match minute.
In addition, the VfB women's schedule is loaded hourly so that cup matches also appear in the preview. Add to `config.json`:

```json
"goal_api_key": "YOUR_KEY"
```

Requests are only made when a competition plays today: every minute while a match is live, otherwise every 30 minutes.
If goal-api.com fails for more than 5 minutes (or the daily limit is reached), the other sources take over.
`config.json` is not part of the repository; when saving, the overlay only changes its own entries.

Known gaps: women's DFB-Pokal without a goal-api.com key, women's Champions League, Toto-Pokal. Live scores of 1860 may be delayed.
Women's DFB-Pokal: goal-api.com does not provide live scores for every match; such matches show as `HH:MM?` after kickoff.
Errors while fetching are logged to `overlay.log`.

## Note on data sources

The license below covers only the code of this program. The data shown belongs to the respective providers
(OpenLigaDB, ESPN, TheSportsDB, goal-api.com); their terms of use apply. The ESPN interface is
unofficial and not documented for third parties. Use at your own risk.

## Development

```
py -m pip install --user pytest
py -m pytest -q
```

Publishing a new version:

1. Increase `__version__` in `overlay/__init__.py`, commit.
2. Create and push the tag `vX.Y.Z`.
3. On Codeberg, create a release for that tag under "Releases" (only releases are offered as updates).

## License

Copyright (C) 2026 ElvonMF

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option)
any later version (GPL-3.0-or-later).
It is provided without any warranty. See [LICENSE](LICENSE) for details.
