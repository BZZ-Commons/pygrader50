"""Übertrag der Classroom-50-Punkte nach Moodle.

Läuft NICHT im Studi-Repo, sondern im `classroom50`-Config-Repo — der
Moodle-Token darf nicht in einem Repository liegen, in das Studierende pushen
können. Quelle ist `<classroom>/scores.json`, das `collect-scores` dort ohnehin
schon pflegt.

Der Scope — welche Classrooms angefasst werden — wird **fail-closed** aufgelöst
und muss ausgesprochen werden. Ein fehlendes oder leeres Argument ist ein
Abbruch, nicht »alle«: in GitHub Actions kommt eine nicht ausgefüllte Eingabe
als leerer String an, ununterscheidbar von einer bewusst geleerten. Der weiteste
Radius darf deshalb nicht der Vorgabezustand sein. Der Übertrag schreibt in eine
fremde Moodle-Instanz und setzt dabei eine dort von Hand korrigierte Note
zurück; das nimmt kein zweiter Lauf zurück.

    python -m pygrader50.moodle --classroom m323-ix24 --dry-run
    python -m pygrader50.moodle --classroom m323-ix24 --classroom m450-ix25
    python -m pygrader50.moodle --all-classrooms

Gearbeitet wird immer gegen ein Config-Repo (`--config-repo`, Vorgabe `.`), nie
gegen eine einzeln benannte Datei: sonst gäbe es zwei Antworten auf die Frage,
was ein Classroom ist, und nur eine davon ginge durch `resolve_scope`.

`--assignment` und `--user` dürfen weiter »leer = alle« bedeuten. Sie verengen
*innerhalb* des gewählten Classrooms; ihr weitester Fall ist durch die äussere
Grenze schon gedeckt. Die Regel gilt nur für die äusserste Scope-Dimension —
die, die bestimmt, wessen Daten überhaupt angefasst werden.

Umgebung:
    MOODLE_URL       Basis-URL der Moodle-Instanz
    MOODLE_TOKEN     Webservice-Token
    MOODLE_FUNCTION  Webservice-Funktion (Vorgabe: mod_externalassignment_update_grade)
    GH_TOKEN         optional, für den Feedback-Text aus dem Release

Je (Assignment, Owner) wird die neueste Abgabe übertragen. Ein Zustandsfile
merkt sich, was bereits übermittelt wurde, damit ein zweiter Lauf nur noch
Änderungen schickt; `--force` ignoriert es.

Übertragen wird der **exakte** Punktestand, nicht die ganze Zahl aus
`scores.json`. Die kommt aus `result.json`, und dort verlangt Classroom 50
`int` — der Lint-Anteil bringt aber Nachkommastellen mit, und Moodle nimmt sie
(`points` und `max` sind im Plugin `PARAM_FLOAT`). Der exakte Wert steht in der
`_Exakt:`-Zeile des Release-Texts, den dieses Modul für das Feedback ohnehin
holt; `exact_points` liest ihn dort heraus. Fehlt die Zeile, ist die ganze Zahl
bereits exakt.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import render
from .console import (error as console_error, fail, info, ok as console_ok, section,
                      step_summary, warn)

DEFAULT_FUNCTION = 'mod_externalassignment_update_grade'
STATE_SCHEMA = 'pygrader50/moodle-state/v1'
SCORES_SCHEMA = 'classroom50/scores/v1'

# Dateinamen, die `collect-scores` im Config-Repo je Classroom-Ordner anlegt.
SCORES_FILENAME = 'scores.json'
STATE_FILENAME = 'moodle-state.json'

# Die Zeile, die `render.release_body` schreibt, sobald der Punktestand
# bruchwertig ist. Der Wortlaut ist damit eine Schnittstelle und kein blosser
# Prosatext; `test_moodle.py` hält ihn über einen Round-Trip gegen `render` fest.
EXACT_PATTERN = re.compile(
    r'_Exakt:\s*(?P<points>\d+(?:\.\d+)?)\s*/\s*(?P<max>\d+(?:\.\d+)?)\s*Punkte'
)

# So lange wird eine Drosselung ausgesessen. Darüber lohnt das Warten nicht:
# die primäre Grenze gibt erst zur vollen Stunde wieder frei, und einen
# Actions-Job so lange leer laufen zu lassen ist teurer als ein zweiter Lauf.
MAX_THROTTLE_WAIT = 120


@dataclass(frozen=True)
class Submission:  # pylint: disable=too-many-instance-attributes
    """Die eine Abgabe, deren Punkte nach Moodle gehen."""

    assignment: str
    owner: str
    score: int
    max_score: int
    submission: str
    release_url: str
    submitted_at: str
    late: bool

    @property
    def key(self) -> str:
        """Stabiler Schlüssel für das Zustandsfile."""
        return f'{self.assignment}/{self.owner}'

    @property
    def repository(self) -> str:
        """`owner/repo` der Abgabe, aus der Release-URL abgeleitet."""
        return repository_from_url(self.release_url)


@dataclass
class State:
    """Was bereits nach Moodle übertragen wurde."""

    path: pathlib.Path | None = None
    entries: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: pathlib.Path | None) -> 'State':
        """Zustand einlesen; fehlend oder kaputt heisst: alles neu übertragen."""
        if path is None or not path.is_file():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding='UTF-8'))
        except ValueError:
            warn(f'{path} ist unlesbar — es wird alles neu übertragen')
            return cls(path=path)
        return cls(path=path, entries=data.get('entries') or {})

    def is_current(self, submission: Submission) -> bool:
        """True, wenn genau diese Abgabe mit dieser Punktzahl schon übertragen wurde.

        Verglichen wird bewusst die **ganze** Zahl aus `scores.json`, nicht der
        exakte Wert: `scores.json` kennt den exakten gar nicht, und ein
        Vergleich »gespeichert 6.44 == score 6« schlüge jede Nacht fehl und
        sendete dieselbe Note endlos neu.
        """
        previous = self.entries.get(submission.key)
        return bool(
            previous
            and previous.get('submission') == submission.submission
            and previous.get('score') == submission.score
        )

    def has_exact(self, submission: Submission) -> bool:
        """True, wenn der Eintrag von einer Version stammt, die exakt überträgt."""
        return 'points' in (self.entries.get(submission.key) or {})

    def sent_points(self, submission: Submission):
        """Der Wert, der zuletzt wirklich nach Moodle ging.

        Vor dieser Version war das die ganze Zahl, und genau die steht in einem
        Alteintrag unter `score`.
        """
        previous = self.entries.get(submission.key) or {}
        return previous.get('points', previous.get('score'))

    def record(self, submission: Submission, points=None) -> None:
        """Erfolgreiche Übertragung vermerken.

        `points=None` heisst »es ging die gerundete Zahl raus, der exakte Wert
        war nicht zu ermitteln«. Der Eintrag bleibt dann ohne `points`, und ein
        späterer `--backfill` kommt auf ihn zurück — genau wie auf einen
        Eintrag aus der Zeit vor dem exakten Übertrag.
        """
        entry = {
            'submission': submission.submission,
            'score': submission.score,
            'max-score': submission.max_score,
        }
        if points is not None:
            entry['points'] = points
        self.entries[submission.key] = entry

    def save(self) -> None:
        """Zustand zurückschreiben (No-op ohne Pfad)."""
        if self.path is None:
            return
        payload = {'schema': STATE_SCHEMA, 'entries': dict(sorted(self.entries.items()))}
        self.path.write_text(json.dumps(payload, indent=2) + '\n', encoding='UTF-8')


def repository_from_url(url: str) -> str:
    """`https://github.com/org/repo/commit/abc` → `org/repo`."""
    parts = urllib.parse.urlparse(url or '').path.strip('/').split('/')
    return '/'.join(parts[:2]) if len(parts) >= 2 else ''


def latest_submissions(scores: dict, *, assignment: str | None = None,
                       owner: str | None = None) -> list[Submission]:
    """Je (Assignment, Owner) die neueste Abgabe aus scores.json."""
    if scores.get('schema') != SCORES_SCHEMA:
        raise ValueError(
            f'scores.json hat schema {scores.get("schema")!r}, erwartet {SCORES_SCHEMA!r}'
        )

    found: list[Submission] = []
    for slug, block in sorted((scores.get('assignments') or {}).items()):
        if assignment and slug != assignment:
            continue
        for entry in block.get('entries') or []:
            if owner and (entry.get('owner') or '').lower() != owner.lower():
                continue
            submissions = [s for s in entry.get('submissions') or [] if isinstance(s, dict)]
            if not submissions:
                continue
            newest = max(
                submissions,
                key=lambda item: (item.get('datetime') or '', item.get('graded_at') or ''),
            )
            found.append(
                Submission(
                    assignment=slug,
                    owner=entry.get('owner') or newest.get('owner') or '',
                    score=int(newest.get('score') or 0),
                    max_score=int(newest.get('max-score') or 0),
                    submission=newest.get('submission') or '',
                    release_url=newest.get('release') or newest.get('commit') or '',
                    submitted_at=newest.get('datetime') or '',
                    late=bool(newest.get('late')),
                )
            )
    return found


class RateLimited(RuntimeError):
    """GitHub drosselt; für diesen Lauf ist das Kontingent aufgebraucht."""


def throttle_wait(error: urllib.error.HTTPError) -> int | None:
    """Sekunden bis zum nächsten Versuch, oder `None` bei einem echten 403.

    GitHub meldet beides mit demselben Statuscode: das aufgebrauchte Kontingent
    und die fehlende Berechtigung. Unterscheiden lässt sich das nur an den
    Kopfzeilen — die primäre Grenze setzt `X-RateLimit-Remaining: 0`, die
    sekundäre schickt `Retry-After`.
    """
    if error.code not in (403, 429):
        return None
    retry_after = (error.headers.get('Retry-After') or '').strip()
    if retry_after.isdigit():
        return int(retry_after)
    if (error.headers.get('X-RateLimit-Remaining') or '').strip() == '0':
        reset = (error.headers.get('X-RateLimit-Reset') or '').strip()
        if reset.isdigit():
            return max(int(reset) - int(time.time()), 0)
    return None


def release_feedback(submission: Submission, token: str | None, *, attempts: int = 3) -> str:
    """Den Markdown-Text des Releases holen — das Feedback, das pygrader50 schreibt.

    Bei einer kurzen Drosselung wird gewartet und erneut versucht. Ist das
    Kontingent ganz weg, fliegt `RateLimited`: ein Nachzug prüft tausende
    Releases, und ohne diese Bremse rennt er in die Grenze und brennt den Rest
    in Sekunden als »nicht abrufbar« ab.
    """
    if not (submission.repository and submission.submission):
        return ''
    tag = urllib.parse.quote(submission.submission, safe='')
    url = f'https://api.github.com/repos/{submission.repository}/releases/tags/{tag}'
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response).get('body') or ''
        except urllib.error.HTTPError as exc:
            wait = throttle_wait(exc)
            if wait is None:
                warn(f'{submission.key}: Feedback-Text nicht abrufbar ({exc})')
                return ''
            if wait > MAX_THROTTLE_WAIT or attempt == attempts:
                raise RateLimited(
                    f'GitHub drosselt und gibt erst in {wait}s wieder frei'
                ) from exc
            info(f'GitHub drosselt — {wait}s warten (Versuch {attempt}/{attempts})')
            time.sleep(wait)
        # `OSError` statt der einzelnen Typen: `URLError` ist selbst ein
        # OSError-Kind, `TimeoutError` und `RemoteDisconnected` aber nicht — und
        # über die tausenden Abrufe eines Nachzugs ist ein Aussetzer sicher.
        # Der Feedback-Text ist Beiwerk; er darf nie einen Lauf abreissen.
        except (OSError, ValueError) as exc:
            warn(f'{submission.key}: Feedback-Text nicht abrufbar ({exc})')
            return ''
    return ''


def _plain(value: float):
    """Auf zwei Stellen runden, ganze Werte als `int`.

    Ohne das stünde in Moodle und im Log `9.0`, wo heute `9` steht — ein
    Unterschied ohne Unterschied, der jede Gegenprobe gegen den Vorstand
    verrauschen würde.
    """
    rounded = round(value, 2)
    return int(rounded) if rounded == int(rounded) else rounded


def exact_points(body: str) -> tuple | None:
    """Den exakten Punktestand aus dem Release-Text lesen; `None`, wenn keiner drinsteht.

    Kein Treffer heisst nicht »unbekannt«, sondern »die ganze Zahl ist bereits
    exakt«: `render.release_body` schreibt die Zeile nur, wenn gerundet wurde.
    """
    match = EXACT_PATTERN.search(body or '')
    if match is None:
        return None
    try:
        return _plain(float(match.group('points'))), _plain(float(match.group('max')))
    except ValueError:  # pragma: no cover - die Regex lässt nur Zahlen durch
        return None


def build_payload(submission: Submission, feedback: str, *,
                  points=None, max_points=None) -> dict:
    """Formularfelder für mod_externalassignment_update_grade.

    `points`/`max_points` tragen den exakten Stand aus dem Release-Text. Ohne
    sie gehen die ganzen Zahlen der Abgabe raus.
    """
    body = feedback
    if submission.late:
        body = '> ⏰ Abgabe nach dem Fälligkeitstermin.\n\n' + body
    if submission.release_url:
        body += f'\n\nAbgabe: {submission.release_url}\n'
    return {
        'assignment_name': submission.assignment,
        'user_name': submission.owner,
        'points': submission.score if points is None else points,
        'max': submission.max_score if max_points is None else max_points,
        'externallink': submission.release_url,
        # Wie in pygrader: der Text wird quotiert übertragen.
        'feedback': urllib.parse.quote(body),
    }


def parse_response(text: str) -> tuple[bool, str]:
    """Moodle-Antwort auswerten: (erfolgreich, Meldung)."""
    start = text.find('<?xml')
    if start == -1:
        return False, 'keine XML-Antwort erhalten'
    try:
        root = ET.fromstring(text[start:])
    except ET.ParseError as exc:
        return False, f'XML nicht lesbar: {exc}'

    name = root.find(".//KEY[@name='name']/VALUE")
    if name is not None and name.text and 'success' in name.text:
        return True, 'ok'

    message = root.find(".//KEY[@name='message']/VALUE")
    if message is None:
        message = root.find('.//MESSAGE')
    if message is not None and message.text:
        return False, _with_details(root, message.text.replace('\\n', '\n'))
    return False, ET.tostring(root, encoding='unicode')


def _with_details(root: ET.Element, message: str) -> str:
    """Append Moodle's ERRORCODE and DEBUGINFO to `message` when present.

    The localised MESSAGE alone ("Ungültiger Parameterwert") never says *which*
    field Moodle rejected. ERRORCODE is stable across languages and DEBUGINFO
    names the offending value — the only way to tell a bad `externallink` from a
    bad `feedback` without guessing. DEBUGINFO is absent unless the Moodle
    instance runs at developer debug level, hence both are optional.
    """
    for tag in ('ERRORCODE', 'DEBUGINFO'):
        found = root.find(f'.//{tag}')
        if found is not None and found.text:
            message += f' [{tag.lower()}: {found.text.strip()}]'
    return message


def post(endpoint: str, payload: dict, timeout: int = 30) -> tuple[bool, str]:
    """Payload an Moodle senden."""
    data = urllib.parse.urlencode(payload).encode('UTF-8')
    request = urllib.request.Request(endpoint, data=data, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_response(response.read().decode('UTF-8', errors='replace'))
    except urllib.error.HTTPError as exc:
        return False, f'HTTP {exc.code}'
    except urllib.error.URLError as exc:
        return False, str(exc.reason)


def endpoint_url(base_url: str, token: str, function: str) -> str:
    """Moodle-Webservice-Endpunkt inklusive Token und Funktion."""
    return (
        f'{base_url.rstrip("/")}/webservice/rest/server.php/'
        f'?wstoken={urllib.parse.quote(token, safe="")}'
        f'&wsfunction={urllib.parse.quote(function, safe="")}'
    )


def sync(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
    submissions: list[Submission], *, sender, feedback_provider, state: State,
    dry_run: bool = False, force: bool = False, backfill: bool = False,
) -> tuple[int, int, int]:
    """Überträgt die Abgaben; gibt (übertragen, übersprungen, fehlgeschlagen) zurück."""
    sent = skipped = failed = 0
    reasons: collections.Counter = collections.Counter()
    for index, submission in enumerate(submissions):
        label = f'{submission.assignment} / {submission.owner}'
        current = state.is_current(submission)
        # Nachzug: Einträge aus der Zeit vor dem exakten Übertrag tragen im
        # Zustand kein `points`. Nur die werden noch einmal angefasst — und auch
        # sie nur, wenn sich der Wert wirklich ändert (siehe unten).
        catching_up = backfill and current and not state.has_exact(submission)
        if current and not force and not catching_up:
            skipped += 1
            continue
        if not submission.owner:
            warn(f'{submission.assignment}: Abgabe ohne Owner übersprungen')
            failed += 1
            reasons['Abgabe ohne Owner'] += 1
            continue

        # Auch im Trockenlauf: sonst nähme er einen anderen Weg als der echte
        # und zeigte weiter die gerundete Zahl — er bewiese gerade das nicht,
        # wofür er gefahren wird.
        try:
            body = feedback_provider(submission)
        except RateLimited as exc:
            # Weiterlaufen hiesse, den Rest in Sekunden als »nicht abrufbar«
            # abzubrennen — genau das ist am 18.09.2026 passiert: 1310 Abgaben
            # in 65 Sekunden. Sie bleiben ohne `points` und damit offen; ein
            # späterer Lauf holt sie nach.
            remaining = len(submissions) - index
            console_error(
                f'{exc} — {remaining} Abgaben nicht geprüft. Später erneut laufen lassen; '
                'was schon nachgezogen ist, wird übersprungen.'
            )
            failed += remaining
            reasons['GitHub-Kontingent aufgebraucht'] += remaining
            break

        # Beim Nachzug heisst ein leerer Release-Text nicht »nichts zu runden«,
        # sondern »nicht abrufbar«. Ihn wie einen gelesenen zu behandeln,
        # vermerkte den Eintrag mit der gerundeten Zahl als erledigt — und kein
        # späterer Nachzug käme je wieder auf ihn zurück.
        if catching_up and not body:
            warn(f'{label}: Release-Text nicht abrufbar, bleibt für den nächsten Nachzug liegen')
            failed += 1
            reasons['Release-Text nicht abrufbar'] += 1
            continue

        points, maximum = exact_points(body) or (submission.score, submission.max_score)

        # Ein erneuter Versand desselben Werts überschriebe in Moodle eine
        # Handkorrektur, ohne dass die Note davon anders würde. Beim Nachzug
        # wird deshalb nur vermerkt, was sich nicht ändert.
        if catching_up and points == state.sent_points(submission):
            if not dry_run:
                state.record(submission, points)
            skipped += 1
            continue

        if dry_run:
            info(f'[dry-run] {label}: {points}/{maximum}')
            sent += 1
            continue

        payload = build_payload(submission, body, points=points, max_points=maximum)
        ok, message = sender(payload)
        if ok:
            # Ohne Release-Text ging die gerundete Zahl raus — dann bleibt der
            # Eintrag ohne `points` und ein Nachzug holt ihn später ein.
            state.record(submission, points if body else None)
            sent += 1
            console_ok(f'✅ {label}: {points}/{maximum}')
        else:
            failed += 1
            reasons[message.splitlines()[0] if message else 'ohne Meldung'] += 1
            fail(f'❌ {label}: {message}')
    _report_reasons(reasons)
    return sent, skipped, failed


def _report_reasons(reasons: collections.Counter) -> None:
    """Die Fehlschläge nach Ursache zusammenfassen.

    Bei tausenden Abgaben ist die Einzelzeile nicht mehr lesbar — und der
    Unterschied zwischen »Moodle hat abgelehnt« und »GitHub war nicht
    erreichbar« entscheidet, was als Nächstes zu tun ist.
    """
    if not reasons:
        return
    info('Fehlgeschlagen nach Ursache:')
    for reason, count in reasons.most_common():
        info(f'  {count:>5} × {reason}')


class ScopeError(RuntimeError):
    """Der Aufruf sagt nicht eindeutig, wessen Noten angefasst werden."""


class SetupError(RuntimeError):
    """Die Umgebung reicht für einen Übertrag nicht."""


@dataclass(frozen=True)
class Classroom:
    """Ein Classroom des Config-Repos samt seiner beiden Dateien."""

    name: str
    scores: pathlib.Path
    state: pathlib.Path


@dataclass(frozen=True)
class Options:
    """Was ein Classroom-Durchlauf von der Kommandozeile braucht.

    Kopiert die Felder, statt die `argparse.Namespace` weiterzureichen: `sync`
    kennt argparse nicht, und `sync_classroom` soll die Grenze nicht wieder
    einreissen — sonst ist der Durchlauf nur noch über `parse_args` prüfbar.
    """

    assignment: str | None = None
    user: str | None = None
    no_feedback: bool = False
    dry_run: bool = False
    force: bool = False
    backfill: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'Options':
        """Die Felder aus den geparsten Argumenten ziehen."""
        return cls(
            assignment=args.assignment,
            user=args.user,
            no_feedback=args.no_feedback,
            dry_run=args.dry_run,
            force=args.force,
            backfill=args.backfill,
        )


def discover_classrooms(config_repo: pathlib.Path) -> list[str]:
    """Namen aller Ordner der obersten Ebene mit einer `scores.json`."""
    if not config_repo.is_dir():
        return []
    return sorted(
        entry.name for entry in config_repo.iterdir()
        if not entry.name.startswith('.') and (entry / SCORES_FILENAME).is_file()
    )


def resolve_scope(config_repo: pathlib.Path, names: list[str] | None,
                  all_classrooms: bool) -> list[Classroom]:
    """Den Scope fail-closed auflösen.

    »Alle« bleibt möglich — der Nachtlauf braucht es. Es muss nur ausgesprochen
    werden und ist nicht mehr das, was Schweigen bedeutet.

    Ein leerer `--classroom`-Wert zählt dabei als nicht gesetzt: GitHub Actions
    liefert eine nicht ausgefüllte Eingabe als leeren String, und ohne diese
    Zeile wanderte die Lücke nur aus der Shell nach Python.

    Ein unbekanntes Classroom ist ein Fehler und kein leerer Treffer — ein
    Tippfehler darf nicht wie ein erfolgreicher Lauf aussehen. Ein vorhandenes
    Classroom ohne zu übertragende Noten bleibt dagegen ein normaler Lauf.
    """
    wanted = [name.strip() for name in names or []]
    if any(not name for name in wanted):
        raise ScopeError(
            '--classroom ist leer. Ein leerer Wert heisst nicht »alle« — '
            'für alle Classrooms --all-classrooms angeben.'
        )
    wanted = list(dict.fromkeys(wanted))

    if wanted and all_classrooms:
        raise ScopeError('--classroom und --all-classrooms schliessen sich aus.')
    if not wanted and not all_classrooms:
        raise ScopeError(
            'Scope fehlt: --classroom <NAME> (wiederholbar) oder --all-classrooms angeben. '
            'Es wurde nichts übertragen.'
        )

    available = discover_classrooms(config_repo)
    if all_classrooms:
        # Kein ScopeError: der Aufruf war richtig, das Repo ist nur noch nicht
        # so weit. Das war schon in der Bash-Schleife ein gewöhnlicher Fehler.
        if not available:
            raise SetupError(
                f'keine {SCORES_FILENAME} unter {config_repo} gefunden — lief Collect Scores schon?'
            )
        wanted = available
    else:
        # Zwei verschiedene Lagen, zwei verschiedene Exit-Codes: ein Name ohne
        # Ordner ist ein Tippfehler (falsch gerufen), ein Ordner ohne
        # scores.json ist derselbe Fall wie oben — richtig gerufen, Repo noch
        # nicht so weit. Beides als "unbekannt" zu melden log dreifach: falscher
        # Code, falsche Ursache, und "vorhanden: (keines)" für einen Ordner,
        # der sichtbar da ist.
        missing = [name for name in wanted if not (config_repo / name).is_dir()]
        if missing:
            raise ScopeError(
                f'unbekanntes Classroom: {", ".join(missing)} — '
                f'vorhanden: {", ".join(available) or "(keines)"}'
            )
        unready = [name for name in wanted if name not in available]
        if unready:
            raise SetupError(
                f'{", ".join(unready)}: noch keine {SCORES_FILENAME} — '
                'lief Collect Scores schon?'
            )

    return [
        Classroom(
            name=name,
            scores=config_repo / name / SCORES_FILENAME,
            state=config_repo / name / STATE_FILENAME,
        )
        for name in wanted
    ]


def announce_scope(classrooms: list[Classroom], *, dry_run: bool) -> None:
    """Den aufgelösten Scope als erste Zeile ausgeben und in die Job-Summary schreiben.

    Ein zu weiter Lauf soll oben im Log stehen und nicht erst in Moodle auffallen.
    Bewusst *vor* dem ersten Übertrag geschrieben: stirbt der Lauf mittendrin,
    steht der Scope trotzdem in der Zusammenfassung.
    """
    line = (
        f'Scope: {len(classrooms)} Classroom(s) — '
        f'{", ".join(room.name for room in classrooms)} | '
        f'{"Trockenlauf" if dry_run else "echter Übertrag"}'
    )
    info(line)
    step_summary(f'### Moodle-Übertrag\n\n{line}\n')


def summary_table(results: list[tuple[Classroom, tuple[int, int, int] | None]]) -> str:
    """Die Zähler je Classroom als Markdown-Tabelle."""
    return '\n' + render.table([
        {
            'Classroom': room.name,
            'übertragen': counts[0] if counts else '—',
            'unverändert': counts[1] if counts else '—',
            'fehlgeschlagen': counts[2] if counts else f'unlesbare {SCORES_FILENAME}',
        }
        for room, counts in results
    ])


def moodle_endpoint() -> str:
    """Endpunkt-URL für den Webservice aus der Umgebung."""
    base_url = os.environ.get('MOODLE_URL', '').strip()
    token = os.environ.get('MOODLE_TOKEN', '').strip()
    if not (base_url and token):
        raise SetupError('MOODLE_URL und MOODLE_TOKEN müssen gesetzt sein')
    # `or DEFAULT_FUNCTION`, nicht der Vorgabewert von .get(): GitHub Actions
    # setzt `MOODLE_FUNCTION: ${{ vars.MOODLE_FUNCTION }}` auch dann, wenn die
    # Variable nicht existiert — dann steht dort der leere String und .get()
    # liefert ihn statt der Vorgabe. Moodle antwortet auf ein leeres
    # `wsfunction` mit `invalidparameter` / "Missing function name".
    function = os.environ.get('MOODLE_FUNCTION', '').strip() or DEFAULT_FUNCTION
    return endpoint_url(base_url, token, function)


def sync_classroom(room: Classroom, *, options: Options, endpoint: str,
                   gh_token: str | None) -> tuple[int, int, int] | None:
    """Ein Classroom übertragen; `None`, wenn seine `scores.json` unbrauchbar ist.

    Ein gescheitertes Classroom darf die übrigen nicht verhindern — der
    Exit-Code wird in `main` zusammengefasst.
    """
    section(f'Classroom {room.name}')
    if not room.scores.is_file():
        console_error(f'{room.scores} nicht gefunden')
        return None
    # Bewusst breit gefangen, und über den ganzen Durchlauf statt nur über das
    # Einlesen: die Zusage ist »ein kaputtes Classroom stoppt die übrigen
    # nicht«, und die hält nur, wenn sie für *jeden* Fehler gilt. Eine Liste von
    # Ausnahmetypen übersieht immer einen — `{"assignments": {"slug": null}}`
    # in einer von Hand editierten scores.json wirft AttributeError, und der
    # riss vorher den ganzen --all-classrooms-Lauf ab. Die Bash-Schleife, die
    # das hier ersetzt, isolierte über getrennte Subprozesse besser.
    try:
        submissions = latest_submissions(
            json.loads(room.scores.read_text(encoding='UTF-8')),
            assignment=options.assignment,
            owner=options.user,
        )
        info(f'{len(submissions)} Abgaben')
        state = State.load(room.state)
        sent, skipped, failed = sync(
            submissions,
            sender=lambda payload: post(endpoint, payload),
            feedback_provider=(
                (lambda submission: '') if options.no_feedback
                else (lambda submission: release_feedback(submission, gh_token))
            ),
            state=state,
            dry_run=options.dry_run,
            force=options.force,
            backfill=options.backfill,
        )
        if not options.dry_run:
            state.save()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        console_error(f'{room.scores}: {type(exc).__name__}: {exc}')
        return None
    info(f'übertragen: {sent} | unverändert: {skipped} | fehlgeschlagen: {failed}')
    return sent, skipped, failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Kommandozeile lesen."""
    parser = argparse.ArgumentParser(
        prog='python -m pygrader50.moodle',
        description='Überträgt die Punkte aus scores.json nach Moodle.',
        epilog='Der Scope ist fail-closed: ohne --classroom oder --all-classrooms '
               'wird nichts übertragen.',
    )
    parser.add_argument('--config-repo', type=pathlib.Path, default=pathlib.Path('.'),
                        metavar='PFAD', help='Wurzel des Config-Repos (Vorgabe: .)')
    parser.add_argument('--classroom', action='append', metavar='NAME',
                        help='Classroom-Ordner im Config-Repo; wiederholbar')
    parser.add_argument('--all-classrooms', action='store_true',
                        help=f'alle Ordner mit einer {SCORES_FILENAME}')
    parser.add_argument('--assignment', help='nur dieses Assignment übertragen')
    parser.add_argument('--user', help='nur diesen GitHub-Login übertragen')
    parser.add_argument('--force', action='store_true',
                        help='auch unverändertes erneut übertragen')
    parser.add_argument('--backfill', action='store_true',
                        help='Abgaben, die vor dem exakten Übertrag übermittelt '
                             'wurden, auf den exakten Wert nachziehen')
    parser.add_argument('--dry-run', action='store_true',
                        help='nur anzeigen, nichts senden')
    parser.add_argument('--no-feedback', action='store_true',
                        help='ohne Feedback-Text aus dem Release')
    args = parser.parse_args(argv)
    # Der Nachzug lebt vom Release-Text. Ohne ihn vermerkte er jede Abgabe mit
    # der gerundeten Zahl als erledigt — und ein späterer, richtiger Nachzug
    # überspränge sie dann alle. Exit 2 wie bei jedem anderen Fehlaufruf.
    if args.backfill and args.no_feedback:
        parser.error('--backfill braucht den Release-Text und schliesst --no-feedback aus')
    return args


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstieg."""
    args = parse_args(argv)
    try:
        classrooms = resolve_scope(args.config_repo, args.classroom, args.all_classrooms)
        # Ein Trockenlauf baut nie einen Endpunkt und prüft deshalb weder URL
        # noch Token — er beweist nur, welche Abgaben ausgewählt würden.
        endpoint = '' if args.dry_run else moodle_endpoint()
    except ScopeError as exc:
        console_error(exc)
        return 2
    except SetupError as exc:
        console_error(exc)
        return 1

    announce_scope(classrooms, dry_run=args.dry_run)
    options = Options.from_args(args)
    gh_token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or None

    results = [
        (room, sync_classroom(room, options=options, endpoint=endpoint, gh_token=gh_token))
        for room in classrooms
    ]
    step_summary(summary_table(results))
    return 1 if any(counts is None or counts[2] for _, counts in results) else 0


if __name__ == '__main__':
    sys.exit(main())
