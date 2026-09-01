# Für Lernende: Aufgabe annehmen, bearbeiten, abgeben

## Voraussetzungen

1. Ein GitHub-Konto, das deine Schule kennt.
2. **Dein GitHub-Benutzername steht in deinem Moodle-Profil**, in dem Feld, das
   deine Lehrperson dafür nennt. Fehlt er oder ist er falsch geschrieben, wird
   deine Abgabe zwar bewertet, die Note kommt aber nicht in Moodle an.

> Moodle findet dich **nur** über dieses Profilfeld — dein Moodle-Benutzername
> spielt für die Zuordnung keine Rolle. Trage den GitHub-Namen zeichengenau ein,
> bevor du die erste Aufgabe abgibst.

## 1. Aufgabe annehmen

1. Öffne in Moodle die Aktivität der Aufgabe (Typ *External Assignment*).
2. Klicke den dort hinterlegten Link zum Annehmen. Er führt auf die
   Classroom-50-Oberfläche ([classroom50.org](https://classroom50.org)), wo du
   dich mit deinem GitHub-Konto anmeldest und die Aufgabe annimmst.
3. GitHub erstellt dir ein privates Repository in der Organisation der Klasse.

Das Repository enthält den Startcode aus dem Template. Die Tests der Lehrperson
sind bereits hinterlegt.

## 2. Repository klonen und einrichten

```bash
git clone https://github.com/<ORG>/<CLASSROOM>-<SLUG>-<DEIN-LOGIN>.git
cd <CLASSROOM>-<SLUG>-<DEIN-LOGIN>
```

Danach eine virtuelle Umgebung anlegen und die Abhängigkeiten installieren:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> Die `requirements.txt` ist für **deine** lokale Arbeit da — und die Bewertung
> auf GitHub installiert dieselben Zusatzpakete daraus. Die Zeilen für `pytest`
> und `pylint` überspringt sie: dort benutzt sie eigene, festgelegte Versionen.
> Deshalb kann es vorkommen, dass pylint auf GitHub etwas strenger urteilt als
> bei dir lokal.

## 3. Bearbeiten und abgeben

Wann eine Bewertung startet, legt deine Lehrperson **pro Aufgabe** fest. Es gibt
zwei Möglichkeiten:

| Modus | Was bewertet wird |
|---|---|
| **jeder Push** (der übliche Fall) | jeder `git push` löst eine Bewertung aus |
| **nur auf Abgabe** | ein Push speichert nur; bewertet wird erst, wenn du abgibst |

Woran du erkennst, welcher gilt: öffne in deinem Repository die Datei
`.github/workflows/autograde.yaml` und schau auf den `on:`-Block.

```yaml
on:
  push:
    branches: ["main"]      # steht diese Zeile da, wird jeder Push bewertet
    tags: ["submit/*"]      # steht nur diese Zeile da, musst du abgeben
```

### Modus «jeder Push»

```bash
git add .
git commit -m "Aufgabe gelöst"
git push
```

Jeder Push löst eine neue Bewertung aus. Du kannst beliebig oft pushen; gewertet
wird die letzte Abgabe vor dem Abgabetermin.

### Modus «nur auf Abgabe»

Zuerst wie gewohnt arbeiten und pushen — das sichert deinen Stand, bewertet ihn
aber nicht. Zum Abgeben dann einer der beiden Wege:

```bash
# bequem, mit der Erweiterung gh student
gh extension install foundation50/gh-student
gh student submit
```

```bash
# ohne Erweiterung, von Hand: ein Tag, der mit submit/ beginnt
git push                                # zuerst den Stand hochladen
git tag submit/abgabe-1
git push origin submit/abgabe-1
```

Der Name nach `submit/` ist frei wählbar, muss aber pro Abgabe **neu** sein —
ein Tag lässt sich nicht zweimal vergeben. Du kannst also mehrmals abgeben,
etwa `submit/abgabe-1`, `submit/abgabe-2`.

> Vergiss den `git push` **vor** dem Tag nicht. Der Tag zeigt auf einen Commit;
> ist der noch nicht auf GitHub, wird nichts bewertet.

## 4. Resultat anschauen

In der Classroom-50-Oberfläche findest du dein Ergebnis über die Aufgabe unter
*My submission* → *View grade*. Dasselbe steht nach ein bis zwei Minuten auch
direkt im Repository, an vier Stellen:

| Ort | Was du dort siehst |
|---|---|
| Häkchen / Kreuz neben dem Commit | Kurzfassung, z. B. `classroom50/autograde: 5/7 (2/3 tests passed)` |
| Reiter **Actions** | das vollständige Log des Bewertungslaufs |
| Reiter **Releases** | ein Release pro Abgabe mit der Feedback-Tabelle |
| Pull Request *Feedback* | dasselbe Feedback als Kommentar |

Die Feedback-Tabelle sieht so aus:

```
### classroom50 autograde: 5/7

## Unittests
| name     | feedback        | expected | actual | points | max |
| -------- | --------------- | -------- | ------ | ------ | --- |
| test_ggt | Assertion Error | 8        | None   | 0      | 2   |

**0.00/2.00 Points (0.00%)**
```

- **expected** ist der von den Tests erwartete Wert, **actual** dein tatsächlicher.
- Ein Eintrag **Linting** bewertet den Stil deines Codes. Punkte gibt es
  anteilig zur pylint-Note.
- Ein rotes Kreuz beim Commit heisst: mindestens ein Test ist gescheitert
  **oder** das Linting gab 0 Punkte.

## 5. Note in Moodle

Die Punkte werden zeitgesteuert nach Moodle übertragen, in der Regel nachts.
Wenn du am Abend pushst, steht die Note am nächsten Morgen in Moodle. Braucht
die Lehrperson die Noten früher, kann sie den Übertrag von Hand auslösen.

Verspätete Abgaben werden übertragen und im Feedback als solche gekennzeichnet.

## Häufige Fragen

| Frage | Antwort |
|---|---|
| Ich sehe `0/0` statt Punkten. | Für diese Aufgabe ist (noch) keine Bewertung hinterlegt. Kein Fehler deinerseits — der Lehrperson melden. |
| Das Häkchen ist rot, obwohl alle Tests grün sind. | Dann kostet das Linting die Punkte. Schau in die Zeile `Linting` im Release. |
| Es läuft gar kein Bewertungslauf. | Zuerst prüfen, ob die Aufgabe im Modus «nur auf Abgabe» steht — dann fehlt der `submit/`-Tag, siehe Schritt 3. Sonst: enthält deine Commit-Message `NOACTION`, `CLASSROOM 50` oder `[skip ci]`, wird der Lauf absichtlich übersprungen. Sonst: Reiter **Actions** prüfen. |
| Ich habe abgegeben, aber es lief nichts. | Der Tag muss mit `submit/` beginnen und auf einen Commit zeigen, der schon auf GitHub liegt. Also `git push` vor `git push origin <tag>`. |
| Beim Pushen kommt ein Konflikt, den ich nicht verursacht habe. | Deine Lehrperson hat den Abgabemodus umgestellt; dabei kam ein Commit in dein Repository. Einmal `git pull`, dann geht es weiter. |
| Ein Test bricht mit Timeout ab. | Endlosschleife oder wartende Eingabe (`input()`) im Code. Jeder Testfall hat ein eigenes Zeitlimit. |
| pylint meckert auf GitHub mehr als bei mir. | Für pytest und pylint benutzt die Bewertung eigene, neuere Versionen; die Zeilen dazu in deiner `requirements.txt` werden übersprungen. |
| `ModuleNotFoundError` für ein Paket, das lokal da ist. | Das Paket fehlt in `requirements.txt` — oder die Installation im Lauf ist gescheitert. Im **Actions**-Log steht dann `requirements.txt: install failed`. |
| Ich habe nach dem Abgabetermin gepusht. | Die Abgabe wird trotzdem bewertet und als verspätet markiert. |
| Meine Note fehlt in Moodle. | Meist fehlt der GitHub-Name im Moodle-Profilfeld. Sonst der Lehrperson melden. |
