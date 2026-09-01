# Aufgaben-Template

Ein Template-Repo ist der Startcode **einer** Aufgabe. Classroom 50 kopiert es
beim Annehmen in ein Studi-Repo; alles, was drin liegt, landet bei jeder
lernenden Person.

Platzhalter siehe [Übersicht](README.md#platzhalter).

> **Referenz-Vorlage:** [`BZZ-Commons/python-template`](https://github.com/BZZ-Commons/python-template)
> — die Vorlage, aus der die Aufgaben dieses Setups abgeleitet werden. Diese
> Seite beschreibt ihren Aufbau schulunabhängig; wer eine eigene bauen will,
> braucht das Repo nicht, sondern nur die Tabelle unten.

## Aufbau

| Datei | | Zweck |
|---|---|---|
| `main.py` | Pflicht | Startcode, den die Lernenden bearbeiten |
| `main_test.py` | Pflicht | pytest-Fälle der Lehrperson |
| `.github/autograding/unittests.json` | Pflicht | Testfälle mit Punkten und Timeout |
| `.github/autograding/lint.json` | Pflicht | zu lintende Dateien und Lint-Punkte |
| `.github/autograding/pylintrc` | Pflicht | pylint-Konfiguration |
| `requirements.txt` | empfohlen | Pins für die lokale Arbeit; Zusatzpakete daraus installiert auch der Bewertungslauf |
| `.python-version` | empfohlen | muss zu `runtime.python` in `assignments.json` passen |
| `README.md` | empfohlen | Aufgabenstellung oder Link darauf |
| `.gitignore` | empfohlen | `.venv/`, `__pycache__/`, IDE-Ordner |
| `run_pylint.py` | optional | lässt die Lernenden pylint lokal so laufen wie die Bewertung |

Nicht ins Template gehören:

| Datei | Warum |
|---|---|
| `.classroom50.yaml` | legt Classroom 50 beim Annehmen selbst an |
| `.github/workflows/autograde-runner.yaml` | dito — eine eigene Kopie bringt den Lauf durcheinander |
| `.github/workflows/classroom.yml` | GitHub-Classroom-Altlast, siehe [Migration](migration.md#templates-aus-der-alten-zeit-aufräumen) |
| Musterlösung | das Studi-Repo ist eine vollständige Kopie |

Das Repo muss in den Einstellungen als **Template repository** markiert sein,
sonst lehnt `gh teacher assignment add` es ab.

## Startcode und Tests

Der Startcode wird mitgelintet und entscheidet damit über die Startpunktzahl.
Modul- und Funktions-Docstrings gehören hinein, Zeilenlänge und Namen müssen zur
`pylintrc` passen. Warum ein Stub trotzdem bei 0 Lint-Punkten starten kann und
was dagegen hilft: [Bewertung → Startcode lint-sauber halten](bewertung.md#startcode-lint-sauber-halten).

Ein Startcode-Stub markiert die Stelle, an der gearbeitet wird — mit einem
`TODO`, das die `pylintrc` nicht als Meldung zählt, oder mit einem plausiblen
Rückgabewert statt `pass`.

Die Testdatei liegt im Studi-Repo und ist dort **editierbar**. Wer das nicht
will, zieht Tests und Konfiguration in ein Bundle im Config-Repo:
[Bewertung → Bundle oder Studi-Repo?](bewertung.md#bundle-oder-studi-repo).

## Bewertungs-Konfiguration

Die drei Dateien unter `.github/autograding/` sind in
[Bewertung](bewertung.md#die-drei-konfigurationsdateien) vollständig
beschrieben. Eine kopierfertige Vorlage liegt in
[`examples/bundle/`](../examples/bundle).

Zwei Fallen beim Ableiten einer neuen Aufgabe:

- `function` in `unittests.json` muss auf eine **existierende** Testfunktion
  zeigen. Ein Tippfehler gibt still null Punkte, keinen Fehler.
- `max` in `lint.json` ist das **Punktebudget** des Lintings, keine Dateizahl.
  Steht dort mehr, als alle Unittests zusammen geben, entscheidet der Stil die
  Note.

## Lokal prüfen

Das sollte in jedem Template funktionieren, bevor es ausgerollt wird:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pytest                           # laufen die Tests gegen die Musterlösung?
pylint --rcfile .github/autograding/pylintrc main.py
```

Näher an der echten Bewertung ist ein Lauf der Engine gegen das Template,
inklusive Punkteverteilung und Feedback-Tabelle:
[Bewertung → Lokal ausprobieren](bewertung.md#lokal-ausprobieren).

### Der Lint-Helfer

Ein kleines `run_pylint.py` im Template erspart den Lernenden die Optionen:

```bash
python run_pylint.py
```

Es liest `.github/autograding/lint.json`, nimmt die dort genannten Dateien und
lintet sie mit `.github/autograding/pylintrc`. Es rechnet die Note **nicht** in
Punkte um — das macht erst pygrader50 mit `Note / 10 * max`.

> Wer einen solchen Helfer mitliefert, hält ihn an der Engine
> (`src/pygrader50/pylint_runner.py`) ausgerichtet, sonst urteilt er anders als
> die Bewertung:
>
> - Ist `files` gesetzt, lintet die Engine **genau** diese Dateien; `ignore`
>   wirkt nur auf die automatische Auswahl.
> - Ist `files` leer, nimmt die Engine `*.py` im **Wurzelverzeichnis**, nicht
>   rekursiv, und wendet darauf `ignore` an.
> - `max` begrenzt **nichts** an der Dateiauswahl.
>
> Die Fassung in `BZZ-Commons/python-template` weicht in allen drei Punkten ab.
> Solange `files` gesetzt ist und wenige Dateien enthält, fällt das nicht auf.

## Neue Aufgabe ableiten

1. Repo aus dem Template erzeugen (*Use this template*), in `<TEMPLATE-ORG>`.
2. `main.py`, `main_test.py` und `README.md` durch die Aufgabe ersetzen.
3. `unittests.json` auf die echten Testfunktionen und Punkte setzen.
4. `lint.json`: `files` auf die zu lintenden Dateien, `max` auf die Lint-Punkte.
5. Zusätzliche Pakete in `requirements.txt` ergänzen — **nicht** die, welche die
   Lernenden selbst eintragen sollen.
6. Als *Template repository* markieren.
7. Aufgabe registrieren: [Einrichtung → Aufgaben registrieren](einrichtung.md#3-aufgaben-registrieren).

`requirements.txt` wird im Bewertungslauf **gefiltert** installiert: alles bis
auf die Pakete der Engine (`pytest`, `pytest-timeout`, `pylint`, `pygrader50`),
die pygrader50 selbst gepinnt mitbringt. Eine Aufgabe, die `httpx` oder `flask`
braucht, trägt das Paket hier ein und bekommt es damit auch auf GitHub. Die Pins
für pytest und pylint gehören trotzdem in die Datei — für die lokale Arbeit —
und sollten zur Engine passen, sonst lintet es auf GitHub strenger als zu Hause.

## Pflege

Eine Änderung am Template erreicht nur **neu** angenommene Repos. Bestehende
Studi-Repos tragen ihre Kopie seit dem Annehmen weiter, auch die Punkte:
[Betrieb → Template-Änderungen erreichen bestehende Repos nicht](betrieb.md#template-änderungen-erreichen-bestehende-repos-nicht).

Die Werkzeug-Pins aller Templates einer Klasse lassen sich in einem Zug
hochziehen:

```bash
scripts/sync-template-pins.py <ORG> <CLASSROOM>            # Trockenlauf
scripts/sync-template-pins.py <ORG> <CLASSROOM> --apply    # schreiben
```

Die Zielliste kommt aus dem `template`-Block von `assignments.json`, nie aus dem
Repo-Listing von `<TEMPLATE-ORG>` — dort liegen oft auch Templates anderer
Module. Beide Skripte im Detail: [CLI-Referenz](cli.md).
