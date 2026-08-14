# pygrader50

Autograder-Engine für [Classroom 50](https://github.com/foundation50/classroom50) —
bewertet Python-Abgaben mit **pytest** und **pylint**, schreibt das
`classroom50/result/v1`-Payload und überträgt die Punkte nach **Moodle**.

Nachfolger von [BZZ-Commons/pygrader](https://github.com/BZZ-Commons/pygrader).
Dort steckte die Bewertung noch in einem GitHub-Classroom-Workflow; hier ist sie
ein installierbares Paket mit zwei Einstiegspunkten.

- **[SETUP.md](SETUP.md)** — Einrichtung von Grund auf, Migration, Fehlersuche
- **[CLI.md](CLI.md)** — alle Kommandos, Optionen und Umgebungsvariablen

## Ein Klassenzimmer anschliessen

Die Engine ist klassenzimmer-neutral — sie liest Klasse, Aufgabe und Person aus
der Umgebung, die `runner.py` setzt. Für `m320-ix25` gilt derselbe Ablauf wie
für jede andere Klasse:

```bash
gh extension install foundation50/gh-teacher
gh auth refresh -h github.com -s admin:org,read:org,repo,workflow

gh teacher autograder set-default m320-ix25 m320-ix25 --from bootstrap/autograder.py
scripts/remove-legacy-classroom-yml.sh m320-ix25 m320-ix25 --apply
cp classroom50/moodle-sync.yaml <config-repo>/.github/workflows/
```

Vier Schritte, dazwischen je eine Prüfung — ausführlich in
[SETUP.md](SETUP.md). Zwei Dinge sind pro Klasse zu entscheiden: welchen Tag
`bootstrap/autograder.py` pinnt, und ob die Aufgaben-Konfiguration im Studi-Repo
bleibt oder ins Config-Repo wandert.

Voraussetzung ist ein eingerichtetes Classroom 50 (`gh teacher classroom add`).
Python-Module beliebig — die Engine kennt nur pytest und pylint, nicht das Modul.

## Die zwei Einstiegspunkte

```
python -m pygrader50           bewertet eine Abgabe   (läuft im Studi-Repo)
python -m pygrader50.moodle    überträgt die Punkte   (läuft im classroom50-Repo)
```

Die Trennung ist Absicht: der Moodle-Token erlaubt es, **beliebige Noten für
beliebige Personen** zu setzen. Er gehört deshalb nicht in ein Repository, in das
Studierende pushen können — dort liest ihn ein selbst hinzugefügter Workflow in
drei Zeilen aus. Bewertet wird im Studi-Repo, übertragen wird zentral.

## Ablauf

```
Studi pusht
  └─ classroom50 autograde-runner (Studi-Repo)
       └─ runner.py  ←  Pages-Site des classroom50-Repos
            └─ <classroom>/autograder.py   = bootstrap/autograder.py von hier
                 └─ pip install pygrader50@<tag>
                      └─ python -m pygrader50
                           ├─ result.json      → Release, Commit-Status, scores.json
                           └─ release-body.md  → Release-Text + Job-Summary

collect-scores (nachts, classroom50)      → <classroom>/scores.json
  └─ moodle-sync (nachts oder auf Knopfdruck)
       └─ python -m pygrader50.moodle      → Moodle-Notenbuch
```

## Konfiguration einer Aufgabe

Drei Dateien im Format der bestehenden BZZ-Templates:

| Datei | Inhalt |
|---|---|
| `unittests.json` | `[{"name": "test_ggt", "function": "test_ggt", "timeout": 10, "points": 2}]` |
| `lint.json` | `{"files": ["main.py"], "ignore": [], "max": 5}` |
| `pylintrc` | pylint-Konfiguration |

Gesucht wird **pro Datei**, in dieser Reihenfolge:

1. `$RUNNER_TEMP/classroom50-runtime/<assignment>/` — das entpackte
   classroom50-Bundle aus `<classroom>/autograders/<slug>/`. Von der Lehrperson
   kontrolliert, für Studierende nicht editierbar.
2. `.github/autograding/` im Studi-Repo — der bisherige Ort, bleibt als Fallback.
3. `$PYGRADER50_CONFIG_DIR` — nur für lokale Entwicklung.

Fehlt beides, wird eine 0/0-Abgabe aufgezeichnet und im Log gewarnt. Kein roter
Job: eine Aufgabe ohne hinterlegte Bewertung ist ein Konfigurationsstand, kein
Infrastrukturfehler.

Vorlage: [`examples/bundle/`](examples/bundle).

Classroom 50 bringt mit `tests.json` auch deklarative Tests mit. pygrader50
benutzt sie bewusst nicht: `runner.py` löst per-Assignment `tests.json` **vor**
dem Klassen-Default auf, eine Aufgabe mit deklarativen Tests bekommt also kein
Linting mehr. Und im deklarativen Pfad wäre entweder die proportionale
Lint-Note oder der grüne Commit-Status zu haben, nie beides. Beides pro Aufgabe
mischen geht nicht — beides pro Klasse schon.

## Bewertung

- **Unittests** — ein Eintrag pro Testfall, `passed` = volle Punktzahl erreicht.
  Jeder Fall läuft als eigener pytest-Aufruf mit eigenem Timeout, damit ein
  hängender Test die übrigen nicht mitreisst.
- **Linting** — ein Eintrag `Linting`, Punkte = `global_note / 10 * max`,
  `passed` = mehr als 0 Punkte. Eine Konventions-Meldung kostet also Punkte,
  färbt den Commit-Status aber nicht rot.
- `result.json` verlangt **ganze Zahlen**, es wird gerundet. Der exakte Wert
  steht im Feedback-Text.
- Erwartete und tatsächliche Werte im Feedback stammen aus dem
  `pytest_assertrepr_compare`-Hook, der vor dem Lauf ins Checkout kopiert wird.

Beispiel eines erzeugten `release-body.md`:

```markdown
### classroom50 autograde: 0/7

## Unittests
| name | feedback | expected | actual | points | max |
| --- | --- | --- | --- | --- | --- |
| test_ggt | Assertion Error | 8 | None | 0 | 2 |

**0.00/2.00 Points (0.00%)**
```

## Was pygrader50 bewusst nicht tut

- **Keine Zusatzfelder in `result.json`.** CLI und Dashboard von Classroom 50
  parsen strikt; alles Menschenlesbare gehört in `release-body.md`.
- **Kein `$GITHUB_OUTPUT`.** Status und Zusammenfassung leitet der Runner selbst
  aus `result.json` ab — ein Kanal weniger, der auseinanderlaufen kann.
- **Kein `pip install -r requirements.txt`** aus dem Studi-Repo. pygrader50 bringt
  eigene Abhängigkeiten mit, exakt gepinnt in [`pyproject.toml`](pyproject.toml).
  Das hält die Bewertung reproduzierbar: eine neue pylint-Version verschiebt die
  Lint-Punkte erst, wenn hier jemand den Pin hochzieht und einen neuen Tag setzt.
  Transitive Versionen (astroid hinter pylint) bewegen sich weiterhin innerhalb
  ihrer eigenen Schranken — der verbleibende Spielraum, deutlich kleiner als ein
  pylint-Minor.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest -q                        # 44 Tests
.venv/bin/python -m pylint src/pygrader50 bootstrap   # 10.00/10
```

Die End-to-End-Tests bauen ein Wegwerf-Studi-Repo und lassen den echten
Entrypoint als Subprozess darüber laufen. `tests/test_result.py` prüft gegen eine
Kopie der Validierung aus `runner.py`: schlägt sie fehl, würde das Gradebook das
Payload verwerfen.

## Lizenz

MIT
