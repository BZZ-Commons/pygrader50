# CLI-Referenz

Zwei Kommandos: eines bewertet, eines überträgt. Dazu drei Wartungsskripte.

Alle Kommandos sind classroom-neutral — es steckt nirgends ein Modul- oder
Classroom-Name im Code. Platzhalter siehe [Übersicht](README.md#platzhalter).

## `python -m pygrader50` — bewerten

Wird vom Classroom-50-Runner im Studi-Checkout aufgerufen. Keine Argumente —
alles kommt aus der Umgebung.

### Umgebung

Setzt der Runner (`run_entrypoint` in `runner.py`):

| Variable | Bedeutung | Pflicht |
|---|---|---|
| `CLASSROOM` | Kurzname des Classrooms | ja |
| `ASSIGNMENT` | Slug der Aufgabe | ja |
| `SUBMISSION_TAG` | `submit/<Zeitstempel>-<Kurz-SHA>` | ja |
| `OWNER` / `USERNAME` | GitHub-Login der besitzenden Person | – ¹ |
| `ASSIGNMENT_TYPE` | `individual` oder `group` | – ² |
| `COMMIT_URL`, `RELEASE_URL`, `REVIEW_URL` | Links fürs Payload | – ³ |
| `RUNNER_TEMP` | Wurzel für das entpackte Bundle | – ⁴ |
| `PYGRADER50_CONFIG_DIR` | zusätzlicher Config-Ort, nur lokal | nein |

¹ ersatzweise `GITHUB_ACTOR` — ² Vorgabe `individual` —
³ ersatzweise aus `GITHUB_SERVER_URL` / `GITHUB_REPOSITORY` / `GITHUB_SHA` —
⁴ ohne die Variable entfällt die Bundle-Suche

### Ausgabe

| Datei | Inhalt |
|---|---|
| `./result.json` | `classroom50/result/v1`, vom Runner ans Release gehängt |
| `./release-body.md` | Feedback-Tabellen, Release-Text und Job-Summary |

### Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | Bewertung abgeschlossen — **auch** wenn alle Tests scheitern |
| `1` | Infrastrukturfehler: Umgebung fehlt, Konfiguration kaputt, Absturz. Der Runner zeichnet die Abgabe als `error` auf |

Eine fehlende Bewertungs-Konfiguration ist **kein** Fehler: 0/0 mit Warnung im
Log, Exit 0.

### Lokal ausprobieren

```bash
cd /pfad/zum/studi-repo
CLASSROOM=<CLASSROOM> \
ASSIGNMENT=<SLUG> \
SUBMISSION_TAG=submit/2026-08-13T12-00-00Z-abc1234 \
OWNER=<LOGIN> \
python -m pygrader50
cat release-body.md
```

Ohne `RUNNER_TEMP` entfällt die Bundle-Suche, es zählt also
`.github/autograding/` im Checkout. Einen anderen Ort erzwingt
`PYGRADER50_CONFIG_DIR`.

## `python -m pygrader50.moodle` — übertragen

Liest `scores.json` aus dem Config-Repo und schickt die Punkte an Moodle. Je
Kombination aus Aufgabe und Person geht die **neueste** Abgabe raus.

```
python -m pygrader50.moodle (--classroom NAME... | --all-classrooms) [Optionen]
```

### Der Scope ist fail-closed

Welche Classrooms angefasst werden, **muss ausgesprochen werden**. Ein fehlendes
oder leeres Argument bricht ab, statt alles zu übertragen.

| Aufruf | Wirkung |
|---|---|
| `--classroom X` | genau X |
| `--classroom X --classroom Y` | X und Y |
| `--all-classrooms` | alle Ordner mit einer `scores.json` |
| *keins von beiden* | **Abbruch, Exit 2** — es wird nichts übertragen |
| beides zusammen | Abbruch, Exit 2 (Widerspruch) |
| `--classroom ""` | Abbruch, Exit 2 — leer zählt als nicht gesetzt |
| `--classroom TIPPFEHLER` | Abbruch, Exit 2 — ein unbekanntes Classroom ist ein Fehler, kein leerer Treffer |
| `--classroom X`, Ordner da, `scores.json` fehlt | Abbruch, **Exit 1** — richtig gerufen, Repo noch nicht so weit |

»Alle« bleibt möglich — der Nachtlauf braucht es. Es ist nur nicht mehr das, was
Schweigen bedeutet. Der Grund: in GitHub Actions kommt eine nicht ausgefüllte
Eingabe als leerer String an, ununterscheidbar von einer bewusst geleerten. Wer
den Input vergisst, bekäme sonst nicht »nichts passiert«, sondern »alles
passiert« — und der Übertrag schreibt in eine fremde Moodle-Instanz und setzt
dabei eine dort von Hand korrigierte Note zurück. Das nimmt kein zweiter Lauf
zurück.

Ein *vorhandenes* Classroom ohne zu übertragende Noten ist dagegen ein normaler
Lauf mit Exit 0.

`--assignment` und `--user` dürfen weiter leer bleiben und heissen dann »alle«.
Sie verengen **innerhalb** des gewählten Classrooms; ihr weitester Fall ist
durch die äussere Grenze schon gedeckt. Die Regel gilt nur für die äusserste
Scope-Dimension — die, die bestimmt, wessen Daten überhaupt angefasst werden.

Die erste Ausgabezeile nennt den aufgelösten Scope, und in Actions steht er
zusätzlich in der Job-Summary:

```
Scope: 2 Classroom(s) — m323-ix24, m450-ix25 | echter Übertrag
```

### Argumente und Optionen

| Option | Wirkung |
|---|---|
| `--classroom NAME` | Classroom-Ordner im Config-Repo; **wiederholbar** |
| `--all-classrooms` | alle Ordner mit einer `scores.json` |
| `--config-repo PFAD` | Wurzel des Config-Repos (Vorgabe: `.`) |
| `--assignment SLUG` | nur diese Aufgabe |
| `--user LOGIN` | nur diesen GitHub-Login ¹ |
| `--force` | auch Unverändertes erneut senden |
| `--dry-run` | nur anzeigen, nichts senden; funktioniert ohne Zugangsdaten |
| `--no-feedback` | ohne Feedback-Text (spart einen API-Aufruf pro Abgabe) |

Das Zustandsfile ist immer `<CLASSROOM>/moodle-state.json` — es gibt keine
Option dafür. Eine einzelne Datei direkt zu benennen geht bewusst nicht: sonst
gäbe es zwei Antworten auf die Frage, was ein Classroom ist, und nur eine davon
ginge durch die Scope-Prüfung.

¹ Muss im Moodle-Kurs eingeschrieben sein. Der eigene Lehrer-Account ist es
meist nicht — Moodle antwortet dann `No matching assignment found`, obwohl die
Aktivität existiert.

### Umgebung

| Variable | Bedeutung |
|---|---|
| `MOODLE_URL` | Basis-URL der Moodle-Instanz, z. B. `https://moodle.example.org` |
| `MOODLE_TOKEN` | Webservice-Token |
| `MOODLE_FUNCTION` | Vorgabe `mod_externalassignment_update_grade` |
| `GH_TOKEN` / `GITHUB_TOKEN` | optional, liest die Release-Bodies für den Feedback-Text |

Ohne `--dry-run` sind `MOODLE_URL` und `MOODLE_TOKEN` Pflicht. Zur Falle mit
einer leer gesetzten `MOODLE_FUNCTION` siehe [Moodle](moodle.md#zugangsdaten).

### Was an Moodle geht

| Feld | Quelle |
|---|---|
| `assignment_name` | Slug der Aufgabe aus `scores.json` |
| `user_name` | `owner` der Abgabe (GitHub-Login) |
| `points` / `max` | `score` / `max-score` der neuesten Abgabe |
| `externallink` | URL des Releases |
| `feedback` | Release-Body, davor ein Hinweis bei verspäteter Abgabe, dahinter der Abgabe-Link |

### Zustandsfile

```json
{
  "schema": "pygrader50/moodle-state/v1",
  "entries": {
    "<SLUG>/<LOGIN>": {
      "submission": "submit/2026-08-13T08-41-09Z-35bdcb2",
      "score": 5,
      "max-score": 7
    }
  }
}
```

Übersprungen wird nur, wenn Abgabe **und** Punktzahl identisch sind — eine
Nachbewertung derselben Abgabe geht also erneut raus. Nur erfolgreiche
Übertragungen werden vermerkt; gescheiterte versucht der nächste Lauf wieder.

### Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | alles übertragen oder übersprungen |
| `1` | mindestens eine Übertragung scheiterte, oder die Umgebung reicht nicht — fehlende Zugangsdaten, unlesbare `scores.json`, oder eine `scores.json`, die es noch nicht gibt (Collect Scores lief nie) |
| `2` | der Aufruf war unklar — Scope fehlt, widersprüchlich, leer oder unbekannt |

`2` heisst immer: **es wurde nichts gesendet.** Der Unterschied zu `1` ist der
zwischen »falsch gerufen« und »richtig gerufen, aber es ging nicht«. Ein Repo
ohne `scores.json` fällt bewusst in `1`: der Aufruf war korrekt, das Repo ist
nur noch nicht so weit.

Ein Fehler bricht den Lauf **nicht** ab: die übrigen Abgaben gehen trotzdem
raus, und ein Classroom mit unlesbarer `scores.json` stoppt die übrigen nicht.
Der Exit-Code fasst am Ende über alle Classrooms zusammen.

### Beispiele

Alle Beispiele aus der Wurzel des Config-Repos:

```bash
# Trockenlauf über ein Classroom, ohne Zugangsdaten
python -m pygrader50.moodle --classroom <CLASSROOM> --dry-run --no-feedback

# Eine einzelne Person nachtragen
python -m pygrader50.moodle --classroom <CLASSROOM> --user <LOGIN>

# Eine Aufgabe nach einer Nachbewertung komplett neu schicken
python -m pygrader50.moodle --classroom <CLASSROOM> --assignment <SLUG> --force

# Zwei Klassen desselben Config-Repos
python -m pygrader50.moodle --classroom <CLASSROOM-A> --classroom <CLASSROOM-B>

# Wie der Nachtlauf — "alle" ausdrücklich
python -m pygrader50.moodle --all-classrooms
```

Ohne lokalen Klon des Config-Repos genügt es, die Ablage nachzubauen:

```bash
mkdir -p <CLASSROOM>
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/scores.json \
   -H 'Accept: application/vnd.github.raw' > <CLASSROOM>/scores.json
GH_TOKEN=$(gh auth token) python -m pygrader50.moodle --classroom <CLASSROOM> --dry-run
```

Der Ordner muss sein: es gibt nur **eine** Aufrufform, und die erwartet die
Ablage des Config-Repos. Dafür geht jeder Aufruf durch dieselbe Scope-Prüfung.

### Manuell auslösen

Im Config-Repo unter **Actions → Moodle Sync → Run workflow**: Classroom,
optional Aufgabe und Login, dazu die Schalter `all_classrooms`, `dry_run` und
`force`. Ein **leeres** Classroom-Feld heisst nicht »alle« — der Lauf bricht
dann mit Exit 2 ab, ohne etwas zu senden. Für alle Klassen den Schalter
`all_classrooms` setzen. Der Workflow liegt hier als
[`classroom50/moodle-sync.yaml`](../classroom50/moodle-sync.yaml), Einbau siehe
[Einrichtung](einrichtung.md#61-workflow-einbauen).

```bash
gh workflow run moodle-sync.yaml --repo <ORG>/classroom50 \
  -f classroom=<CLASSROOM> -f dry_run=true

# alle Klassen des Config-Repos
gh workflow run moodle-sync.yaml --repo <ORG>/classroom50 \
  -f all_classrooms=true -f dry_run=true
```

## `scripts/remove-legacy-classroom-yml.sh` — migrieren

Entfernt den alten GitHub-Classroom-Workflow aus den Template-Repos einer
migrierten Klasse und aus den bereits angenommenen Studi-Repos.

```
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM> [--apply]
```

| Aufruf | Wirkung |
|---|---|
| ohne `--apply` | Trockenlauf, listet jedes Ziel als `would rm` oder `absent` |
| mit `--apply` | löscht `.github/workflows/classroom.yml`, ein Commit pro Repo |

Die Zielliste kommt aus dem `template`-Block von `<CLASSROOM>/assignments.json`,
**nicht** aus dem Repo-Listing der Template-Organisation. Wiederholbar; fehlende
Dateien sind `absent`, kein Fehler. Exit 1, sobald ein Repo scheitert.

Hintergrund und die nötige Token-Rotation: [Migration](migration.md).

## `scripts/sync-template-pins.py` — Pins aktualisieren

Hebt die Werkzeug-Versionen in den Template-Repos einer Klasse und legt
`.python-version` an.

```
scripts/sync-template-pins.py <ORG> <CLASSROOM> [--apply]
```

| Was | Verhalten |
|---|---|
| `pylint`, `pytest` | werden überall gesetzt, fehlende Zeilen angehängt |
| `httpx`, `pytest-asyncio` | nur dort gehoben, wo sie schon stehen |
| alles andere | bleibt Zeile für Zeile erhalten, inkl. Kommentaren |
| `.python-version` | wird auf die konfigurierte Version gesetzt |

Die Versionen stehen als Block am Kopf des Skripts. Wiederholbar: ein bereits
aktuelles Template meldet `ok`.

`pytest-asyncio` muss mit `pytest` mitziehen — alte Versionen und pytest 9
lassen sich nicht gemeinsam auflösen. Pakete, welche die Lernenden selbst
eintragen sollen, gehören nicht in die Pin-Liste.

## `scripts/sync-template-docstrings.py` — Aufgabenlink setzen

Schreibt in jedes Template einen Modul-Docstring, der die Aufgabe benennt und
auf ihre Seite in einer externen Aufgabensammlung zeigt.

```
scripts/sync-template-docstrings.py <ORG> <CLASSROOM> [--apply]
```

```python
"""ToDo-Liste mit SQLite und DAO-Klassen.

Aufgabenstellung: https://wiki.example.org/lu06/aufgaben/dao
"""
```

| Was | Verhalten |
|---|---|
| Zieldatei | die erste Datei aus `lint.json`, `main.py` bevorzugt |
| vorhandener Modul-Docstring | wird ersetzt, nicht ergänzt |
| Datei ohne gültiges Python | Docstring wird vorangestellt, sofern die Datei nicht schon mit einem String beginnt |
| Aufgabe ohne eindeutige Zielseite | `SKIP`, es wird nicht geraten |

Der Slug führt nicht zwangsläufig zur Zielseite — Nummerierung und Seitennamen
können auseinanderlaufen. Schlüssel ist ein Code in der Seitenüberschrift; trägt
ein Code mehrere Seiten, entscheidet der `OVERRIDES`-Block am Kopf des Skripts,
sonst wird übersprungen.

Das Skript ist auf eine bestimmte Aufgabensammlung zugeschnitten. Wer eine
andere benutzt, passt die Auflösung am Kopf des Skripts an oder lässt es weg —
für die Bewertung ist es nicht nötig.

## `gh teacher` — Classrooms verwalten

Nicht Teil dieses Repos, aber die Gegenstelle. Dieselben Handgriffe gibt es in
der Web-Oberfläche [classroom50.org](https://classroom50.org); die CLI ist der
skriptbare Weg. Vollständige Referenz im
[Wiki von foundation50/classroom50](https://github.com/foundation50/classroom50/wiki).

```bash
gh extension install foundation50/gh-teacher
gh auth refresh -h github.com -s admin:org,read:org,repo,workflow

gh teacher classroom list <ORG>
gh teacher assignment list <ORG> <CLASSROOM>
gh teacher assignment add <ORG> <CLASSROOM> <SLUG> --name "<SLUG>" --template <OWNER>/<REPO>@main
gh teacher assignment submission-mode <ORG> <CLASSROOM> <SLUG> --every-push
gh teacher assignment submission-mode <ORG> <CLASSROOM> <SLUG> --tag
gh teacher autograder show <ORG> <CLASSROOM>
gh teacher autograder set-default <ORG> <CLASSROOM> --from bootstrap/autograder.py
gh teacher rotate-service-token <ORG>
```

`submission-mode` schreibt nicht nur das Feld in `assignments.json`, sondern
auch `.github/workflows/autograde.yaml` in jedem bestehenden Studi-Repo — der
Auslöser sitzt dort, nicht zentral. Details und Fallstricke unter
[Betrieb](betrieb.md#abgabemodus-jeder-push-oder-nur-submit-tags).

## `gh student` — abgeben

Die Gegenstelle auf der Seite der Lernenden. Braucht es nur bei Aufgaben im
Tag-Modus; ein von Hand gesetzter `submit/*`-Tag tut dasselbe.

```bash
gh extension install foundation50/gh-student
gh student submit
```
