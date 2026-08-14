# Einrichtung

Von einem laufenden Classroom 50 bis zu Noten in Moodle. Reihenfolge einhalten —
jeder Schritt ist einzeln prüfbar.

Voraussetzungen: ein `classroom50`-Config-Repo mit laufenden Workflows
(`publish-pages`, `collect-scores`), die `gh`-CLI mit den Teacher-Erweiterungen,
und Push-Rechte auf `BZZ-Commons/pygrader50`.

---

## 1. Engine veröffentlichen

```bash
git tag v2.0.0 && git push origin main --tags
```

Der Tag ist das, was die Klassenzimmer pinnen. Ohne Tag kein reproduzierbares
Semester: `main` würde sich unter laufenden Bewertungen verändern.

## 2. Default-Autograder setzen

```bash
gh teacher autograder set-default m323-ix24 m323-ix24 --from bootstrap/autograder.py
```

Das legt `m323-ix24/autograder.py` im Config-Repo ab; `publish-pages` stellt die
Datei auf die Pages-Site, wo `runner.py` sie bei jeder Abgabe holt.

Die Version steht in `bootstrap/autograder.py`:

```python
VERSION = 'v2.0.0'
```

Ein Upgrade heisst später: Tag hier hochziehen, Zeile ändern, `set-default`
erneut ausführen.

**Prüfen:** in einem Test-Repo etwas pushen. Das Release der Abgabe muss jetzt
eine echte Punktzahl zeigen (z. B. `0/7`) statt `0/0`. Im Job-Log steht, welche
Konfigurationsdateien gefunden wurden.

## 3. Aufgaben-Konfiguration ablegen

Die drei Dateien können bleiben, wo sie sind (`.github/autograding/` im
Studi-Repo) — dann ist nichts zu tun. Manipulationssicher wird es erst im
Config-Repo:

```
classroom50/
└── m323-ix24/
    └── autograders/
        └── m323-lu01-a02-imperativer-ggt/
            ├── unittests.json
            ├── lint.json
            └── pylintrc
```

Nach dem Push bündelt `publish-pages` den Ordner zu
`autograders/<slug>.tar.gz`; `runner.py` entpackt ihn und pygrader50 liest von
dort. **Wichtig:** kein `autograder.py` und keine `tests.json` in den Ordner
legen — sonst greift der Ordner selbst als Autograder und der Klassen-Default
kommt nicht mehr zum Zug.

Vorlage: [`examples/bundle/`](examples/bundle). Quelle für den Rollout sind die
`templates-python`-Repos, dort liegen die Dateien bereits.

**Prüfen:** Punkte in der Bundle-`unittests.json` ändern, pushen, neu bewerten
lassen — die neue Maximalpunktzahl muss im Release stehen.

## 4. Moodle-Übertrag einrichten

### 4.1 Workflow einbauen

[`classroom50/moodle-sync.yaml`](classroom50/moodle-sync.yaml) ins Config-Repo
kopieren:

```bash
cp classroom50/moodle-sync.yaml <config-repo>/.github/workflows/moodle-sync.yaml
```

Eigener Dateiname, keine bestehende Datei anfassen: `gh teacher init` überschreibt
die mitgelieferten Skeleton-Workflows bei einem Update.

### 4.2 Zugangsdaten hinterlegen

Im **classroom50-Repo** (nicht in der Studi-Organisation):

| Art | Name | Wert |
|---|---|---|
| Secret | `MOODLE_TOKEN` | Webservice-Token |
| Variable | `MOODLE_URL` | z. B. `https://moodle.bzz.ch` |
| Variable | `MOODLE_FUNCTION` | optional, Vorgabe `mod_externalassignment_update_grade` |

Der vorhandene `CLASSROOM50_SERVICE_TOKEN` wird für die Release-Bodies
weiterverwendet — er hat bereits Leserechte auf die Studi-Repos.

Für den Moodle-Token einen eigenen Webservice-Benutzer anlegen, der **nur** diese
eine Funktion darf. Der Token kann Noten für beliebige Personen setzen; je enger
die Rechte, desto kleiner der Schaden bei einem Leck.

