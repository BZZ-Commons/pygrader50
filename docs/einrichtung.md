# Einrichtung

Von einem laufenden Classroom 50 bis zu Noten in Moodle — für einen beliebigen
Classroom. Reihenfolge einhalten; jeder Schritt ist einzeln prüfbar.

Platzhalter siehe [Übersicht](README.md#platzhalter).

## 0. Voraussetzungen

Ein `classroom50`-Config-Repo unter `<ORG>` mit laufenden Workflows
(`publish-pages`, `collect-scores`), erzeugt von `gh teacher classroom add`.

```bash
gh extension install foundation50/gh-teacher
gh auth refresh -h github.com -s admin:org,read:org,repo,workflow
```

Der zweite Befehl ist keine Formalie: ohne `admin:org` bricht **jeder**
`gh teacher`-Aufruf mit einer Scope-Meldung ab. Er öffnet den Browser und
braucht deshalb ein interaktives Terminal.

**Prüfen:**

```bash
gh teacher classroom list <ORG>
```

## 1. Engine veröffentlichen

Nur nötig, wenn du pygrader50 selbst weiterentwickelst — für einen neuen
Classroom pinnst du einen bestehenden Tag und überspringst diesen Schritt.

```bash
git tag <TAG> && git push origin main --tags
```

Der Tag ist das, was die Classrooms pinnen. Ohne Tag kein reproduzierbares
Semester: `main` würde sich unter laufenden Bewertungen verändern.

Zum Tag gehören die Werkzeug-Versionen. `pyproject.toml` pinnt `pytest`,
`pytest-timeout` und `pylint` exakt, nicht als Untergrenze — sonst installierte
jeder Bewertungslauf das jeweils Neueste, und eine pylint-Minor-Version
verschöbe mitten im Semester allen die Lint-Punkte. Ein Upgrade heisst deshalb:

1. Pins in `pyproject.toml` hochziehen und lokal prüfen, dass sie zusammen installieren.
2. `version` dort und `__version__` in `src/pygrader50/__init__.py` anheben.
3. `VERSION` in `bootstrap/autograder.py` und den Tag in `classroom50/moodle-sync.yaml` mitziehen.
4. Taggen, dann Schritt 2 dieser Anleitung erneut ausführen.

**Prüfen**, dass der Pin installierbar ist — sonst scheitert er erst im ersten
Studi-Lauf:

```bash
python3 -m venv /tmp/pin && /tmp/pin/bin/pip install \
  "pygrader50 @ git+https://github.com/BZZ-Commons/pygrader50@<TAG>"
```

## 2. Klassen-Default setzen

Pro Classroom einmal:

```bash
gh teacher autograder set-default <ORG> <CLASSROOM> --from bootstrap/autograder.py
```

Das legt `<CLASSROOM>/autograder.py` im Config-Repo ab; `publish-pages` stellt
die Datei auf die Pages-Site, wo `runner.py` sie bei jeder Abgabe holt.

Die gepinnte Version steht in `bootstrap/autograder.py`:

```python
VERSION = 'v2.1.2'
```

Ein Upgrade heisst später: Tag hochziehen, Zeile ändern, `set-default` erneut
ausführen — pro Classroom, der mitziehen soll. Klassen können bewusst auf
unterschiedlichen Versionen bleiben.

**Vorher prüfen**, was du überschreibst:

```bash
gh teacher autograder show <ORG> <CLASSROOM>
gh teacher autograder list <ORG> <CLASSROOM>
```

**Nachher prüfen**, dass Pages die Datei ausliefert:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://<ORG>.github.io/classroom50/<CLASSROOM>/autograder.py
```

> Das Klassen-Segment im Pfad ist Pflicht. `…/classroom50/autograder.py` **ohne**
> `<CLASSROOM>/` liefert 404 — eine beliebte Fehlspur beim Prüfen. Der Deploy
> braucht nach dem Push rund 30 Sekunden.

Dann in einem Test-Repo etwas pushen: Das Release muss eine echte Punktzahl
zeigen statt `0/0`. Im Job-Log steht, welche Konfigurationsdateien gefunden
wurden.

## 3. Aufgaben registrieren

Jede Aufgabe braucht einen Eintrag in `<CLASSROOM>/assignments.json`:

```bash
gh teacher assignment add <ORG> <CLASSROOM> <SLUG> \
  --name "<SLUG>" \
  --template <TEMPLATE-ORG>/<SLUG>@main \
  --runtime runtime.json
```

`runtime.json` legt die Python-Version fest:

```json
{ "python": "3.14" }
```

Ohne `--runtime` nimmt der Runner seine eigene Vorgabe. Die ist heute dieselbe,
aber es ist eine Upstream-Entscheidung, die sich ohne Zutun ändern kann —
deshalb besser explizit setzen.

Das Template-Repo muss als **Template repository** markiert sein (Settings →
*Template repository*), sonst lehnt die CLI es ab.

**Prüfen**, dass die Pages-Site den neuen Eintrag ausliefert:

```bash
curl -s https://<ORG>.github.io/classroom50/<CLASSROOM>/assignments.json \
  | jq -r '.assignments[].slug'
```

Vorher lohnt ein Blick ins Template: lösen alle `function`-Namen aus
`unittests.json` wirklich auf Testfunktionen auf? Ein Tippfehler ergibt still
null Punkte. Der schnellste Test ist ein lokaler Lauf gegen das Template, siehe
[Bewertung](bewertung.md#lokal-ausprobieren).

## 4. Aufgaben-Konfiguration ablegen

Die drei Dateien können bleiben, wo sie sind (`.github/autograding/` im
Studi-Repo) — dann ist hier nichts zu tun. Manipulationssicher wird es erst im
Config-Repo, weil Lernende ihr eigenes `.github/` bearbeiten können.

Aufbau, Vorrangregeln und die Abwägung: [Bewertung](bewertung.md#ein-bundle-anlegen).

## 5. Von GitHub Classroom kommende Templates migrieren

Nur bei Klassen mit Vorgeschichte — vollständig unter [Migration](migration.md).
Kurzfassung:

```bash
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM>            # Trockenlauf
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM> --apply    # löschen
```

Danach den alten Moodle-Token **löschen und rotieren**.

## 6. Moodle-Übertrag einrichten

### 6.1 Workflow einbauen

```bash
cp classroom50/moodle-sync.yaml <config-repo>/.github/workflows/moodle-sync.yaml
```

Eigener Dateiname, keine bestehende Datei anfassen: `gh teacher` überschreibt
die mitgelieferten Skeleton-Workflows bei einem Refresh.

Die Datei ist classroom-neutral. Bleibt die Eingabe `classroom` leer, wird jeder
Ordner mit einer `scores.json` übertragen — ein Config-Repo mit mehreren Klassen
braucht keine zweite Kopie. Anzupassen ist nur der gepinnte Tag, falls er von
`bootstrap/autograder.py` abweicht.

### 6.2 Zugangsdaten, Moodle-Seite, erster Lauf

Vollständig unter [Moodle](moodle.md). Kurz:

1. Secret `MOODLE_TOKEN` und Variable `MOODLE_URL` im **Config-Repo** setzen.
2. In Moodle je Aufgabe eine Aktivität *External Assignment* mit dem Slug als Namen.
3. Das Profilfeld mit dem GitHub-Login bei allen Teilnehmenden füllen lassen.
4. **Actions → Moodle Sync → Run workflow** mit `dry_run`, Ausgabe prüfen.
5. Dasselbe ohne `dry_run`. Danach liegt `<CLASSROOM>/moodle-state.json` im Repo.

> Ein Trockenlauf baut **nie** einen Endpunkt und prüft deshalb weder URL noch
> Token noch Funktionsnamen. Er beweist nur, welche Abgaben ausgewählt würden.
> Der erste echte Lauf ist der eigentliche Test.

## 7. Betriebsfallen kennen

Vier Verhaltensweisen der Classroom-50-Seite, die man einmal gelesen haben muss,
bevor der erste Nachtlauf rot wird: [Betrieb → Betriebsfallen](betrieb.md#betriebsfallen).
