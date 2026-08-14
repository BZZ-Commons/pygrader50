# CLI-Referenz

Zwei Kommandos: eines bewertet, eines überträgt.

---

## `python -m pygrader50` — bewerten

Wird vom Classroom-50-Runner im Studi-Checkout aufgerufen. Keine Argumente —
alles kommt aus der Umgebung.

### Umgebung

Setzt der Runner (`run_entrypoint` in `runner.py`):

| Variable | Bedeutung | Pflicht |
|---|---|---|
| `CLASSROOM` | Kurzname des Klassenzimmers | ja |
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
CLASSROOM=m323-ix24 \
ASSIGNMENT=m323-lu01-a02-imperativer-ggt \
SUBMISSION_TAG=submit/2026-08-13T12-00-00Z-abc1234 \
OWNER=graphics80 \
python -m pygrader50
cat release-body.md
```

---

## `python -m pygrader50.moodle` — übertragen

Liest `scores.json` aus dem classroom50-Config-Repo und schickt die Punkte an
Moodle. Je (Assignment, Owner) geht die **neueste** Abgabe raus.

```
python -m pygrader50.moodle SCORES [Optionen]
```

### Argumente und Optionen

| Option | Wirkung |
|---|---|
| `SCORES` | Pfad zu `<classroom>/scores.json` (Pflicht) |
| `--assignment SLUG` | nur diese Aufgabe |
| `--user LOGIN` | nur diesen GitHub-Login |
| `--state PFAD` | Zustandsfile; ohne Angabe wird jedes Mal alles übertragen |
| `--force` | auch Unverändertes erneut senden |
| `--dry-run` | nur anzeigen, nichts senden; funktioniert ohne Zugangsdaten |
| `--no-feedback` | ohne Feedback-Text (spart einen API-Aufruf pro Abgabe) |

### Umgebung

| Variable | Bedeutung |
|---|---|
| `MOODLE_URL` | Basis-URL der Moodle-Instanz, z. B. `https://moodle.bzz.ch` |
| `MOODLE_TOKEN` | Webservice-Token |
| `MOODLE_FUNCTION` | Vorgabe `mod_externalassignment_update_grade` |
| `GH_TOKEN` / `GITHUB_TOKEN` | optional, liest die Release-Bodies für den Feedback-Text |

Ohne `--dry-run` sind `MOODLE_URL` und `MOODLE_TOKEN` Pflicht.

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
    "m323-lu01-a02-imperativer-ggt/graphics80": {
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
| `1` | mindestens eine Übertragung scheiterte, oder Zugangsdaten/Datei fehlen |

Ein Fehler bricht den Lauf **nicht** ab: die übrigen Abgaben gehen trotzdem raus.

### Beispiele

```bash
# Trockenlauf über alles, ohne Zugangsdaten
python -m pygrader50.moodle m323-ix24/scores.json --dry-run --no-feedback

# Eine einzelne Person nachtragen
python -m pygrader50.moodle m323-ix24/scores.json --user graphics80

# Eine Aufgabe nach einer Nachbewertung komplett neu schicken
python -m pygrader50.moodle m323-ix24/scores.json \
  --assignment m323-lu01-a02-imperativer-ggt --force

# Wie der Nachtlauf
python -m pygrader50.moodle m323-ix24/scores.json --state m323-ix24/moodle-state.json
```

### Manuell auslösen

Im classroom50-Repo unter **Actions → Moodle Sync → Run workflow**: Klassenzimmer,
optional Aufgabe und Login, dazu die Schalter `dry_run` und `force`. Der Workflow
liegt hier als [`classroom50/moodle-sync.yaml`](classroom50/moodle-sync.yaml),
Einbau siehe [SETUP.md](SETUP.md).
