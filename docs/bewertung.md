# Bewertung

pygrader50 bewertet mit **pytest** für die Funktion und **pylint** für den Stil.
Beides zählt zur Note.

## Die drei Konfigurationsdateien

| Datei | Inhalt |
|---|---|
| `unittests.json` | welche Tests laufen, mit Timeout und Punkten |
| `lint.json` | welche Dateien gelintet werden und wie viele Punkte das gibt |
| `pylintrc` | pylint-Konfiguration |

Wo sie gesucht werden, steht unter [Konzept](konzept.md#wo-die-konfiguration-einer-aufgabe-liegt).
Eine vollständige Vorlage liegt in [`examples/bundle/`](../examples/bundle).

### `unittests.json`

Ein Eintrag pro Testfall. `function` ist der Name der Testfunktion in der
Testdatei, `points` sind ganze Zahlen.

```json
[
  { "name": "test_ggt", "function": "test_ggt", "timeout": 10, "points": 2 }
]
```

| Feld | Bedeutung | Vorgabe |
|---|---|---|
| `name` | Anzeigename in Feedback und `result.json` | Pflicht |
| `function` | Name der pytest-Funktion | Pflicht |
| `timeout` | Sekunden für diesen einen Fall | `10` |
| `points` | Punkte bei bestandenem Fall | `0` |

Ein Bruchwert bei `points` wird beim Einlesen gerundet — `result.json` verlangt
ganze Zahlen, und ein stillschweigend verschwindender Bruchteil wäre schlimmer
als eine sichtbare Rundung.

Jeder Fall läuft als **eigener** pytest-Aufruf mit eigenem Timeout, damit ein
hängender Test die übrigen nicht mitreisst.

### `lint.json`

```json
{ "files": ["main.py"], "ignore": [], "max": 5 }
```

| Feld | Bedeutung |
|---|---|
| `files` | Dateien, die gelintet werden. Leer oder fehlend: alle `*.py` im Wurzelverzeichnis |
| `ignore` | Muster, die von der automatischen Auswahl ausgenommen werden |
| `max` | **Punktebudget** für das Linting — keine Dateizahl |

`max` ist die häufigste Verwechslung. Es sind die Punkte, die perfektes Linting
einbringt. Steht dort `20`, während die Unittests zusammen `2` Punkte geben,
entscheidet der Stil die Note zehnfach gegenüber der Funktion.

### `pylintrc`

Gewöhnliche pylint-Konfiguration. Entscheidend für die Punkte ist die
`evaluation`-Formel: sie bestimmt, wie stark eine Meldung die Note drückt.

```ini
# pylint-Vorgabe
evaluation=10.0 - ((float(5 * error + warning + refactor + convention) / statement) * 10)
```

Bei kleinen Dateien ist die Formel empfindlich: wenige Statements im Nenner
lassen eine einzige Meldung stark durchschlagen. Wer den Faktor erhöht, macht
die Note auf Startcode-Grossen praktisch binär — perfekt oder null. Das ist eine
zulässige Entscheidung, aber eine bewusste.

## Wie Punkte entstehen

### Unittests

Ein Eintrag pro Testfall. `passed` heisst: volle Punktzahl erreicht.

### Linting

Ein einziger Eintrag `Linting`:

```
Punkte = pylint-Note / 10 * max
passed = Punkte > 0
```

Eine Konventionsmeldung kostet also **Punkte**, färbt den Commit-Status aber
nicht rot. Ohne diese Regel wäre praktisch jeder Commit rot, weil der
Commit-Status nur grün wird, wenn *alle* Zeilen `passed` sind.

Bei wenigen Statements und einem `E…`-Fehler wird die pylint-Note negativ und
auf 0 geklemmt. `Linting: 0` ist in dem Fall korrekt, kein Defekt.

### Rundung

`result.json` verlangt ganze Zahlen, es wird gerundet. Der exakte Wert steht im
Feedback-Text.

## Startcode lint-sauber halten

Der Startcode im Template sollte ohne pylint-Meldung durchlaufen — Modul- und
Funktions-Docstrings inklusive. Sonst startet jede Aufgabe bei null
Lint-Punkten, bevor eine lernende Person eine Zeile geschrieben hat.

Unvermeidlich ist das nur bei Stubs: eine Funktion mit `pass` und ungenutzten
Parametern erzeugt `W0613 unused-argument`, eine Zuweisung aus einer Funktion
ohne `return` erzeugt `E1111`. Beides verschwindet mit der Lösung. Wer es
vermeiden will, gibt dem Stub einen plausiblen Rückgabewert statt `pass`.

## Beispiel-Feedback

```markdown
### classroom50 autograde: 0/7

## Unittests
| name     | feedback        | expected | actual | points | max |
| -------- | --------------- | -------- | ------ | ------ | --- |
| test_ggt | Assertion Error | 8        | None   | 0      | 2   |

**0.00/2.00 Points (0.00%)**
```

Die Spalten *expected* und *actual* stammen aus dem pytest-Hook
`pytest_assertrepr_compare`, den pygrader50 vor dem Lauf als `conftest.py` ins
Checkout kopiert. Eine vorhandene `conftest.py` im Wurzelverzeichnis wird dabei
überschrieben — der Hook ist die Grundlage der Feedback-Tabelle und gehört nicht
zur Aufgabe.

## Ein Bundle anlegen

```
classroom50/
└── <CLASSROOM>/
    └── autograders/
        └── <SLUG>/
            ├── unittests.json
            ├── lint.json
            └── pylintrc
```

Nach dem Push bündelt der Workflow `publish-pages` den Ordner zu
`autograders/<SLUG>.tar.gz`; der Runner entpackt ihn und pygrader50 liest von
dort.

> **Kein `autograder.py` und keine `tests.json` in diesen Ordner legen.**
> Beides hat Vorrang vor dem Klassen-Default und schaltet damit für diese
> Aufgabe die Bewertung durch pygrader50 ab — insbesondere das Linting.

**Prüfen:** Punkte in der Bundle-`unittests.json` ändern, pushen, neu bewerten
lassen — die neue Maximalpunktzahl muss im Release stehen.

### Bundle oder Studi-Repo?

| | Bundle im Config-Repo | `.github/autograding/` im Studi-Repo |
|---|---|---|
| Für Lernende editierbar | nein | **ja** |
| Erreicht bestehende Repos | ja, ab dem nächsten Lauf | nein, nur neu angenommene |
| Pflegeaufwand | ein Ordner je Aufgabe im Config-Repo | liegt beim Startcode |

Der Manipulationsgewinn eines Bundles ist nur halb, solange die Testdatei selbst
im Studi-Repo liegt und dort editierbar bleibt. Wer wirklich manipulationssicher
bewerten will, muss auch sie ins Bundle ziehen.

## Lokal ausprobieren

```bash
cd /pfad/zum/studi-repo
CLASSROOM=<CLASSROOM> \
ASSIGNMENT=<SLUG> \
SUBMISSION_TAG=submit/2026-08-13T12-00-00Z-abc1234 \
OWNER=<LOGIN> \
python -m pygrader50
cat release-body.md
```

Ohne `RUNNER_TEMP` entfällt die Bundle-Suche, es zählt also `.github/autograding/`
im Checkout. Alle Variablen: [CLI-Referenz](cli.md).
