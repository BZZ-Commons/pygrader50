# Migration von GitHub Classroom

Was beim Umstieg einer bestehenden Klasse zu tun ist. Ein neuer Classroom von
Grund auf: [Einrichtung](einrichtung.md).

> Solange beide Wege parallel installiert sind, laufen bei **jedem Push zwei
> Autograder** nebeneinander — der alte scheitert dabei am Moodle-Aufruf. Die
> Migration ist erst mit Schritt 2 abgeschlossen.

## Was sich ändert

| | vorher | nachher |
|---|---|---|
| Bewertung ausgelöst von | `.github/workflows/classroom.yml` im Studi-Repo | zentralem `autograde-runner.yaml` |
| Bewertungs-Logik | GitHub-Classroom-Workflow | `pygrader50`, per Tag gepinnt |
| Moodle-Übertrag | direkt aus dem Studi-Repo | zentral aus dem Config-Repo |
| Moodle-Token | in der Org, per `secrets: inherit` überall lesbar | nur im Config-Repo |
| Zuordnung zu Moodle | GitHub-Login im Moodle-Profilfeld | **unverändert**, dasselbe Feld |
| Konfigurationsdateien | `.github/autograding/` | Bundle im Config-Repo, `.github/autograding/` bleibt Fallback |

Die drei Dateien `unittests.json`, `lint.json` und `pylintrc` behalten ihr
Format. Es ist **kein** Umschreiben der Aufgaben nötig.

## 1. Klassen-Default setzen

Erst wenn `<CLASSROOM>/autograder.py` im Config-Repo liegt, bewertet
Classroom 50 überhaupt etwas — vorher liefert es überall `0/0`.

Ablauf und Prüfungen: [Einrichtung, Schritt 2](einrichtung.md#2-klassen-default-setzen).

## 2. Alten Workflow entfernen

### 2.1 Was raus muss

`.github/workflows/classroom.yml`. Typischerweise stecken zwei Jobs darin:

| Job | Was damit passiert |
|---|---|
| `grading` | ruft den alten Bewertungs-Workflow — ersetzt durch Classroom 50 |
| `copy-issues` | läuft nur unter `if: contains(github.actor, 'classroom')`, also nur beim GitHub-Classroom-Bot; unter Classroom 50 feuert er nie |

Ein separates `copyissues.yml` mit `workflow_dispatch` macht dasselbe manuell.
Beim Löschen von `classroom.yml` geht also **keine Funktion verloren**.

### 2.2 Was bleiben muss

`.github/autograding/` mit `unittests.json`, `lint.json` und `pylintrc` — das
ist der Fallback, solange nicht jede Aufgabe ein Bundle im Config-Repo hat.

`requirements.txt` und Hilfsskripte stören die Bewertung nicht: pygrader50
installiert die Studi-Abhängigkeiten bewusst nicht. Für die lokale Arbeit der
Lernenden zählt die Datei trotzdem, deshalb hält sie ein eigenes Skript aktuell:

```bash
scripts/sync-template-pins.py <ORG> <CLASSROOM>            # Trockenlauf
scripts/sync-template-pins.py <ORG> <CLASSROOM> --apply    # schreiben
```

Es hebt die Werkzeug-Pins und legt `.python-version` an. Alles andere bleibt
Zeile für Zeile erhalten — Pakete, welche die Lernenden im Rahmen der Aufgabe
selbst eintragen sollen, gehören nicht in die Pin-Liste.

> `pytest-asyncio` muss mit `pytest` mitziehen: alte Versionen und pytest 9
> lassen sich nicht gemeinsam auflösen.

### 2.3 Die Zielliste richtig bilden

> **Nicht** die Repos der Template-Organisation auflisten. Dort liegen oft auch
> Templates von Modulen, die noch auf dem alten Pfad laufen — ihnen den Workflow
> zu nehmen, stoppt dort **still** die Bewertung.

Massgeblich ist der `template`-Block in `<CLASSROOM>/assignments.json`:

```bash
gh api repos/<ORG>/classroom50/contents/<CLASSROOM>/assignments.json \
   -H 'Accept: application/vnd.github.raw' \
  | jq -r '.assignments[] | "\(.template.owner)/\(.template.repo)"' | sort -u
```

### 2.4 Ausführen

```bash
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM>            # Trockenlauf
scripts/remove-legacy-classroom-yml.sh <ORG> <CLASSROOM> --apply    # löschen
```

Das Skript nimmt die Liste aus 2.3 und ergänzt die bereits angenommenen
Studi-Repos. Es ist wiederholbar; fehlende Dateien meldet es als `absent`.

**Template-Änderungen erreichen bestehende Repos nicht.** Ein Studi-Repo trägt
seine Kopie aus dem Moment der Annahme — deshalb behandelt das Skript beide
Seiten. Umgekehrt sind Repos früherer Klassen, die dasselbe Template benutzt
haben, von der Template-Änderung nicht betroffen.

## 3. Alten Moodle-Token entwerten

> **Sicherheitsrelevant.** Der alte Workflow reichte den Moodle-Token per
> `secrets: inherit` an den Bewertungs-Workflow weiter. Jede Person mit
> Schreibrecht auf ein Studi-Repo konnte ihn mit drei Zeilen auslesen — und der
> Token kann Noten für beliebige Personen setzen.

1. Secret in **allen** betroffenen Organisationen löschen — typischerweise die
   Studi-Org *und* die Template-Org. Auf Namensvarianten achten, es gibt oft
   mehrere.
2. Den Token **in Moodle neu erzeugen und den alten invalidieren.** Löschen
   allein beendet nur die künftige Exposition, nicht die vergangene.

```bash
gh secret list --org <ORG>
```

## 4. Moodle-Seite umstellen

Hier ändert sich **nichts**: Die Lernenden tragen ihren GitHub-Login weiterhin
in dasselbe Moodle-Profilfeld ein. Das Plugin liest ausschliesslich dieses Feld;
der Moodle-Benutzername spielt keine Rolle. Einzelheiten unter
[Moodle](moodle.md#die-zuordnung-läuft-über-ein-profilfeld).

Vor dem ersten echten Übertrag prüfen, ob das Feld bei allen Teilnehmenden
gefüllt und richtig geschrieben ist. Ein leeres Feld pro Person genügt, um den
Nachtlauf rot zu färben.

## 5. Prüfen, dass wirklich umgestellt ist

- In einem Studi-Repo pushen: Es startet **genau ein** Bewertungslauf.
- Das Release zeigt eine echte Punktzahl, nicht `0/0`.
- `gh secret list --org <ORG>` listet keinen Moodle-Token mehr.
- Ein `moodle-sync`-Lauf ohne `dry_run` trägt die erwarteten Noten ein.

## Templates aus der alten Zeit aufräumen

Ein Template, das aus der GitHub-Classroom-Zeit stammt, trägt oft mehr mit sich
als nötig. Was hineingehört und was nicht:

| Datei | |
|---|---|
| `.github/workflows/classroom.yml` | **weg** — ruft den alten Workflow, reicht Secrets durch |
| `.github/autograding/` | bleibt — Fallback für die Bewertungs-Konfiguration |
| `requirements.txt` | bleibt, Pins hochziehen — für die lokale Arbeit der Lernenden |
| `.python-version` | ergänzen, passend zu `runtime.python` in `assignments.json` |
| Startcode, Tests | bleiben |

`.classroom50.yaml` und `.github/workflows/autograde-runner.yaml` legt
Classroom 50 beim Annehmen selbst an — beide gehören **nicht** ins Template.

Der vollständige Soll-Aufbau eines Templates: [Aufgaben-Template](template.md).
