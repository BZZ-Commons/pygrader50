# DokuWiki-Quellen für wiki.bzz.ch

Die Dateien in diesem Ordner spiegeln die Struktur von DokuWikis `data/pages/`.
Pfad → Seiten-ID → URL ist 1:1: `howto/git/classroom50/start.txt` wird zu
`howto:git:classroom50:start` unter `https://wiki.bzz.ch/howto/git/classroom50/start`.

## Zuordnung

| Datei | Seiten-ID | Bearbeiten unter | Aktion |
|---|---|---|---|
| `howto/git/start.txt` | `howto:git:start` | https://wiki.bzz.ch/howto/git/start?do=edit | **ersetzen** (Navigation neu gegliedert) |
| `howto/git/classroom50repo.txt` | `howto:git:classroom50repo` | https://wiki.bzz.ch/howto/git/classroom50repo?do=edit | **ersetzen** (Inhalt war veraltet) |
| `howto/git/template.txt` | `howto:git:template` | https://wiki.bzz.ch/howto/git/template?do=edit | **neu** (war verlinkt, existierte nicht) |
| `howto/git/classroom50/start.txt` | `howto:git:classroom50:start` | https://wiki.bzz.ch/howto/git/classroom50/start?do=edit | neu |
| `howto/git/classroom50/lernende.txt` | `howto:git:classroom50:lernende` | https://wiki.bzz.ch/howto/git/classroom50/lernende?do=edit | neu |
| `howto/git/classroom50/lehrpersonen.txt` | `howto:git:classroom50:lehrpersonen` | https://wiki.bzz.ch/howto/git/classroom50/lehrpersonen?do=edit | neu |
| `howto/git/classroom50/bewertung.txt` | `howto:git:classroom50:bewertung` | https://wiki.bzz.ch/howto/git/classroom50/bewertung?do=edit | neu |
| `howto/git/classroom50/moodle.txt` | `howto:git:classroom50:moodle` | https://wiki.bzz.ch/howto/git/classroom50/moodle?do=edit | neu |
| `howto/git/classroom50/einrichtung.txt` | `howto:git:classroom50:einrichtung` | https://wiki.bzz.ch/howto/git/classroom50/einrichtung?do=edit | neu |
| `howto/git/classroom50/migration.txt` | `howto:git:classroom50:migration` | https://wiki.bzz.ch/howto/git/classroom50/migration?do=edit | neu |
| `howto/git/classroom50/troubleshooting.txt` | `howto:git:classroom50:troubleshooting` | https://wiki.bzz.ch/howto/git/classroom50/troubleshooting?do=edit | neu |
| `howto/git/classroom50/cli.txt` | `howto:git:classroom50:cli` | https://wiki.bzz.ch/howto/git/classroom50/cli?do=edit | neu |

## Reihenfolge beim Einspielen

1. Erst die neuen Seiten unter `howto:git:classroom50:` anlegen — sonst zeigt
   der überarbeitete Hub auf rote Links.
2. Dann `howto:git:template` und `howto:git:classroom50repo`.
3. Zuletzt `howto:git:start`.
4. Danach die Altseiten mit dem Banner unten versehen.

## Banner für die Altseiten

Oben in `howto:git:grading:autograding2`, `howto:git:grading:linter`,
`howto:git:grading:automatic_grading` und `howto:git:grading:autograding`
einfügen — Inhalt sonst unverändert lassen:

```
<WRAP center round important 90%>
**Veraltet.** Diese Anleitung beschreibt den Ablauf über GitHub Classroom und
''BZZ-Commons/pygrader''. Seit August 2026 läuft die Bewertung an der BZZ über
[[howto:git:classroom50:start|Classroom 50]]. Diese Seite bleibt nur als Archiv
für noch nicht migrierte Module stehen.
</WRAP>
```

## Nach dem Einspielen prüfen

- `https://wiki.bzz.ch/howto/git/start` — keine roten Links mehr
- Suche nach `pygrader` im Wiki: Treffer ausserhalb der Archivseiten prüfen
- `howto:git:github_moodle` bleibt gültig und wird aus den Classroom-50-Seiten
  verlinkt — das Moodle-Profilfeld *GitHub Classroom* ist weiterhin die
  einzige Zuordnung zwischen Moodle-Konto und GitHub-Login

## Quellen

Der Inhalt ist aus `README.md`, `SETUP.md` und `CLI.md` dieses Repos abgeleitet.
Ändert sich dort etwas, hier nachziehen.
