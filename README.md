# pygrader50

Autograder-Engine für [Classroom 50](https://github.com/foundation50/classroom50) —
bewertet Python-Abgaben mit **pytest** und **pylint** und schreibt das
`classroom50/result/v1`-Payload, das der Runner erwartet.

Nachfolger von [BZZ-Commons/pygrader](https://github.com/BZZ-Commons/pygrader)
(GitHub Classroom). Alles, was ohne GitHub Classroom noch gebraucht wird, lebt hier.

## Wie es läuft

```
Studi push
  └─ classroom50 autograde-runner (Studi-Repo)
       └─ runner.py  ←  von der Pages-Site der Lehrperson
            └─ <classroom>/autograder.py   = bootstrap/autograder.py aus diesem Repo
                 └─ pip install pygrader50@<tag>
                      └─ python -m pygrader50
                           ├─ result.json        → Release, Commit-Status, scores.json
                           └─ release-body.md    → Release-Text + Job-Summary
```

Der Übertrag nach Moodle passiert **nicht** hier, sondern nachts zentral aus dem
`classroom50`-Repo — der Moodle-Token gehört nicht in ein Repo, in das Studierende
pushen können.

## Konfiguration

Drei Dateien steuern die Bewertung, im Format der bestehenden BZZ-Templates:

| Datei | Inhalt |
|---|---|
| `unittests.json` | `[{"name": …, "function": …, "timeout": 10, "points": 2}]` |
| `lint.json` | `{"files": ["main.py"], "ignore": [], "max": 5}` |
| `pylintrc` | pylint-Konfiguration |

Gesucht wird **pro Datei**, in dieser Reihenfolge:

1. `$RUNNER_TEMP/classroom50-runtime/<assignment>/` — das entpackte classroom50-Bundle
   (`<classroom>/autograders/<slug>/` im Config-Repo). Lehrpersonen-kontrolliert,
   für Studierende nicht editierbar.
2. `.github/autograding/` im Studi-Repo — der bisherige Ort, bleibt als Fallback.
3. `$PYGRADER50_CONFIG_DIR` — nur für lokale Entwicklung.

Fehlt beides, wird eine 0/0-Abgabe aufgezeichnet und im Log gewarnt — kein roter Job.

Beispiel-Bundle: [`examples/bundle/`](examples/bundle).

## Bewertung

- **Unittests**: ein `tests[]`-Eintrag pro Fall, `passed` = volle Punktzahl erreicht.
- **Linting**: ein Eintrag `Linting`, Punkte = `global_note / 10 * max`,
  `passed` = mehr als 0 Punkte. Eine Konventions-Meldung kostet also Punkte,
  färbt den Commit-Status aber nicht rot.
- `result.json` verlangt ganzzahlige Punkte → gerundet. Der exakte Wert steht im
  Feedback-Text von `release-body.md`.

## Installation in einem Klassenzimmer

```bash
gh teacher autograder set-default <org> <classroom> --from bootstrap/autograder.py
```

`bootstrap/autograder.py` pinnt die Engine-Version (`VERSION`). Update eines
Klassenzimmers = Tag hier hochziehen, eine Zeile im Bootstrap ändern,
publish-pages läuft automatisch.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest -q       # Unit- und End-to-End-Tests
.venv/bin/python -m pylint src/pygrader50 bootstrap
```

Die End-to-End-Tests bauen ein Wegwerf-Studi-Repo und lassen den echten
Entrypoint darüber laufen. `tests/test_result.py` spiegelt die Validierung aus
`runner.py`: schlägt sie fehl, würde das Gradebook das Payload verwerfen.

## Kontrakt mit dem Runner

- Arbeitsverzeichnis ist das Studi-Checkout.
- Ausgabe: `./result.json` (Pflicht), `./release-body.md` (optional).
- Exit **0** für jedes Bewertungs-Ergebnis, auch für eine durchgefallene Abgabe.
- Exit **≠ 0** nur bei Infrastruktur-Fehlern — die Abgabe wird dann als `error`
  aufgezeichnet.
- Keine Zusatzfelder in `result.json`: CLI und Dashboard parsen strikt.
