# Einrichtung

Von einem laufenden Classroom 50 bis zu Noten in Moodle — für ein **beliebiges**
Klassenzimmer. Reihenfolge einhalten; jeder Schritt ist einzeln prüfbar.

Die Beispiele verwenden durchgehend Platzhalter:

| Platzhalter | Bedeutung | Beispiel |
|---|---|---|
| `<ORG>` | GitHub-Organisation der Klasse | `m320-ix25` |
| `<CLASSROOM>` | Kurzname des Klassenzimmers = Ordner im Config-Repo | `m320-ix25` |
| `<SLUG>` | Slug einer Aufgabe | `m320-lu04-a4-objektkommunikation` |
| `<TAG>` | gepinnte pygrader50-Version | `v2.0.0` |

`<ORG>` und `<CLASSROOM>` sind oft gleich, müssen es aber nicht sein — der
Kurzname steht in `<CLASSROOM>/classroom.json`.

---

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

Prüfen:

```bash
gh teacher classroom list <ORG>
```

---

## 1. Engine veröffentlichen

Nur nötig, wenn du pygrader50 selbst weiterentwickelst — für ein neues
Klassenzimmer pinnst du einen bestehenden Tag und überspringst diesen Schritt.

```bash
git tag v2.0.0 && git push origin main --tags
```

Der Tag ist das, was die Klassenzimmer pinnen. Ohne Tag kein reproduzierbares
Semester: `main` würde sich unter laufenden Bewertungen verändern.

**Prüfen**, dass der Pin installierbar ist — sonst scheitert er erst im ersten
Studi-Lauf:

```bash
python3 -m venv /tmp/pin && /tmp/pin/bin/pip install \
  "pygrader50 @ git+https://github.com/BZZ-Commons/pygrader50@<TAG>"
```

---

## 2. Default-Autograder setzen

Pro Klassenzimmer einmal:

```bash
gh teacher autograder set-default <ORG> <CLASSROOM> --from bootstrap/autograder.py
```

Das legt `<CLASSROOM>/autograder.py` im Config-Repo ab; `publish-pages` stellt
die Datei auf die Pages-Site, wo `runner.py` sie bei jeder Abgabe holt.

Die Version steht in `bootstrap/autograder.py`:

```python
VERSION = 'v2.0.0'
```

Ein Upgrade heisst später: Tag hochziehen, Zeile ändern, `set-default` erneut
ausführen — pro Klassenzimmer, das mitziehen soll. Klassen können bewusst auf
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

Der Klassen-Segment-Pfad ist Pflicht. `…/classroom50/autograder.py` **ohne**
`<CLASSROOM>/` liefert 404 — eine beliebte Fehlspur beim Prüfen. Der Deploy
braucht nach dem Push rund 30 Sekunden.

Dann in einem Test-Repo etwas pushen: das Release der Abgabe muss eine echte
Punktzahl zeigen (z. B. `0/7`) statt `0/0`. Im Job-Log steht, welche
Konfigurationsdateien gefunden wurden.

---

## 3. Aufgaben-Konfiguration ablegen

Die drei Dateien können bleiben, wo sie sind (`.github/autograding/` im
Studi-Repo) — dann ist nichts zu tun. Manipulationssicher wird es erst im
Config-Repo, weil Studierende ihr eigenes `.github/` bearbeiten können:

```
classroom50/
└── <CLASSROOM>/
    └── autograders/
        └── <SLUG>/
            ├── unittests.json
            ├── lint.json
            └── pylintrc
```

Nach dem Push bündelt `publish-pages` den Ordner zu `autograders/<SLUG>.tar.gz`;
`runner.py` entpackt ihn und pygrader50 liest von dort.

**Wichtig:** kein `autograder.py` und keine `tests.json` in den Ordner legen.
`runner.py` löst in dieser Reihenfolge auf — per-Assignment `autograder.py` →
per-Assignment `tests.json` → Klassen-Default → 0/0. Beides würde den
Klassen-Default verdrängen und damit auch das Linting abschalten.

Vorlage: [`examples/bundle/`](examples/bundle). Quelle für den Rollout sind die
Template-Repos, dort liegen die Dateien bereits.

**Prüfen:** Punkte in der Bundle-`unittests.json` ändern, pushen, neu bewerten
lassen — die neue Maximalpunktzahl muss im Release stehen.

