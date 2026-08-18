# Beispiel-Repos für die Bewertungs-Engine

Achtzehn Studi-Abgaben, wie sie wirklich vorkommen: gelöst, halb gelöst, mit
Tippfehler im Funktionsnamen, mit Syntaxfehler, mit leerer Datei, mit
`print()`-Ausgaben. `tests/test_fixture_corpus.py` bewertet jede davon mit der
echten Engine und vergleicht Zelle für Zelle mit `expected.json`.

Der Zweck ist nicht, Punkte zu prüfen — das tun die anderen Tests. Der Zweck
ist der **Text**, den die Lernenden lesen. Eine Änderung an der Engine, die eine
Rückmeldung verschlechtert, fällt hier auf, bevor sie eine Klasse trifft.

## Herkunft

Die Fixtures stammen aus dem Python-Grader von GitHub Classroom,
[classroom-resources/autograding-python-grader](https://github.com/classroom-resources/autograding-python-grader/tree/main/test),
MIT-Lizenz, Copyright (c) 2023 GitHub. Übernommen sind die Lösungs- und
Testdateien.

Angepasst an unser Setup:

- Die `results.json` von dort (Schema `version 3`) ist durch `expected.json` in
  unserem Format ersetzt — eine Zeile pro Fall mit `feedback`, `expected`,
  `actual`, `points`.
- Die `.meta/config.json`-Ordner sind entfallen; unsere Aufgaben werden über
  `unittests.json` konfiguriert, nicht über Exercism-Metadaten.
- Den beiden `lasagna`-Fixtures wurden Testfunktionen angehängt. Im Original
  bricht die Datei nach dem `raise ImportError` ab; unsere Engine bewertet
  benannte Funktionen, und eine echte Aufgabe deklariert welche. Ausgeführt
  werden sie nie — der Import scheitert vorher, und genau das prüft das Fixture.

## Erwartungen ändern

```
python scripts/refresh-fixture-expectations.py --check      # was ist gedriftet?
python scripts/refresh-fixture-expectations.py [fixture]    # neu aufzeichnen
```

Neu aufzeichnen heisst: der Diff wurde gelesen und der neue Wortlaut ist der
bessere. Genau dafür liegt der Korpus hier.

Eine einzelne Zelle kann statt eines Literals `{"contains": [...]}` enthalten
und wird dann nie überschrieben. Das brauchen nur die zwei Fixtures, deren
Rückmeldung eine Meldung von CPython selbst zitiert (`SyntaxError`,
`ImportError`): deren Wortlaut kann zwischen den Python-Versionen der CI-Matrix
abweichen, darum stehen dort die Bestandteile, die die Aussage tragen. Alles
andere an diesen Fixtures — Punkte, Fallliste, die übrigen Spalten — wird ganz
normal mitgeneriert.
