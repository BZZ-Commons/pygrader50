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
2. Klicke den dort hinterlegten Link zum Annehmen.
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

> Die `requirements.txt` ist für **deine** lokale Arbeit da. Die Bewertung auf
> GitHub benutzt sie bewusst nicht, sondern eigene, festgelegte Versionen.
> Deshalb kann es vorkommen, dass pylint auf GitHub etwas strenger urteilt als
> bei dir lokal.

## 3. Bearbeiten und abgeben

Abgeben heisst: **pushen**. Es gibt keinen separaten Abgabeknopf.

```bash
git add .
git commit -m "Aufgabe gelöst"
git push
```

Jeder Push löst eine neue Bewertung aus. Du kannst beliebig oft pushen; gewertet
wird die letzte Abgabe vor dem Abgabetermin.

## 4. Resultat anschauen

Nach ein bis zwei Minuten stehen im Repository vier Dinge:

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
| Es läuft gar kein Bewertungslauf. | Enthält deine Commit-Message `NOACTION` oder `CLASSROOM 50`, wird der Lauf absichtlich übersprungen. Sonst: Reiter **Actions** prüfen. |
| Ein Test bricht mit Timeout ab. | Endlosschleife oder wartende Eingabe (`input()`) im Code. Jeder Testfall hat ein eigenes Zeitlimit. |
| pylint meckert auf GitHub mehr als bei mir. | Die Bewertung benutzt eigene, neuere Versionen statt deiner `requirements.txt`. |
| Ich habe nach dem Abgabetermin gepusht. | Die Abgabe wird trotzdem bewertet und als verspätet markiert. |
| Meine Note fehlt in Moodle. | Meist fehlt der GitHub-Name im Moodle-Profilfeld. Sonst der Lehrperson melden. |
