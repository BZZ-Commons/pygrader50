#!/usr/bin/env python3
"""Push the DokuWiki sources in wiki/ to a DokuWiki instance.

    scripts/publish-wiki.py            # dry run, shows what would change
    scripts/publish-wiki.py --apply    # write the changed pages

The folder mirrors DokuWiki's data/pages/, so the path *is* the page ID:
wiki/howto/git/classroom50/start.txt becomes howto:git:classroom50:start.
wiki/README.md is import notes for a human and is never published.

Only pages whose text actually differs are written, so a re-run after a partial
failure is cheap and the wiki's revision history stays free of empty edits.

Credentials come from the environment — never from a file in the repo:

    DOKUWIKI_URL        base URL, default https://wiki.bzz.ch
    DOKUWIKI_TOKEN      API token (preferred), sent as a Bearer header
    DOKUWIKI_USER       alternative: login plus
    DOKUWIKI_PASSWORD   the matching password (HTTP Basic)

Create a token in DokuWiki under your user profile; scope it to the pages you
intend to write. A dry run needs no credentials at all as long as the wiki is
publicly readable.
"""
# Hyphenated on purpose: a command, not an importable module.
# pylint: disable=invalid-name

from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_URL = 'https://wiki.bzz.ch'
SOURCE_DIR = pathlib.Path(__file__).resolve().parent.parent / 'wiki'
DEFAULT_SUMMARY = 'Sync aus BZZ-Commons/pygrader50'
TIMEOUT = 30


class WikiError(RuntimeError):
    """The wiki refused a call."""


def auth_header() -> dict[str, str]:
    """Authorization header from the environment, empty when unauthenticated."""
    token = os.environ.get('DOKUWIKI_TOKEN', '').strip()
    if token:
        return {'Authorization': f'Bearer {token}'}
    user = os.environ.get('DOKUWIKI_USER', '').strip()
    password = os.environ.get('DOKUWIKI_PASSWORD', '')
    if user:
        raw = base64.b64encode(f'{user}:{password}'.encode()).decode()
        return {'Authorization': f'Basic {raw}'}
    return {}


def call(base_url: str, method: str, params: dict) -> object:
    """One JSON-RPC call. Raises WikiError on a transport or API error."""
    request = urllib.request.Request(
        f'{base_url.rstrip("/")}/lib/exe/jsonrpc.php/{method}',
        data=json.dumps(params).encode('UTF-8'),
        headers={'Content-Type': 'application/json', **auth_header()},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = json.loads(response.read().decode('UTF-8'))
    except urllib.error.HTTPError as exc:
        # The body carries the API's own message ("not authorized to call
        # method core.savePage"), which the status code alone never gives.
        # Dropping it turns a one-line diagnosis into a guessing game.
        detail = exc.read().decode('UTF-8', errors='replace').strip()
        try:
            detail = (json.loads(detail).get('error') or {}).get('message') or detail
        except json.JSONDecodeError:
            pass
        raise WikiError(f'{method}: HTTP {exc.code} — {detail[:200]}') from exc
    except urllib.error.URLError as exc:
        raise WikiError(f'{method}: {exc.reason}') from exc
    except json.JSONDecodeError as exc:
        raise WikiError(f'{method}: keine JSON-Antwort ({exc})') from exc

    # The API reports success as an error object with code 0, so a non-zero code
    # is the only reliable failure signal.
    error = body.get('error') or {}
    if error.get('code'):
        raise WikiError(f'{method}: {error.get("message")} (code {error["code"]})')
    return body.get('result')


def page_id(path: pathlib.Path) -> str:
    """Page ID for a source file: the path with ':' instead of '/'."""
    return ':'.join(path.relative_to(SOURCE_DIR).with_suffix('').parts)


def sources() -> list[pathlib.Path]:
    """Every .txt under wiki/, sorted. README.md is import notes, not a page."""
    return sorted(SOURCE_DIR.rglob('*.txt'))


def normalise(text: str) -> str:
    """Compare without tripping over line endings or a trailing newline."""
    return text.replace('\r\n', '\n').rstrip('\n')


def main() -> int:
    """Compare every source against the wiki and write what differs."""
    apply = '--apply' in sys.argv[1:]
    summary = DEFAULT_SUMMARY
    if '--summary' in sys.argv:
        summary = sys.argv[sys.argv.index('--summary') + 1]

    base_url = os.environ.get('DOKUWIKI_URL', '').strip() or DEFAULT_URL
    if not SOURCE_DIR.is_dir():
        print(f'{SOURCE_DIR} fehlt', file=sys.stderr)
        return 2
    if apply and not auth_header():
        print('DOKUWIKI_TOKEN oder DOKUWIKI_USER/DOKUWIKI_PASSWORD setzen',
              file=sys.stderr)
        return 2

    files = sources()
    print(f'== {len(files)} Seiten gegen {base_url} ==')
    if not apply:
        print('(Trockenlauf — --apply schreibt)')

    tally = {'geschrieben': 0, 'unverändert': 0, 'fehlgeschlagen': 0}
    for path in files:
        pid = page_id(path)
        wanted = path.read_text(encoding='UTF-8')
        try:
            current = call(base_url, 'core.getPage', {'page': pid}) or ''
        except WikiError as exc:
            # A page that does not exist yet reads as an error; treat it as empty
            # so the first publish creates it instead of aborting the run.
            current = ''
            if 'HTTP' in str(exc):
                print(f'FEHLER   {pid}: {exc}')
                tally['fehlgeschlagen'] += 1
                continue

        if normalise(str(current)) == normalise(wanted):
            print(f'gleich   {pid}')
            tally['unverändert'] += 1
            continue

        if not apply:
            print(f'würde    {pid}')
            tally['geschrieben'] += 1
            continue

        try:
            call(base_url, 'core.savePage',
                 {'page': pid, 'text': wanted, 'summary': summary, 'isminor': False})
            print(f'gesetzt  {pid}')
            tally['geschrieben'] += 1
        except WikiError as exc:
            print(f'FEHLER   {pid}: {exc}')
            tally['fehlgeschlagen'] += 1

    print('== ' + '  '.join(f'{k}: {v}' for k, v in tally.items()) + ' ==')
    return 1 if tally['fehlgeschlagen'] else 0


if __name__ == '__main__':
    sys.exit(main())
