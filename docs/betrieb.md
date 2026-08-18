# Betrieb

Der laufende Betrieb einer eingerichteten Klasse. Neu aufsetzen:
[Einrichtung](einrichtung.md).

## Werkzeug

Classroom 50 lässt sich auf zwei Wegen bedienen, beide schreiben in dasselbe
Config-Repo:

| Weg | Womit | Wofür |
|---|---|---|
| **Web-Oberfläche** | [classroom50.org](https://classroom50.org), Anmeldung mit dem GitHub-Konto | Aufgaben anlegen und ändern, Abgabemodus setzen, Roster pflegen, Punkte ansehen, überschreiben und als CSV ausgeben, nachbewerten |
| **CLI** | `gh teacher` | dasselbe, aber skriptbar — Massenänderungen über viele Aufgaben, Automatisierung, alles was hier in der Doku als Befehl steht |

Diese Seite zeigt durchgehend die CLI, weil ein Befehl kopierbar und
wiederholbar ist. Wo dieselbe Sache in der Oberfläche liegt, steht es dabei.
Für einen einzelnen Handgriff ist die Oberfläche meist schneller.

```bash
gh extension install foundation50/gh-teacher
gh auth refresh -h github.com -s admin:org,read:org,repo,workflow
```

Ohne `admin:org` bricht **jeder** `gh teacher`-Aufruf mit einer Scope-Meldung
ab. Der Refresh öffnet den Browser und braucht ein interaktives Terminal.

## Roster

Die Klassenliste liegt als `<CLASSROOM>/roster.csv` im Config-Repo, mit diesem
Header:

```
username,first_name,last_name,email,section,github_id,role
```

> Ältere Classrooms haben stattdessen eine `students.csv`. Damit scheitert jeder
> `gh teacher roster`-Befehl, und die Namen in `scores.json` bleiben leer. Datei
> umbenennen und die Spalte `role` ergänzen; eine Datei ohne sie wird zwar
> gelesen, liefert aber `""`.

**Das Roster steuert die Bewertung nicht** — es liefert Anzeigedaten. Wer
eingesammelt wird, entscheidet die Team-Mitgliedschaft, siehe unten.

## Aufgaben

Alle Aufgaben einer Klasse stehen in `<CLASSROOM>/assignments.json`. Ein Eintrag
verweist auf das Template-Repo, den Slug, optional den Abgabetermin und den zu
verwendenden Autograder.

```bash
gh teacher assignment list <ORG> <CLASSROOM>
```

Eine Aufgabe hinzufügen oder ändern — derselbe Aufruf, er ist ein Upsert:

```bash
gh teacher assignment add <ORG> <CLASSROOM> <SLUG> \
  --name "<SLUG>" --template <TEMPLATE-ORG>/<SLUG>@main --runtime runtime.json
```

Nach jeder Änderung läuft `publish-pages`; erst danach sieht der Runner sie.

Damit das Linting überall zur Note zählt, stehen alle Aufgaben auf
`"autograder": "default"` und tragen **keinen** `tests`-Block — Begründung unter
[Konzept](konzept.md#warum-nicht-die-deklarativen-tests-von-classroom-50).

## Abgabemodus: jeder Push oder nur `submit`-Tags

Pro Aufgabe steht, wann ein Bewertungslauf startet:

| Modus | Feld in `assignments.json` | Wann bewertet wird |
|---|---|---|
| **jeder Push** (Vorgabe) | Feld fehlt | jeder Push auf den Standardzweig, zusätzlich jeder `submit/*`-Tag |
| **nur Tag** | `"submission_mode": "tag"` | ausschliesslich ein `submit/*`-Tag; ein gewöhnlicher `git push` speichert nur |

Der Tag-Modus ist der Kostenhebel: bei grossen Klassen kostet nicht mehr jeder
Zwischenstand Actions-Minuten, sondern nur die bewusste Abgabe. Der Preis ist
ein zusätzlicher Schritt für die Lernenden, siehe
[Für Lernende](lernende.md#3-bearbeiten-und-abgeben).

Umstellen — in der Oberfläche beim Bearbeiten der Aufgabe, oder:

```bash
gh teacher assignment submission-mode <ORG> <CLASSROOM> <SLUG> --every-push
gh teacher assignment submission-mode <ORG> <CLASSROOM> <SLUG> --tag
gh teacher assignment submission-mode <ORG> <CLASSROOM> <SLUG> --tag --dry-run
```

**Der Modus steht nicht nur im Config-Repo, sondern in jedem Studi-Repo.** Der
Auslöser ist der `on:`-Block in `.github/workflows/autograde.yaml`, und GitHub
wertet ihn aus, bevor irgendein Job startet. Umschalten heisst deshalb: Feld
setzen **und** diese Datei in allen bestehenden Repos neu schreiben. Genau das
tut der Befehl — er geht die Klassenmitglieder durch, ist idempotent und
committet mit `[skip ci]`. Ein einzelnes Repo nachziehen: `--user <LOGIN>`.

Drei Dinge, die dabei regelmässig auffallen:

- **Die Lernenden müssen danach `git pull`.** Der Retrofit-Commit liegt in ihrem
  Repo; ein veralteter Klon kollidiert beim nächsten Push.
- **Wer den Modus nur im Config-Repo ändert, erzeugt zwei Generationen.** Vorher
  angenommene Repos behalten ihren alten Auslöser, neu angenommene bekommen den
  neuen. Symptom: ein Teil der Klasse wird bei jedem Push bewertet, der andere
  Teil hat null Runs, null Tags, null Releases — und niemand hat etwas falsch
  gemacht.
- **Aufgaben mit teacher-eigenem Autograder** rührt der Befehl nicht an. Dort
  den `on:`-Block selbst pflegen und mit `--update-shims=false` nur das Feld
  umlegen.

Nachbewerten nach einem Retrofit: siehe [Nachbewerten](#nachbewerten) — der
`[skip ci]`-Commit ist dabei eine Falle.

## Resultate einsehen

- **Pro Abgabe** — Release und Commit-Status im Studi-Repo.
- **Pro Klasse** — `<CLASSROOM>/scores.json`, nachts von `collect-scores` aktualisiert.
- **In Moodle** — nach dem Lauf von `moodle-sync`, siehe [Moodle](moodle.md).

```bash
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/scores.json \
   -H 'Accept: application/vnd.github.raw' | jq '.'
```

`collect-scores` lässt sich von Hand auslösen, wahlweise auf eine Klasse oder
eine Aufgabe verengt:

```bash
gh workflow run collect-scores.yaml --repo <ORG>/classroom50
```

> Eine gesetzte Eingabe `assignment` verengt den Lauf **still**: übersprungene
> Aufgaben erzeugen keine Logzeile. Wer eine Aufgabe in `scores.json` vermisst,
> prüft zuerst, ob der letzte Lauf verengt war.

## Nachbewerten

Eine Abgabe neu bewerten lassen: in der Oberfläche über *Regrade*, oder im
Studi-Repo unter **Actions** den Bewertungslauf erneut starten
(*Re-run all jobs*). Das erzeugt ein neues Release; der nächste Moodle-Lauf
überträgt die geänderte Punktzahl automatisch, weil sich die Punktzahl
unterscheidet.

Gibt es noch gar keinen Lauf — etwa weil die Aufgabe im Tag-Modus stand und
niemand abgegeben hat —, lässt sich ein Stand von aussen zur Bewertung bringen,
indem man den `submit/*`-Tag selbst setzt:

```bash
SHA=$(gh api repos/<ORG>/<CLASSROOM>-<SLUG>-<LOGIN>/git/ref/heads/main --jq '.object.sha')
gh api repos/<ORG>/<CLASSROOM>-<SLUG>-<LOGIN>/git/refs \
  -f ref="refs/tags/submit/$(date -u +%Y-%m-%dT%H-%M-%SZ)-${SHA:0:7}" -f sha="$SHA"
```

> **Falle:** zeigt der Tag auf einen Commit, dessen Message `[skip ci]` enthält
> — und genau das trifft auf den Retrofit-Commit von `submission-mode` zu —,
> passiert **nichts**. GitHub wertet `[skip ci]` am Head-Commit des
> Push-Ereignisses aus, auch bei einem Tag-Push. Dann den letzten echten Commit
> der Lernenden taggen statt `HEAD`. Dessen Baum darf ruhig noch den alten
> Auslöser enthalten: `tags: ["submit/*"]` steht in beiden Generationen.

Das schreibt eine echte Note: Release, Commit-Status, und über den Nachtlauf
Moodle. Für unfertige Zwischenstände also sparsam einsetzen.

Nur die Note in Moodle nachtragen, ohne neuen Bewertungslauf:

```bash
gh workflow run moodle-sync.yaml --repo <ORG>/classroom50 \
  -f classroom=<CLASSROOM> -f assignment=<SLUG> -f force=true
```

## Betriebsfallen

Vier Verhaltensweisen der Classroom-50-Seite, die man einmal wissen muss.

### `scores.json` wird nie aufgeräumt

Das Einsammeln ist ein reiner Upsert, geschlüsselt auf den Repo-Owner. Ein
Eintrag bleibt stehen, auch wenn das Repository gelöscht oder die Person
ausgetragen wurde. Da der Moodle-Übertrag mit Exit 1 endet, sobald **eine**
Übertragung scheitert, färbt ein einziger solcher Karteileichen-Eintrag den
Nachtlauf dauerhaft rot.

Nach einer Abmeldung den Eintrag von Hand aus `<CLASSROOM>/scores.json`
entfernen.

### Eingesammelt wird nach Teams, nicht nach Roster

Massgeblich ist die Union aus Studenten-Team **und allen Staff-Teams**
(`teacher`, `hta`, `ta`). Wer als Lehrperson eine Aufgabe annimmt, um den Ablauf
zu testen, wird bewusst wie eine lernende Person bewertet und landet in
`scores.json` — und damit im Moodle-Übertrag, wo der Account dann als
Kursteilnehmer fehlt.

Testrepos nach dem Test löschen **und** den Eintrag aus `scores.json` entfernen.

### Template-Änderungen erreichen bestehende Repos nicht

Ein Studi-Repo trägt seine Kopie aus dem Moment der Annahme. Eine Korrektur an
Punkten, Tests oder Startcode im Template wirkt nur auf **neu** angenommene
Repos. Wer bestehende mitziehen will, muss sie einzeln anfassen — oder die
Konfiguration ins Bundle im Config-Repo legen, das bei jedem Lauf neu geladen
wird.

### Der Service-Token braucht Administration-Rechte

`collect-scores` scheitert mit
`staff-team access grant failed with HTTP 403`, wenn dem
`CLASSROOM50_SERVICE_TOKEN` *Repository → Administration: Read and write* fehlt.
Die Punkte werden trotzdem gesammelt, der Job endet aber mit Exit 1 und die
Staff-Teams bekommen keinen Zugriff auf die Studi-Repos.

```bash
gh teacher rotate-service-token <ORG>
```

> Dieselbe Meldung erscheint auch bei einem **vorübergehenden** 403 — GitHub
> beantwortet Sekundär-Ratelimits ebenfalls mit 403, und der Sammler behandelt
> jeden 403 als harten Fehler und rät zur Token-Rotation. Bevor du einen
> funktionierenden Token wegwirfst: den Lauf wiederholen. Geht er durch, war es
> ein Ratelimit. Ein Lauf, der Rechte vergibt und Punkte sammelt, beweist, dass
> der Token ausreicht.

## Python-Version

Ohne Angabe von `runtime.python` in `assignments.json` wählt der Runner seine
eigene Vorgabe. Dort installieren sich aktuelle pytest- und pylint-Versionen —
die Lint-Punkte fallen strenger aus als mit alten Template-Pins. Besser
explizit setzen, damit eine Upstream-Änderung die Noten nicht verschiebt.