---

## 4. Template-Repos migrieren

Templates aus der GitHub-Classroom-Zeit tragen einen eigenen Bewertungs-Workflow.
Er muss weg, sonst laufen bei jedem Push zwei Autograder nebeneinander.

### 4.1 Was raus muss

`.github/workflows/classroom.yml`. Zwei Jobs stecken darin:

| Job | Was damit passiert |
|---|---|
| `grading` | ruft den alten pygrader-Workflow — ersetzt durch Classroom 50 |
| `copy-issues` | läuft nur unter `if: contains(github.actor, 'classroom')`, also nur beim GitHub-Classroom-Bot; unter Classroom 50 feuert er nie |

Ein separates `copyissues.yml` mit `workflow_dispatch` macht dasselbe manuell.
Beim Löschen von `classroom.yml` geht also keine Funktion verloren.

### 4.2 Was bleiben muss

`.github/autograding/` mit `unittests.json`, `lint.json`, `pylintrc` — das ist
der Fallback, solange Schritt 3 nicht für alle Aufgaben erledigt ist. Erst wenn
jede Aufgabe ein Bundle im Config-Repo hat, kann der Ordner verschwinden.

`requirements.txt` und Hilfsskripte wie `_run_pylint.py` stören die Bewertung
nicht — pygrader50 installiert die Studi-`requirements.txt` bewusst nicht. Für
die lokale Arbeit der Studierenden zählt sie trotzdem, deshalb hält sie ein
eigenes Skript aktuell:

```bash
scripts/sync-template-pins.py <ORG> <CLASSROOM>            # Trockenlauf
scripts/sync-template-pins.py <ORG> <CLASSROOM> --apply    # schreiben
```

Es hebt die Werkzeug-Pins (`pylint`, `pytest`, und wo vorhanden `httpx` /
`pytest-asyncio`) und legt `.python-version` an. Alles andere bleibt
unangetastet — Pakete, die die Studierenden im Rahmen der Aufgabe selbst
eintragen sollen (Flask in den lu06-Aufgaben), gehören nicht hinein.

Die Versionen stehen als Block am Kopf des Skripts und werden einmal pro
Semester angefasst. `pytest-asyncio` muss dabei mit `pytest` mitziehen: 0.23.8
und pytest 9 sind ein `ResolutionImpossible`.

### 4.3 Die Zielliste richtig bilden

**Nicht** die Repos der Template-Organisation auflisten. Dort liegen auch
Templates von Modulen, die noch auf dem alten Pfad laufen — ihnen den Workflow
zu nehmen, stoppt dort still die Bewertung.

Massgeblich ist der `template`-Block in `<CLASSROOM>/assignments.json`:

```bash
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/assignments.json \
   -H 'Accept: application/vnd.github.raw' \
  | jq -r '.assignments[] | "\(.template.owner)/\(.template.repo)"' | sort -u
```

### 4.4 Ausführen

```bash
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM>            # Trockenlauf
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM> --apply    # löschen
```

Das Skript nimmt die Liste aus 4.3 und ergänzt die bereits angenommenen
Studi-Repos. Es ist wiederholbar; fehlende Dateien meldet es als `absent`.

**Template-Änderungen erreichen bestehende Repos nicht.** Ein Studi-Repo trägt
seine Kopie aus dem Moment der Annahme — deshalb behandelt das Skript beide
Seiten. Umgekehrt sind Repos früherer Klassen, die dasselbe Template benutzt
haben, von der Template-Änderung nicht betroffen.

### 4.5 Alten Token entwerten

Der alte Workflow reichte den Moodle-Token per `secrets: inherit` an den
Bewertungs-Workflow weiter. Jede Person mit Schreibrecht auf ein Studi-Repo
konnte ihn mit drei Zeilen auslesen.

1. Secret in **allen** betroffenen Organisationen löschen — typischerweise die
   Studi-Org *und* die Template-Org.
2. Den Token **in Moodle neu erzeugen und den alten invalidieren.** Löschen
   allein beendet nur die künftige Exposition, nicht die vergangene.

```bash
gh secret list --org <ORG>
```

---

## 5. Moodle-Übertrag einrichten

### 5.1 Workflow einbauen

