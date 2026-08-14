# Projekt-Kontext für Claude

Dieses Dokument ist der Übergabepunkt zwischen Sessions. Es beschreibt, warum es
dieses Repo gibt, was schon entschieden und gebaut ist, und was als Nächstes
ansteht. Benutzerdokumentation steht in [README.md](README.md),
[CLI.md](CLI.md) und [SETUP.md](SETUP.md) — hier steht das, was dort nicht
hingehört.

## Worum es geht

Die BZZ ist von **GitHub Classroom** auf **Classroom 50** umgestiegen.
`BZZ-Commons/pygrader` war der alte Autograder (GitHub-Classroom-Workflow +
Moodle-Upload). `pygrader50` ist der Nachfolger: alles, was ohne GitHub
Classroom noch gebraucht wird, gepflegt an einem Ort.

Beteiligte Repos, alle auf github.com:

| Repo | Rolle |
|---|---|
| `BZZ-Commons/pygrader50` | dieses Repo — Bewertungs-Engine + Moodle-Übertrag |
| `BZZ-Commons/pygrader` | Vorgänger, läuft noch, wird abgelöst |
| `m323-ix24/classroom50` | Config-Repo der Klasse (privat): `assignments.json`, `scores.json`, Workflows, Pages-Site |
| `m323-ix24/m323-ix24-<slug>-<login>` | Studi-Repos (privat) |
| `templates-python/<slug>` | Startcode-Templates |
| `foundation50/classroom50` | Upstream-Projekt, [Wiki](https://github.com/foundation50/classroom50/wiki) |

## Wie Classroom 50 unseren Code aufruft

Wichtig für jede Änderung an der Engine:

1. Studi pusht → Reusable Workflow `m323-ix24/classroom50/.github/workflows/autograde-runner.yaml`.
2. Der `setup`-Job liest `.classroom50.yaml` aus dem Studi-Repo und den Eintrag
   aus `assignments.json` von der Pages-Site.
3. Der `grade`-Job holt `runner.py` von der Pages-Site und startet es.
4. `runner.py` lädt **immer** `autograders/<slug>.tar.gz` und entpackt es nach
   `$RUNNER_TEMP/classroom50-runtime/<slug>/`, sucht dann in dieser Reihenfolge:
   per-Assignment `autograder.py` → per-Assignment `tests.json` → Klassen-Default
   `<classroom>/autograder.py` → vacuous pass (0/0).
5. Unser `bootstrap/autograder.py` ist dieser Klassen-Default. Er installiert
   `pygrader50` in gepinnter Version und startet `python -m pygrader50` im
   Studi-Checkout.
6. `runner.py` liest danach `result.json`, überschreibt `owner`,
   `assignment_type`, `datetime`, `graded_at`, `submitted_by`, validiert und
   publiziert Release + Commit-Status.
7. Nachts sammelt `collect-scores` alle Releases in `<classroom>/scores.json`.
8. `moodle-sync` (siehe `classroom50/moodle-sync.yaml`) überträgt daraus nach Moodle.

Zwei Kopplungen an Interna von `runner.py`, die bei Upstream-Updates zu prüfen sind:

- Der Bundle-Pfad `$RUNNER_TEMP/classroom50-runtime/<slug>/` in `config.py`
  (`BUNDLE_SUBDIR`). Nicht dokumentiert, aus dem Quelltext abgeleitet.
- `result.validate` ist eine Kopie von `runner.py::validate_result`. Weicht sie
  ab, verwirft das Gradebook unsere Payloads stillschweigend.

## Getroffene Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Moodle-Übertrag **zentral** aus dem classroom50-Repo, nicht aus dem Studi-Run | Der Token kann Noten für beliebige Personen setzen. In einem Studi-Repo liest ihn ein selbst hinzugefügter Workflow aus. Zusätzlich reicht `autograde-runner.yaml` gar keine Secrets an den Grade-Job durch (`workflow_call:` hat nur `outputs:`) |
| Übertrag **nachts** statt bei jedem Push | Vom Benutzer so gewählt. Direkt hätte gekostet: Token in jedem Studi-Repo, eine `moodle.yml` in jedem Repo, nachgebaute Skip-Logik des Runners, +33 % Actions-Minuten — und einen Nacht-Fallback bräuchte es trotzdem |
| Lint-Eintrag `passed = Punkte > 0` | Sonst wäre fast jeder Commit-Status rot; Konventionsmeldungen kosten Punkte, nicht den grünen Haken |
| Punkte mit `round()` auf ganze Zahlen | `result.json` verlangt `int`. Exakter Wert steht im Feedback-Text |
| Config-Suche: Bundle → Studi-Repo | Bundle ist manipulationssicher (`allowed_files` schützt `.github/` **nicht**, KEEP_PREFIXES lässt es stehen), Fallback erlaubt Rollout in Ruhe |
| Keine Zusatzfelder in `result.json` | Wiki: CLI und Dashboard parsen strikt |
| Kein `$GITHUB_OUTPUT` | `runner.py` leitet Status/Summary selbst aus `result.json` ab — ein Kanal weniger |
| Studi-`requirements.txt` wird nicht installiert | Reproduzierbarkeit; ausserdem sind die Template-Pins (`pytest==8.3.3`, `pylint==3.2.7`) auf Python 3.14 nicht lauffähig |

## Stand

Zwei Commits auf `main`, **noch nicht gepusht** (Repo auf GitHub ist leer):

- `998faa7` Bewertungs-Engine
- `7e031ca` Moodle-Übertrag + Dokumentation

Geprüft: 44 Tests grün, pylint 10.00/10 (`.venv/bin/python -m pytest -q`,
`.venv/bin/python -m pylint src/pygrader50 bootstrap`). Der Moodle-Übertrag
wurde als `--dry-run` gegen die echte `scores.json` aus `m323-ix24/classroom50`
getestet.

### Offen

1. Push nach `BZZ-Commons/pygrader50`, Tag `v2.0.0` setzen.
2. `gh teacher autograder set-default m323-ix24 m323-ix24 --from bootstrap/autograder.py`,
   danach Test-Push im Repo `m323-ix24/m323-ix24-m323-lu01-a02-imperativer-ggt-graphics80`
   — das Release muss `0/7` statt `0/0` zeigen.
3. `classroom50/moodle-sync.yaml` ins Config-Repo kopieren, Secrets/Variablen
   setzen, `dry_run` auslösen.
4. Aufgaben-Bundles für die 63 Assignments anlegen (Quelle: `templates-python`).
5. Alten Pfad abschalten: `classroom.yml` aus Templates und Studi-Repos,
   `MOODLE_TOKEN2` in der Studi-Organisation entfernen **und rotieren**.

## Zustand der Umgebung (Stand 13.08.2026)

- **Es benotet aktuell niemand.** `m323-ix24/autograder.py` fehlt im Config-Repo,
  also liefert Classroom 50 überall `0/0` (`scores.json`: `tests: []`).
  Gleichzeitig läuft in den Studi-Repos noch die alte `classroom.yml` und
  scheitert am Moodle-Aufruf. Beide Pfade laufen bei jedem Push parallel.
- Die Moodle-Seite antwortet mit
  `No matching assignment found. Contact your teacher.` für
  `assignmentname "m323-lu01-a02-imperativer-ggt"`, `username "graphics80"`.
  Das ist eine Konfigurationsfrage in Moodle (Aktivitätsname / Benutzername),
  nicht im Code — der Benutzer hat sie ausdrücklich zurückgestellt.
- Alle 63 Assignments stehen auf `"autograder": "default"` und `feedback_pr: true`,
  keines hat einen `tests`-Block. Der Klassen-Default greift also überall.
- `students.csv` enthält bisher 2 Logins (`graphics80`, `fage34`) — Testbetrieb.
- Ohne `runtime.python` wählt der Runner **Python 3.14**. Dort installieren sich
  pytest 9.x und pylint 4.x; die Lint-Punkte fallen strenger aus als mit 3.2.7.
- Deklarative Tests (`tests`-Block) und pygrader50 schliessen sich pro Assignment
  aus — `tests.json` hat Vorrang vor dem Klassen-Default.

## Arbeitsweise in diesem Repo

- Benutzerdokumentation auf **Deutsch**, Code, Kommentare und Commit-Messages auf
  **Englisch**.
- Python: einfache Anführungszeichen, Docstrings überall, pylint muss 10.00/10
  bleiben (CI erzwingt es).
- Änderungen an der Engine immer mit einem End-to-End-Test absichern; die
  bestehenden bauen ein Wegwerf-Studi-Repo und starten den echten Entrypoint als
  Subprozess.
- Commit-Autor ist `graphics80 <kevin.maurizi@bzz.ch>`.
- Vor einem Push oder einem Eingriff in `m323-ix24/classroom50` nachfragen — das
  Config-Repo betrifft laufende Klassen.
