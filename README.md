# pygrader50

Autograder-Engine für [Classroom 50](https://github.com/foundation50/classroom50) —
bewertet Python-Abgaben mit **pytest** und **pylint**, schreibt das
`classroom50/result/v1`-Payload und überträgt die Punkte nach **Moodle**.

Nachfolger von [BZZ-Commons/pygrader](https://github.com/BZZ-Commons/pygrader).
Dort steckte die Bewertung noch in einem GitHub-Classroom-Workflow; hier ist sie
ein installierbares Paket mit zwei Einstiegspunkten.

```
python -m pygrader50           bewertet eine Abgabe   (läuft im Studi-Repo)
python -m pygrader50.moodle    überträgt die Punkte   (läuft im Config-Repo)
```

## Dokumentation

Alles Weitere steht in **[docs/](docs/)** — schulunabhängig, mit Platzhaltern
statt konkreten Klassennamen.

| | |
|---|---|
| [Konzept](docs/konzept.md) | wie Classroom 50 die Engine aufruft, welche Repos beteiligt sind |
| [Bewertung](docs/bewertung.md) | `unittests.json`, `lint.json`, `pylintrc`, wie Punkte entstehen |
| [Einrichtung](docs/einrichtung.md) | einen Classroom von Grund auf anschliessen |
| [Betrieb](docs/betrieb.md) | Roster, Aufgaben, Nachbewerten, Betriebsfallen |
| [Moodle](docs/moodle.md) | Notenübertrag und Zuordnung der Personen |
| [Migration](docs/migration.md) | Umstieg von GitHub Classroom |
| [CLI-Referenz](docs/cli.md) | alle Kommandos, Optionen, Umgebungsvariablen |
| [Für Lernende](docs/lernende.md) | Aufgabe annehmen, bearbeiten, abgeben |
| [Fehlersuche](docs/troubleshooting.md) | Symptom → Ursache |

## Schnellstart

Voraussetzung ist ein eingerichtetes Classroom 50 (`gh teacher classroom add`).

```bash
gh extension install foundation50/gh-teacher
gh auth refresh -h github.com -s admin:org,read:org,repo,workflow

gh teacher autograder set-default <ORG> <CLASSROOM> --from bootstrap/autograder.py
cp classroom50/moodle-sync.yaml <config-repo>/.github/workflows/
```

Jeder Schritt einzeln, mit Prüfung dazwischen:
[Einrichtung](docs/einrichtung.md).

Python-Module beliebig — die Engine kennt nur pytest und pylint, nicht das
Modul, die Klasse oder die Schule.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m pylint src/pygrader50 bootstrap    # muss 10.00/10 bleiben
```

Die End-to-End-Tests bauen ein Wegwerf-Studi-Repo und lassen den echten
Entrypoint als Subprozess darüber laufen. `tests/test_result.py` prüft gegen
eine Kopie der Validierung aus `runner.py`: schlägt sie fehl, würde das
Gradebook das Payload verwerfen.

## Lizenz

MIT