[`classroom50/moodle-sync.yaml`](classroom50/moodle-sync.yaml) ins Config-Repo
kopieren:

```bash
cp classroom50/moodle-sync.yaml <config-repo>/.github/workflows/moodle-sync.yaml
```

Eigener Dateiname, keine bestehende Datei anfassen: `gh teacher` überschreibt die
mitgelieferten Skeleton-Workflows bei einem Refresh.

Die Datei ist klassenzimmer-neutral. Bleibt die Eingabe `classroom` leer, wird
jeder Ordner mit einer `scores.json` übertragen — ein Config-Repo mit mehreren
Klassen braucht keine zweite Kopie. Anpassen musst du nur den gepinnten Tag,
falls er von `bootstrap/autograder.py` abweicht.

### 5.2 Zugangsdaten hinterlegen

Im **classroom50-Repo** (nicht in der Studi-Organisation):

| Art | Name | Wert |
|---|---|---|
| Secret | `MOODLE_TOKEN` | Webservice-Token |
| Variable | `MOODLE_URL` | z. B. `https://moodle.bzz.ch` |
| Variable | `MOODLE_FUNCTION` | optional, Vorgabe `mod_externalassignment_update_grade` |

```bash
gh secret   set MOODLE_TOKEN --repo <ORG>/classroom50
gh variable set MOODLE_URL   --repo <ORG>/classroom50 --body "https://moodle.example.ch"
```

Der vorhandene `CLASSROOM50_SERVICE_TOKEN` wird für die Release-Bodies
weiterverwendet — er hat bereits Leserechte auf die Studi-Repos.

Für den Moodle-Token einen eigenen Webservice-Benutzer anlegen, der **nur** diese
eine Funktion darf. Der Token kann Noten für beliebige Personen setzen; je enger
die Rechte, desto kleiner der Schaden bei einem Leck.

### 5.3 Moodle-Seite prüfen

Der Übertrag verlangt eine Aktivität *External Assignment* mit **exakt dem Slug**
als Namen und einen Moodle-Benutzernamen, der dem GitHub-Login entspricht.

`No matching assignment found. Contact your teacher.` heisst **nicht** zwingend,
dass die Aktivität fehlt: das Plugin löst `(assignmentname, username)` gemeinsam
auf und meldet denselben Text, wenn nur der Benutzer im Kurs fehlt. Zum Testen
deshalb einen echten Studi-Login nehmen, nicht den eigenen Lehrer-Account — der
ist in Moodle meist kein Kursteilnehmer.

### 5.4 Erster Lauf

**Actions → Moodle Sync → Run workflow**, `dry_run` anhaken:

```
Moodle-Übertrag: 2 Abgaben
[dry-run] <SLUG> / anna:  5/7
[dry-run] <SLUG> / bruno: 7/7
übertragen: 2 | unverändert: 0 | fehlgeschlagen: 0
```

Sieht das richtig aus, dasselbe ohne `dry_run`. Danach liegt
`<CLASSROOM>/moodle-state.json` im Repo; ab dann überträgt jeder Lauf nur noch
Änderungen.

Der Nachtlauf steht auf `57 4 * * *` — 40 Minuten nach `collect-scores`. Wer
zwischendurch Noten braucht, drückt auf den Knopf.

Lokal geht dasselbe ohne Zugangsdaten:

```bash
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/scores.json \
   -H 'Accept: application/vnd.github.raw' > scores.json
GH_TOKEN=$(gh auth token) python -m pygrader50.moodle scores.json --dry-run
```

---

## 6. Betriebsfallen

Vier Verhaltensweisen der Classroom-50-Seite, die man einmal wissen muss.

### `scores.json` wird nie aufgeräumt

`collect_scores.py::apply_updates` ist ein reiner Upsert, keyed auf den
Repo-Owner. Ein Eintrag bleibt stehen, auch wenn das Repo gelöscht oder die
Person ausgetragen wurde. Da `python -m pygrader50.moodle` mit Exit 1 endet,
sobald **eine** Übertragung scheitert, färbt ein einziger solcher
Karteileichen-Eintrag den Nachtlauf dauerhaft rot.

Nach einer Abmeldung den Eintrag von Hand aus `<CLASSROOM>/scores.json`
entfernen.

