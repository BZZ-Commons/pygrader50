# Dokumentation

pygrader50 bewertet Python-Abgaben für [Classroom 50](https://github.com/foundation50/classroom50)
mit **pytest** und **pylint** und überträgt die Punkte nach **Moodle**.

Diese Dokumentation beschreibt die Engine unabhängig von einer bestimmten Schule.
Wo ein Beispiel nötig ist, steht ein Platzhalter.

## Einstieg

| Rolle | Fang hier an |
|---|---|
| Du gibst Aufgaben ab | [Für Lernende](lernende.md) |
| Du betreust eine laufende Klasse | [Betrieb](betrieb.md) · [Fehlersuche](troubleshooting.md) |
| Du richtest eine neue Klasse ein | [Konzept](konzept.md) → [Einrichtung](einrichtung.md) |
| Du kommst von GitHub Classroom | [Migration](migration.md) |
| Du baust eine neue Aufgabe | [Aufgaben-Template](template.md) → [Bewertung](bewertung.md) |
| Du entwickelst an der Engine | [Konzept](konzept.md) · [CLI-Referenz](cli.md) |

## Alle Seiten

- **[Konzept](konzept.md)** — wie Classroom 50 die Engine aufruft, welche Repos beteiligt sind, woher die Konfiguration kommt
- **[Bewertung](bewertung.md)** — `unittests.json`, `lint.json`, `pylintrc`, wie Punkte entstehen
- **[Aufgaben-Template](template.md)** — was in ein Template-Repo gehört, was nicht, und wie eine neue Aufgabe daraus entsteht
- **[Einrichtung](einrichtung.md)** — einen Classroom von Grund auf anschliessen
- **[Betrieb](betrieb.md)** — Roster, Aufgaben, Abgabemodus, Nachbewerten, Betriebsfallen
- **[Moodle](moodle.md)** — Notenübertrag, Zugangsdaten, Zuordnung der Personen
- **[Migration](migration.md)** — Umstieg von GitHub Classroom
- **[CLI-Referenz](cli.md)** — alle Kommandos, Optionen, Umgebungsvariablen
- **[Für Lernende](lernende.md)** — Aufgabe annehmen, bearbeiten, abgeben
- **[Fehlersuche](troubleshooting.md)** — Symptom → Ursache

## Platzhalter

Die Beispiele verwenden durchgehend diese Platzhalter:

| Platzhalter | Bedeutung | Beispiel |
|---|---|---|
| `<ORG>` | GitHub-Organisation der Klasse | `informatik-2026` |
| `<CLASSROOM>` | Kurzname des Classrooms = Ordner im Config-Repo | `informatik-2026` |
| `<TEMPLATE-ORG>` | Organisation mit den Template-Repos | `templates-python` |
| `<SLUG>` | Slug einer Aufgabe | `lu04-a4-objektkommunikation` |
| `<LOGIN>` | GitHub-Login einer lernenden Person | `anna` |
| `<TAG>` | gepinnte pygrader50-Version | `v2.4.0` |

`<ORG>` und `<CLASSROOM>` sind oft gleich, müssen es aber nicht sein — der
Kurzname steht in `<CLASSROOM>/classroom.json`.

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **Config-Repo** | `<ORG>/classroom50` — Aufgaben, Roster, Autograder, Resultate, Workflows |
| **Studi-Repo** | `<ORG>/<CLASSROOM>-<SLUG>-<LOGIN>` — das Repository einer Person für eine Aufgabe |
| **Template-Repo** | Startcode und Tests einer Aufgabe, aus dem die Studi-Repos entstehen — siehe [Aufgaben-Template](template.md) |
| **Klassen-Default** | `<CLASSROOM>/autograder.py` im Config-Repo — gilt für alle Aufgaben ohne eigenen Autograder |
| **Bundle** | `<CLASSROOM>/autograders/<SLUG>/` — Bewertungs-Konfiguration je Aufgabe, für Lernende nicht editierbar |
| **Abgabe** | ein `submit/*`-Release im Studi-Repo, erzeugt von einem Bewertungslauf |