### 4.3 Moodle-Seite prüfen

Der Übertrag verlangt, dass in Moodle eine Aktivität *External Assignment* mit
**exakt dem Slug** als Namen existiert (`m323-lu01-a02-imperativer-ggt`) und der
Moodle-Benutzername dem GitHub-Login entspricht. Stimmt das nicht, antwortet
Moodle mit `No matching assignment found. Contact your teacher.`

### 4.4 Erster Lauf

**Actions → Moodle Sync → Run workflow**, `dry_run` anhaken. Das Log zeigt, was
gesendet würde:

```
Moodle-Übertrag: 2 Abgaben
[dry-run] m323-lu01-a02-imperativer-ggt / fage34: 5/7
[dry-run] m323-lu01-a02-imperativer-ggt / graphics80: 7/7
übertragen: 2 | unverändert: 0 | fehlgeschlagen: 0
```

Sieht das richtig aus, dasselbe ohne `dry_run`. Danach liegt
`m323-ix24/moodle-state.json` im Repo; ab dann überträgt jeder Lauf nur noch
Änderungen.

Der Nachtlauf steht auf `57 4 * * *` — 40 Minuten nach `collect-scores`. Wer
zwischendurch Noten braucht, drückt auf den Knopf.

---

## 5. Alten Pfad abschalten

Solange die alte `classroom.yml` in den Studi-Repos liegt, läuft bei jedem Push
zusätzlich der GitHub-Classroom-Workflow: doppelte Actions-Minuten und ein
zweiter Schreiber auf demselben Moodle-Notenbuch.

1. `.github/workflows/classroom.yml` aus den `templates-python`-Repos löschen.
2. Aus den bestehenden Studi-Repos löschen (Schleife über die Organisation).
3. `BZZ-Commons/pygrader` als deprecated markieren.
4. **`MOODLE_TOKEN2` in der Studi-Organisation entfernen und rotieren.** Das
   Secret war über `secrets: inherit` aus jedem Studi-Repo auslesbar.

---

## Fehlersuche

| Symptom | Ursache |
|---|---|
| Release zeigt `0/0`, `tests: []` | Kein Autograder aktiv — Schritt 2 fehlt, oder `publish-pages` lief noch nicht |
| Log: `no grading configuration found` | Weder Bundle noch `.github/autograding/` enthält `unittests.json` / `lint.json` |
| Commit-Status `error`, kein Release | Exit ≠ 0: `pip install` gescheitert (Netz, Tag falsch) oder Absturz — Traceback steht im Job-Log |
| Bundle wird ignoriert | Ordner enthält `autograder.py` oder `tests.json`, oder `publish-pages` lief nach dem Push nicht |
| Lint-Punkte weichen von früher ab | Auf Python 3.14 installiert sich pylint 4.x statt der alten 3.2.7 — strengere Prüfungen |
| Moodle: `No matching assignment found` | Aktivitätsname oder Benutzername in Moodle passt nicht zu Slug/GitHub-Login (Schritt 4.3) |
| Moodle: `keine XML-Antwort erhalten` | Falsche `MOODLE_URL` oder ungültiger Token — Moodle liefert eine Login-Seite |
| Noten kommen nicht an, Log sagt „unverändert" | Zustandsfile hält sie für erledigt — mit `force` erneut auslösen |

## Verantwortlichkeiten

| Was | Wo | Warum dort |
|---|---|---|
| Bewertungs-Engine, Moodle-Übertrag | `BZZ-Commons/pygrader50` | eine Quelle, versioniert, für alle Klassenzimmer |
| Default-Autograder, Aufgaben-Bundles, Moodle-Token | `<org>/classroom50` | von der Lehrperson kontrolliert, für Studierende nicht schreibbar |
| Startcode, Tests, Musterlösung | `templates-python/<slug>` | gehört zur Aufgabe |
| Abgabe | Studi-Repo | gehört den Studierenden |
