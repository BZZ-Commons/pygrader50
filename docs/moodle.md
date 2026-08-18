# Noten nach Moodle übertragen

Der Übertrag läuft **zentral** aus dem Config-Repo und **zeitgesteuert**, nicht
bei jedem Push.

## Warum zentral

Der Moodle-Webservice-Token kann Noten für **beliebige Personen** setzen. In
einem Studi-Repo liest ihn ein selbst hinzugefügter Workflow in drei Zeilen aus.

Technisch geht es unter Classroom 50 ohnehin nicht anders: der zentrale Reusable
Workflow `autograde-runner.yaml` deklariert nur `outputs:` und reicht **keine
Secrets** an den Bewertungs-Job durch.

Zeitgesteuert statt bei jedem Push, weil der direkte Weg einen Token in jedem
Studi-Repo bräuchte, eine eigene Workflow-Datei je Repo, eine nachgebaute
Skip-Logik und spürbar mehr Actions-Minuten — und einen Nacht-Fallback bräuchte
es trotzdem.

## Voraussetzungen auf der Moodle-Seite

Der Übertrag benutzt das Plugin
[`mod_externalassignment`](https://moodle.org/plugins/mod_externalassignment).

1. Eine Aktivität vom Typ **External Assignment** je Aufgabe.
2. Ihr Name ist **exakt der Slug** der Aufgabe.
3. Der **GitHub-Login steht in einem Profilfeld** der lernenden Person.
4. Die Person ist im Kurs eingeschrieben.

### Die Zuordnung läuft über ein Profilfeld

Das ist der Punkt, an dem die meiste Zeit verloren geht. Das Plugin sucht den
GitHub-Login **ausschliesslich** in einem benutzerdefinierten Profilfeld:

```sql
SELECT userid FROM {user_info_data} WHERE fieldid=:fieldid AND data=:ghusername
```

Welches Feld, sagt die Plugin-Einstellung
`mod_externalassignment/external_username` (Vorgabe: Kurzname `github_user`).
Der angezeigte Label des Feldes kann davon abweichen — massgeblich ist der
Kurzname in der Einstellung.

**Der Moodle-Benutzername spielt für die Zuordnung keine Rolle.** Stimmen die
beiden bei Testkonten zufällig überein, fällt ein falsch konfiguriertes Feld
nicht auf — und geht später bei der ganzen Klasse schief.

Zwei Fehlermeldungen, die auseinanderzuhalten sind:

| Meldung | Bedeutung |
|---|---|
| `No Moodle user found with username "X": Update your Moodle profile.` | Profilfeld leer oder falsch geschrieben |
| `No matching assignment found. Contact your teacher.` | Aktivität fehlt **oder** die Person ist nicht im Kurs — das Plugin löst `(assignmentname, userid)` gemeinsam auf |

Zum Testen deshalb einen echten Lernenden-Login nehmen, nicht den eigenen
Lehrer-Account — der ist im Kurs meist kein Teilnehmer und erzeugt die zweite
Meldung, obwohl die Aktivität existiert.

## Zugangsdaten

Im **Config-Repo**, nicht in der Studi-Organisation:

| Art | Name | Wert |
|---|---|---|
| Secret | `MOODLE_TOKEN` | Webservice-Token |
| Variable | `MOODLE_URL` | z. B. `https://moodle.example.org` |
| Variable | `MOODLE_FUNCTION` | optional, Vorgabe `mod_externalassignment_update_grade` |

```bash
gh secret   set MOODLE_TOKEN --repo <ORG>/classroom50
gh variable set MOODLE_URL   --repo <ORG>/classroom50 --body "https://moodle.example.org"
```

Für den Token einen **eigenen Webservice-Benutzer** anlegen, der nur diese eine
Funktion darf. Je enger die Rechte, desto kleiner der Schaden bei einem Leck.

> `MOODLE_FUNCTION` nur setzen, wenn du wirklich eine andere Funktion brauchst.
> GitHub Actions setzt eine Variable bei `${{ vars.MOODLE_FUNCTION }}` auch dann,
> wenn sie gar nicht existiert — dann als **leere Zeichenkette**. Ein
> `os.environ.get('MOODLE_FUNCTION', DEFAULT)` greift die Vorgabe nur, wenn der
> Name *fehlt*, nicht wenn er leer ist. Das Ergebnis ist eine Endpunkt-URL ohne
> `wsfunction` und ein `Ungültiger Parameterwert` aus dem Moodle-Kern, das wie
> ein Payload-Fehler aussieht. pygrader50 fängt den Fall seit `v2.1.2` ab.

Der vorhandene `CLASSROOM50_SERVICE_TOKEN` wird für die Release-Bodies
weiterverwendet — er hat bereits Leserechte auf die Studi-Repos.

## Was übertragen wird

Je Kombination aus Aufgabe und Person geht die **neueste** Abgabe raus.

| Moodle-Feld | Quelle |
|---|---|
| `assignment_name` | Slug der Aufgabe aus `scores.json` |
| `user_name` | GitHub-Login der besitzenden Person |
| `points` / `max` | Punkte der neuesten Abgabe |
| `externallink` | URL des GitHub-Releases |
| `feedback` | Release-Text; davor ein Hinweis bei verspäteter Abgabe, dahinter der Link zur Abgabe |

## Zeitplan

| Job | Was er tut |
|---|---|
| `collect-scores` | sammelt alle Releases in `<CLASSROOM>/scores.json` |
| `moodle-sync` | überträgt daraus nach Moodle |

Zwischen beiden genug Abstand lassen, damit `collect-scores` sicher durch ist.

Ein Zustandsfile `<CLASSROOM>/moodle-state.json` merkt sich, was schon
übertragen wurde. Übersprungen wird nur, wenn Abgabe **und** Punktzahl identisch
sind — eine Nachbewertung derselben Abgabe geht also erneut raus.

## Von Hand auslösen

Im Config-Repo unter **Actions → Moodle Sync → Run workflow**. Eingaben:
Classroom, optional Aufgabe und Login, dazu die Schalter `dry_run` und `force`.
Bleibt der Classroom leer, laufen **alle** Ordner mit einer `scores.json`.

```bash
gh workflow run moodle-sync.yaml --repo <ORG>/classroom50 \
  -f classroom=<CLASSROOM> -f dry_run=true
```

Trockenlauf-Ausgabe:

```
Moodle-Übertrag: 2 Abgaben
[dry-run] <SLUG> / anna:  5/7
[dry-run] <SLUG> / bruno: 7/7
übertragen: 2 | unverändert: 0 | fehlgeschlagen: 0
```

> **Ein Trockenlauf baut nie einen Endpunkt.** Er prüft weder `MOODLE_URL` noch
> Token noch Funktionsnamen und beweist nur, welche Abgaben ausgewählt würden.
> Erst der erste echte Lauf zeigt, ob die Moodle-Seite stimmt.

## Lokal prüfen, ohne Zugangsdaten

```bash
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/scores.json \
   -H 'Accept: application/vnd.github.raw' > scores.json
GH_TOKEN=$(gh auth token) python -m pygrader50.moodle scores.json --dry-run
```

Alle Optionen: [CLI-Referenz](cli.md#python--m-pygrader50moodle-übertragen).

## Probleme

| Meldung / Symptom | Ursache |
|---|---|
| `No Moodle user found with username "X"` | Profilfeld leer oder falsch geschrieben |
| `No matching assignment found` | Aktivitätsname **oder** Kursmitgliedschaft passt nicht |
| `Ungültiger Parameterwert` | kommt aus dem Moodle-Kern, nicht aus dem Plugin — meist eine kaputte Endpunkt-URL, siehe `MOODLE_FUNCTION` oben |
| `keine XML-Antwort erhalten` | falsche `MOODLE_URL` oder ungültiger Token — Moodle liefert eine Login-Seite |
| Note kommt nicht an, Log sagt „unverändert" | Zustandsfile hält sie für erledigt — mit `force` erneut auslösen |
| Nachtlauf jede Nacht rot, immer dieselbe Person | Karteileichen-Eintrag in `scores.json`, siehe [Betrieb](betrieb.md#scoresjson-wird-nie-aufgeräumt) |

Die Plugin-eigenen Fehler (`no_user`, `no_assignment`, `overdue`) kommen als
**Warnungen im Ergebnis** zurück, nie als Exception. Eine Exception stammt
deshalb fast immer aus `validate_parameters()` im Moodle-Kern und meint die
Anfrage selbst, nicht ihren Inhalt.
