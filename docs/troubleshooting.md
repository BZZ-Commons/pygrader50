# Fehlersuche

Symptom → Ursache. Ausführliche Erklärungen stehen auf den verlinkten Seiten.

## Für Lernende

| Symptom | Ursache / Abhilfe |
|---|---|
| Es startet kein Bewertungslauf | Enthält die Commit-Message `NOACTION` oder `CLASSROOM 50`, wird absichtlich übersprungen. Sonst im Reiter **Actions** nachsehen. |
| Release zeigt `0/0` | Für diese Aufgabe ist keine Bewertung hinterlegt. Kein Fehler auf deiner Seite — der Lehrperson melden. |
| Rotes Kreuz, aber alle Tests grün | Das Linting gab 0 Punkte. Zeile `Linting` im Release ansehen. |
| pylint meckert auf GitHub mehr als lokal | Die Bewertung benutzt eigene, festgelegte Versionen statt deiner `requirements.txt`. |
| Ein Test bricht mit Timeout ab | Endlosschleife oder wartende Eingabe (`input()`) im Code. Jeder Testfall hat ein eigenes Zeitlimit. |
| Note fehlt in Moodle | Übertrag läuft zeitgesteuert. Fehlt sie am Folgetag: meist steht der GitHub-Name nicht im Moodle-Profilfeld. |

## Einrichtung und Bewertung

| Symptom | Ursache |
|---|---|
| `gh teacher …`: `missing scopes` | `gh auth refresh -h github.com -s admin:org,read:org,repo,workflow` in einem **interaktiven** Terminal |
| Release zeigt `0/0`, `tests: []` | Kein Autograder aktiv — Klassen-Default fehlt, oder `publish-pages` lief noch nicht |
| Pages liefert 404 für `autograder.py` | Klassen-Segment vergessen: `…/classroom50/<CLASSROOM>/autograder.py` |
| Log: `no grading configuration found` | Weder Bundle noch `.github/autograding/` enthält `unittests.json` / `lint.json` |
| Commit-Status `error`, kein Release | Exit ≠ 0: `pip install` gescheitert (Netz, falscher Tag) oder Absturz — Traceback steht im Job-Log |
| Bundle wird ignoriert | Ordner enthält `autograder.py` oder `tests.json`, oder `publish-pages` lief nach dem Push nicht |
| Aufgabe hat plötzlich kein Linting mehr | Eine `tests.json` für diese Aufgabe verdrängt den Klassen-Default |
| Ein Test zählt nie Punkte, ohne Fehlermeldung | `function` in `unittests.json` trifft keine Testfunktion — Tippfehler ergibt still 0 Punkte |
| Lint-Punkte weichen von früher ab | Neuere pylint-Version prüft strenger als die alten Template-Pins |
| Lint gibt 0 Punkte | Bei wenigen Statements und einem `E…` wird die pylint-Note negativ und auf 0 geklemmt — korrekt, kein Defekt. Siehe [Bewertung](bewertung.md#startcode-lint-sauber-halten) |
| Zwei Bewertungsläufe pro Push | Die alte `classroom.yml` liegt noch im Repo, siehe [Migration](migration.md) |

## Einsammeln

| Symptom | Ursache |
|---|---|
| `collect-scores` rot, Punkte trotzdem da | `CLASSROOM50_SERVICE_TOKEN` ohne *Administration: Read and write* — **oder** ein vorübergehender 403. Erst wiederholen, siehe [Betrieb](betrieb.md#der-service-token-braucht-administration-rechte) |
| Eine Aufgabe fehlt komplett in `scores.json` | Der letzte Lauf war auf eine andere Aufgabe verengt. Verengte Läufe überspringen still |
| `gh teacher roster …` scheitert, Namen leer | Classroom hat noch `students.csv` statt `roster.csv` |
| Eine Lehrperson taucht in `scores.json` auf | Eingesammelt wird nach Teams, nicht nach Roster. Testrepo löschen **und** Eintrag entfernen |
| Eintrag einer abgemeldeten Person bleibt stehen | `scores.json` wird nie aufgeräumt — von Hand entfernen |

## Moodle

| Symptom | Ursache |
|---|---|
| `No Moodle user found with username "X"` | Profilfeld leer oder falsch geschrieben |
| `No matching assignment found` | Aktivitätsname **oder** Kursmitgliedschaft passt nicht. Nicht mit dem Lehrer-Account testen |
| `Ungültiger Parameterwert` | Aus dem Moodle-Kern, nicht aus dem Plugin — meist eine kaputte Endpunkt-URL, siehe [Moodle](moodle.md#zugangsdaten) |
| `keine XML-Antwort erhalten` | Falsche `MOODLE_URL` oder ungültiger Token — Moodle liefert eine Login-Seite |
| Noten kommen nicht an, Log sagt „unverändert" | Zustandsfile hält sie für erledigt — mit `force` erneut auslösen |
| Nachtlauf jede Nacht rot, immer dieselbe Person | Karteileichen-Eintrag in `scores.json` |
| Trockenlauf grün, echter Lauf fällt um | Ein Trockenlauf baut nie einen Endpunkt und prüft weder URL noch Token |

## Wo nachschauen

- **Ein Lauf** — Studi-Repo → Actions → der Bewertungsjob. Dort steht, welche
  Konfigurationsdateien gefunden wurden.
- **Eine Klasse** — `<CLASSROOM>/scores.json` im Config-Repo.
- **Der Übertrag** — Config-Repo → Actions → Moodle Sync.

```bash
# Was hat der letzte Sammellauf geschrieben?
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/scores.json \
   -H 'Accept: application/vnd.github.raw' | jq '.'

# Übertrag trocken nachspielen
GH_TOKEN=$(gh auth token) python -m pygrader50.moodle scores.json --dry-run
```
