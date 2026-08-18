"""Übertrag der Classroom-50-Punkte nach Moodle.

Läuft NICHT im Studi-Repo, sondern im `classroom50`-Config-Repo — der
Moodle-Token darf nicht in einem Repository liegen, in das Studierende pushen
können. Quelle ist `<classroom>/scores.json`, das `collect-scores` dort ohnehin
schon pflegt.

    python -m pygrader50.moodle m323-ix24/scores.json --dry-run
    python -m pygrader50.moodle m323-ix24/scores.json --assignment m323-lu01-a02-imperativer-ggt

Umgebung:
    MOODLE_URL       Basis-URL der Moodle-Instanz
    MOODLE_TOKEN     Webservice-Token
    MOODLE_FUNCTION  Webservice-Funktion (Vorgabe: mod_externalassignment_update_grade)
    GH_TOKEN         optional, für den Feedback-Text aus dem Release

Je (Assignment, Owner) wird die neueste Abgabe übertragen. Ein Zustandsfile
merkt sich, was bereits übermittelt wurde, damit ein zweiter Lauf nur noch
Änderungen schickt; `--force` ignoriert es.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .console import error as console_error, fail, info, ok as console_ok, section, warn

DEFAULT_FUNCTION = 'mod_externalassignment_update_grade'
STATE_SCHEMA = 'pygrader50/moodle-state/v1'
SCORES_SCHEMA = 'classroom50/scores/v1'


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
        """True, wenn genau diese Abgabe mit dieser Punktzahl schon übertragen wurde."""
        previous = self.entries.get(submission.key)
        return bool(
            previous
            and previous.get('submission') == submission.submission
            and previous.get('score') == submission.score
        )

    def record(self, submission: Submission) -> None:
        """Erfolgreiche Übertragung vermerken."""
        self.entries[submission.key] = {
            'submission': submission.submission,
            'score': submission.score,
            'max-score': submission.max_score,
        }

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


def release_feedback(submission: Submission, token: str | None) -> str:
    """Den Markdown-Text des Releases holen — das Feedback, das pygrader50 schreibt."""
    if not (submission.repository and submission.submission):
        return ''
    tag = urllib.parse.quote(submission.submission, safe='')
    url = f'https://api.github.com/repos/{submission.repository}/releases/tags/{tag}'
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response).get('body') or ''
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        warn(f'{submission.key}: Feedback-Text nicht abrufbar ({exc})')
        return ''


def build_payload(submission: Submission, feedback: str) -> dict:
    """Formularfelder für mod_externalassignment_update_grade."""
    body = feedback
    if submission.late:
        body = '> ⏰ Abgabe nach dem Fälligkeitstermin.\n\n' + body
    if submission.release_url:
        body += f'\n\nAbgabe: {submission.release_url}\n'
    return {
        'assignment_name': submission.assignment,
        'user_name': submission.owner,
        'points': submission.score,
        'max': submission.max_score,
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


def sync(  # pylint: disable=too-many-arguments
    submissions: list[Submission], *, sender, feedback_provider, state: State,
    dry_run: bool = False, force: bool = False,
) -> tuple[int, int, int]:
    """Überträgt die Abgaben; gibt (übertragen, übersprungen, fehlgeschlagen) zurück."""
    sent = skipped = failed = 0
    for submission in submissions:
        label = f'{submission.assignment} / {submission.owner}'
        if not force and state.is_current(submission):
            skipped += 1
            continue
        if not submission.owner:
            warn(f'{submission.assignment}: Abgabe ohne Owner übersprungen')
            failed += 1
            continue

        if dry_run:
            info(f'[dry-run] {label}: {submission.score}/{submission.max_score}')
            sent += 1
            continue

        payload = build_payload(submission, feedback_provider(submission))
        ok, message = sender(payload)
        if ok:
            state.record(submission)
            sent += 1
            console_ok(f'✅ {label}: {submission.score}/{submission.max_score}')
        else:
            failed += 1
            fail(f'❌ {label}: {message}')
    return sent, skipped, failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Kommandozeile lesen."""
    parser = argparse.ArgumentParser(
        prog='python -m pygrader50.moodle',
        description='Überträgt die Punkte aus scores.json nach Moodle.',
    )
    parser.add_argument('scores', type=pathlib.Path, help='Pfad zu <classroom>/scores.json')
    parser.add_argument('--assignment', help='nur dieses Assignment übertragen')
    parser.add_argument('--user', help='nur diesen GitHub-Login übertragen')
    parser.add_argument('--state', type=pathlib.Path,
                        help='Zustandsfile; ohne Angabe wird alles übertragen')
    parser.add_argument('--force', action='store_true',
                        help='auch unverändertes erneut übertragen')
    parser.add_argument('--dry-run', action='store_true',
                        help='nur anzeigen, nichts senden')
    parser.add_argument('--no-feedback', action='store_true',
                        help='ohne Feedback-Text aus dem Release')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstieg."""
    args = parse_args(argv)

    if not args.scores.is_file():
        console_error(f'{args.scores} nicht gefunden')
        return 1

    base_url = os.environ.get('MOODLE_URL', '').strip()
    token = os.environ.get('MOODLE_TOKEN', '').strip()
    # `or DEFAULT_FUNCTION`, nicht der Vorgabewert von .get(): GitHub Actions
    # setzt `MOODLE_FUNCTION: ${{ vars.MOODLE_FUNCTION }}` auch dann, wenn die
    # Variable nicht existiert — dann steht dort der leere String und .get()
    # liefert ihn statt der Vorgabe. Moodle antwortet auf ein leeres
    # `wsfunction` mit `invalidparameter` / "Missing function name".
    function = os.environ.get('MOODLE_FUNCTION', '').strip() or DEFAULT_FUNCTION
    if not args.dry_run and not (base_url and token):
        console_error('MOODLE_URL und MOODLE_TOKEN müssen gesetzt sein')
        return 1

    try:
        submissions = latest_submissions(
            json.loads(args.scores.read_text(encoding='UTF-8')),
            assignment=args.assignment,
            owner=args.user,
        )
    except ValueError as exc:
        console_error(exc)
        return 1

    section(f'Moodle-Übertrag: {len(submissions)} Abgaben')
    state = State.load(args.state)
    gh_token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or None

    endpoint = endpoint_url(base_url, token, function) if not args.dry_run else ''
    sent, skipped, failed = sync(
        submissions,
        sender=lambda payload: post(endpoint, payload),
        feedback_provider=(
            (lambda submission: '') if args.no_feedback
            else (lambda submission: release_feedback(submission, gh_token))
        ),
        state=state,
        dry_run=args.dry_run,
        force=args.force,
    )

    if not args.dry_run:
        state.save()

    info(f'übertragen: {sent} | unverändert: {skipped} | fehlgeschlagen: {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
