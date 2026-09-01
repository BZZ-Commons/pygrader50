# Konzept

Wie eine Abgabe von einem `git push` zu einer Note in Moodle wird, und welches
Stück welchen Teil verantwortet.

## Die beteiligten Repositories

| Repository | Rolle | Sichtbarkeit |
|---|---|---|
| `<ORG>/classroom50` | Config-Repo: `assignments.json`, `roster.csv`, `scores.json`, Autograder, Workflows, Pages-Site | privat |
| `<ORG>/<CLASSROOM>-<SLUG>-<LOGIN>` | Studi-Repo, eines pro Person und Aufgabe | privat |
| Template-Repo | Startcode und Tests einer Aufgabe, siehe [Aufgaben-Template](template.md) | frei wählbar |
| `BZZ-Commons/pygrader50` | dieses Repo: Bewertungs-Engine und Moodle-Übertrag | öffentlich |
| [`foundation50/classroom50`](https://github.com/foundation50/classroom50) | Upstream-Projekt, dessen Runner uns aufruft | öffentlich |

## Die Kette

```
Lernende:r pusht
  └─ autograde-runner.yaml            (im Studi-Repo, ruft den zentralen Workflow)
       └─ runner.py                   (von der Pages-Site des Config-Repos)
            └─ <CLASSROOM>/autograder.py   (Klassen-Default)
                 └─ pip install pygrader50@<TAG>
                      └─ python -m pygrader50
                           ├─ result.json      → Release, Commit-Status
                           └─ release-body.md  → Release-Text, Job-Summary, Feedback-PR

collect-scores (nachts, im Config-Repo)   → <CLASSROOM>/scores.json
  └─ moodle-sync (nachts)
       └─ python -m pygrader50.moodle       → Moodle-Notenbuch
```

Im Einzelnen:

1. Ein Push im Studi-Repo startet `.github/workflows/autograde-runner.yaml`.
   Die Datei wird beim Anlegen des Repos eingesetzt und ruft nur den
   **zentralen** Reusable Workflow des Config-Repos auf. Enthält die
   Commit-Message `NOACTION` oder `CLASSROOM 50`, wird der Lauf übersprungen.
2. Der `setup`-Job liest `.classroom50.yaml` aus dem Studi-Repo und den
   passenden Eintrag aus `assignments.json` von der Pages-Site.
3. Der `grade`-Job holt `runner.py` von der Pages-Site und startet es.
4. `runner.py` lädt `autograders/<SLUG>.tar.gz`, entpackt es nach
   `$RUNNER_TEMP/classroom50-runtime/<SLUG>/` und sucht dann in dieser
   Reihenfolge: per-Assignment `autograder.py` → per-Assignment `tests.json` →
   Klassen-Default `<CLASSROOM>/autograder.py` → sonst eine leere `0/0`-Abgabe.
5. Der Klassen-Default ist [`bootstrap/autograder.py`](../bootstrap/autograder.py)
   aus diesem Repo. Er installiert pygrader50 in gepinnter Version und startet
   `python -m pygrader50` im Studi-Checkout. pygrader50 installiert daraufhin die
   Zusatzpakete aus `requirements.txt` — gefiltert, siehe unten — und bewertet.
6. `runner.py` liest danach `result.json`, überschreibt `owner`,
   `assignment_type`, `datetime`, `graded_at` und `submitted_by`, validiert das
   Payload und publiziert Release und Commit-Status.
7. Nachts sammelt `collect-scores` alle Releases in `<CLASSROOM>/scores.json`.
8. `moodle-sync` überträgt daraus nach Moodle.

## Zwei Kopplungen an Interna des Runners

Beide sind aus dem Quelltext von `runner.py` abgeleitet und bei einem
Upstream-Update zu prüfen:

- **Der Bundle-Pfad** `$RUNNER_TEMP/classroom50-runtime/<SLUG>/`, in
  `src/pygrader50/config.py` als `BUNDLE_SUBDIR`. Nicht dokumentiert. Die
  Testsuite pinnt die Zeichenkette, damit eine Änderung hier auffällt und nicht
  erst in der Produktion.
- **`result.validate`** ist eine Kopie von `runner.py::validate_result`. Weicht
  sie ab, verwirft das Gradebook die Payloads stillschweigend.

## Wo die Konfiguration einer Aufgabe liegt

Gesucht wird **pro Datei**, in dieser Reihenfolge — der erste Treffer gewinnt:

1. `$RUNNER_TEMP/classroom50-runtime/<SLUG>/` — das entpackte Bundle aus
   `<CLASSROOM>/autograders/<SLUG>/`. Von der Lehrperson kontrolliert, für
   Lernende nicht editierbar.
2. `.github/autograding/` im Studi-Repo — der Ort aus der
   GitHub-Classroom-Zeit, bleibt als Fallback.
3. `$PYGRADER50_CONFIG_DIR` — nur für lokale Entwicklung und Tests.

Fehlt alles, wird eine `0/0`-Abgabe aufgezeichnet und im Log gewarnt. Der Job
wird dabei **nicht** rot: eine Aufgabe ohne hinterlegte Bewertung ist ein
Konfigurationsstand, kein Infrastrukturfehler.

Details: [Bewertung](bewertung.md).

## Die zwei Einstiegspunkte

```
python -m pygrader50           bewertet eine Abgabe   (läuft im Studi-Repo)
python -m pygrader50.moodle    überträgt die Punkte   (läuft im Config-Repo)
```

Die Trennung ist Absicht. Der Moodle-Token erlaubt es, **beliebige Noten für
beliebige Personen** zu setzen. Er gehört deshalb nicht in ein Repository, in
das Lernende pushen können — dort liest ihn ein selbst hinzugefügter Workflow in
drei Zeilen aus.

Technisch geht es unter Classroom 50 ohnehin nicht anders: der Reusable Workflow
`autograde-runner.yaml` deklariert in seinem `workflow_call:`-Block nur
`outputs:` und reicht **keine Secrets** an den Bewertungs-Job durch. Der Job ist
laut Upstream ausdrücklich **keine** Isolationsgrenze gegen selbst hinzugefügte
Workflows im Studi-Repo — alles Vertrauliche gehört ins Config-Repo.

## Warum nicht die deklarativen Tests von Classroom 50

Classroom 50 bringt mit `tests.json` einen deklarativen Weg mit. pygrader50
benutzt ihn bewusst nicht:

- `runner.py` löst eine aufgaben-eigene `tests.json` **vor** dem Klassen-Default
  auf. Eine Aufgabe mit deklarativen Tests bekommt also kein Linting mehr.
- Im deklarativen Pfad wäre entweder die proportionale Lint-Note **oder** der
  grüne Commit-Status zu haben, nie beides: `derive_status_and_summary` setzt
  `success` nur, wenn *alle* Zeilen `passed` sind, und im deklarativen Pfad
  vergibt der Interpreter das Flag selbst.

Pro Aufgabe lässt sich beides nicht mischen — pro Klasse schon. Wer Linting
überall zur Note zählen lassen will, lässt alle Aufgaben auf
`"autograder": "default"` und ohne `tests`-Block stehen.

## Was pygrader50 bewusst nicht tut

- **Keine Zusatzfelder in `result.json`.** CLI und Dashboard von Classroom 50
  parsen strikt; alles Menschenlesbare gehört in `release-body.md`.
- **Kein `$GITHUB_OUTPUT`.** Status und Zusammenfassung leitet der Runner selbst
  aus `result.json` ab — ein Kanal weniger, der auseinanderlaufen kann.
- **Kein *ungefiltertes* `pip install -r requirements.txt`** aus dem Studi-Repo.
  Die Datei wird benutzt — es ist dieselbe, die die Lernenden lokal
  installieren —, aber gefiltert: jede Zeile, die ein Paket der Engine nennt
  (`pytest`, `pytest-timeout`, `pylint`, `pygrader50`), fällt mit einer Warnung
  weg. Der Rest wird unter einer Constraints-Datei installiert, die genau diese
  Pakete auf die laufende Version festnagelt. Eine Aufgabe darf so `httpx` oder
  `flask` ergänzen, aber `pylint` nicht verschieben.

  Der Grund für die Filterung: `requirements.txt` pinnt pytest und pylint
  ebenfalls, und `pip` stuft die Werkzeuge, mit denen benotet wird, klaglos
  zurück — es druckt `ERROR:` und liefert trotzdem Exit 0. Die Pins in
  [`pyproject.toml`](../pyproject.toml) entschieden dann nichts mehr.
  Transitive Versionen (astroid hinter pylint) bewegen sich weiter innerhalb
  ihrer eigenen Schranken — der verbleibende Spielraum, klein gegenüber einem
  pylint-Minor, aber nicht null.

  Scheitert die Installation (Tippfehler im Pin, Index nicht erreichbar, ein
  Paket, das der Constraints-Datei widerspricht), warnt der Lauf und bewertet
  weiter. Das ist kein Infrastrukturfehler: die Abgabe bekommt eine Note und
  einen lesbaren `ModuleNotFoundError` statt gar keine Rückmeldung.

## Verantwortlichkeiten

| Was | Wo | Warum dort |
|---|---|---|
| Bewertungs-Engine, Moodle-Übertrag | `BZZ-Commons/pygrader50` | eine Quelle, versioniert, für alle Classrooms |
| Klassen-Default, Bundles, Moodle-Token | `<ORG>/classroom50` | von der Lehrperson kontrolliert, für Lernende nicht schreibbar |
| Startcode, Tests, Musterlösung | Template-Repo | gehört zur Aufgabe |
| Abgabe | Studi-Repo | gehört den Lernenden |