### Eingesammelt wird nach Teams, nicht nach Roster

Massgeblich ist die Union aus Studenten-Team **und allen Staff-Teams**
(`teacher`, `hta`, `ta`). Wer als Lehrperson eine Aufgabe annimmt, um den Ablauf
zu testen, wird bewusst wie eine studierende Person bewertet und landet in
`scores.json` — und damit im Moodle-Übertrag, wo der Account dann fehlt.

Testrepos der Lehrperson nach dem Test löschen **und** den Eintrag aus
`scores.json` entfernen (siehe oben).

### Das Roster heisst `roster.csv`

CLI und `collect_scores.py` lesen ausschliesslich
`<CLASSROOM>/roster.csv` mit dem Header

```
username,first_name,last_name,email,section,github_id,role
```

Ältere Klassenzimmer haben eine `students.csv` — dann scheitert jeder
`gh teacher roster`-Befehl und der Namens-Join in `scores.json` bleibt leer.
Umbenennen und die `role`-Spalte ergänzen; eine Datei ohne sie wird zwar
gelesen, liefert aber `""`. Das Roster steuert die Bewertung nicht, es ist
Anzeigedaten.

### Der Service-Token braucht Administration-Rechte

`collect-scores` scheitert mit
`staff-team access grant failed with HTTP 403`, wenn dem
`CLASSROOM50_SERVICE_TOKEN` *Repository → Administration: Read and write* fehlt.
Die Punkte werden trotzdem gesammelt, der Job endet aber mit Exit 1 und die
TA-Teams bekommen keinen Zugriff.

```bash
gh teacher rotate-service-token <ORG>
```

---

## Fehlersuche

| Symptom | Ursache |
|---|---|
| `gh teacher …`: `missing scopes` | `gh auth refresh -h github.com -s admin:org,read:org,repo,workflow` in einem interaktiven Terminal (Schritt 0) |
| Release zeigt `0/0`, `tests: []` | Kein Autograder aktiv — Schritt 2 fehlt, oder `publish-pages` lief noch nicht |
| Pages liefert 404 für `autograder.py` | Klassen-Segment vergessen: `…/classroom50/<CLASSROOM>/autograder.py` |
| Log: `no grading configuration found` | Weder Bundle noch `.github/autograding/` enthält `unittests.json` / `lint.json` |
| Commit-Status `error`, kein Release | Exit ≠ 0: `pip install` gescheitert (Netz, Tag falsch) oder Absturz — Traceback steht im Job-Log |
| Bundle wird ignoriert | Ordner enthält `autograder.py` oder `tests.json`, oder `publish-pages` lief nach dem Push nicht |
| Lint-Punkte weichen von früher ab | Auf Python 3.14 installiert sich pylint 4.x statt der alten 3.2.7 — strengere Prüfungen |
| Lint gibt 0 Punkte | Bei wenigen Statements und einem `E…` wird die pylint-Note negativ und auf 0 geklemmt — korrekt, kein Defekt |
| Moodle: `No matching assignment found` | Aktivitätsname **oder** Kursmitgliedschaft passt nicht (Schritt 5.3) |
| Moodle: `keine XML-Antwort erhalten` | Falsche `MOODLE_URL` oder ungültiger Token — Moodle liefert eine Login-Seite |
| Noten kommen nicht an, Log sagt „unverändert" | Zustandsfile hält sie für erledigt — mit `force` erneut auslösen |
| Moodle-Sync jede Nacht rot, immer dieselbe Person | Karteileichen-Eintrag in `scores.json` (Schritt 6) |
| `collect-scores` rot, Punkte trotzdem da | Service-Token ohne Administration-Recht (Schritt 6) |

## Verantwortlichkeiten

| Was | Wo | Warum dort |
|---|---|---|
| Bewertungs-Engine, Moodle-Übertrag | `BZZ-Commons/pygrader50` | eine Quelle, versioniert, für alle Klassenzimmer |
| Default-Autograder, Aufgaben-Bundles, Moodle-Token | `<ORG>/classroom50` | von der Lehrperson kontrolliert, für Studierende nicht schreibbar |
| Startcode, Tests, Musterlösung | Template-Repo | gehört zur Aufgabe |
| Abgabe | Studi-Repo | gehört den Studierenden |
