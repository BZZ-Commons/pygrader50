#!/usr/bin/env python3
"""Bring the tool pins in a classroom's template repos up to date.

    scripts/sync-template-pins.py <org> <classroom>           # dry run
    scripts/sync-template-pins.py <org> <classroom> --apply    # write

Rewrites two files in every template the classroom's assignments.json points at:

    requirements.txt   the pins in TOOL_PINS, everything else left alone
    .python-version    PYTHON_VERSION

Only the tool pins are touched. A template that also needs httpx or
pytest-asyncio keeps those lines untouched and in place — the point is to bump
what everyone shares, not to flatten the differences. Packages a student is
meant to add deliberately (flask in the lu06 exercises) are none of this
script's business.

The target list comes from the `template` block of assignments.json, never from
listing the template organisation: that org also holds templates for modules on
other toolchains.

Requires `gh` on PATH and authenticated.
"""
# Hyphenated on purpose: this is a command, not an importable module, and it
# sits next to remove-legacy-classroom-yml.sh.
# pylint: disable=invalid-name

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys

# --- update these once per semester ------------------------------------------
# Every template gets these; a missing one is appended.
TOOL_PINS = {
    'pylint': '4.0.7',
    'pytest': '9.1.1',
}
# Bumped only where the template already lists them — test infrastructure a few
# assignments need. pytest-asyncio in particular MUST move with pytest: 0.23.8
# and pytest 9 are a ResolutionImpossible, so bumping pytest alone breaks the
# one template that uses it.
BUMP_IF_PRESENT = {
    'httpx': '0.28.1',
    'pytest-asyncio': '1.4.0',
}
PYTHON_VERSION = '3.14'
# -----------------------------------------------------------------------------

REQUIREMENTS = 'requirements.txt'
PYTHON_VERSION_FILE = '.python-version'
# Package name at the start of a requirement line, before any version specifier
# or extras — `pytest-asyncio == 1.4.0` must NOT read as `pytest`.
NAME_RE = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def gh_run(args: list[str], stdin: str | None = None) -> tuple[int, str]:
    """Run `gh` and return (returncode, stdout)."""
    proc = subprocess.run(
        ['gh', *args], input=stdin, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout


def fetch_raw(repo: str, path: str) -> str | None:
    """File contents, or None when the file does not exist."""
    code, out = gh_run(
        ['api', f'repos/{repo}/contents/{path}', '-H', 'Accept: application/vnd.github.raw']
    )
    return out if code == 0 else None


def fetch_sha(repo: str, path: str) -> str | None:
    """Blob SHA, or None when the file does not exist."""
    code, out = gh_run(['api', f'repos/{repo}/contents/{path}', '--jq', '.sha'])
    return out.strip() if code == 0 and out.strip() else None


def put_file(repo: str, path: str, content: str, message: str) -> bool:
    """Create or update `path`. Returns True on success."""
    args = [
        'api', '-X', 'PUT', f'repos/{repo}/contents/{path}',
        '-f', f'message={message}',
        '-f', f'content={base64.b64encode(content.encode()).decode()}',
    ]
    sha = fetch_sha(repo, path)
    if sha:
        args += ['-f', f'sha={sha}']
    code, _ = gh_run(args)
    return code == 0


def bump_requirements(text: str) -> str:
    """Return `text` with the pinned tool lines rewritten, order preserved.

    Lines that are not a pinned tool survive verbatim, including comments and
    blank lines — a package the students are meant to add themselves stays
    exactly as it is. A missing TOOL_PINS entry is appended; BUMP_IF_PRESENT
    entries are never introduced.
    """
    lines = text.splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = NAME_RE.match(line)
        name = match.group(1).lower() if match else ''
        if name in TOOL_PINS:
            out.append(f'{name}=={TOOL_PINS[name]}')
            seen.add(name)
        elif name in BUMP_IF_PRESENT:
            out.append(f'{name}=={BUMP_IF_PRESENT[name]}')
        else:
            out.append(line)
    for name, version in TOOL_PINS.items():
        if name not in seen:
            out.append(f'{name}=={version}')
    while out and not out[-1].strip():
        out.pop()
    return '\n'.join(out) + '\n'


def templates_for(org: str, classroom: str) -> list[str]:
    """`owner/repo` of every template the classroom's assignments point at."""
    code, out = gh_run([
        'api', f'repos/{org}/classroom50/contents/{classroom}/assignments.json',
        '-H', 'Accept: application/vnd.github.raw',
    ])
    if code != 0:
        sys.exit(f'could not read {classroom}/assignments.json from {org}/classroom50')
    data = json.loads(out)
    return sorted({
        f"{a['template']['owner']}/{a['template']['repo']}" for a in data['assignments']
    })


def pending(repo: str) -> dict[str, str]:
    """Map of path -> wanted content for the files that are out of date."""
    work: dict[str, str] = {}

    wanted = bump_requirements(fetch_raw(repo, REQUIREMENTS) or '')
    if fetch_raw(repo, REQUIREMENTS) != wanted:
        work[REQUIREMENTS] = wanted

    wanted_py = PYTHON_VERSION + '\n'
    if fetch_raw(repo, PYTHON_VERSION_FILE) != wanted_py:
        work[PYTHON_VERSION_FILE] = wanted_py

    return work


def commit_message() -> str:
    """The message every rewritten file is committed with."""
    pins = ', '.join(f'{n}=={v}' for n, v in TOOL_PINS.items())
    return (
        f'chore: update tool pins and pin Python {PYTHON_VERSION}\n\n'
        f'{pins} are the versions that install on Python {PYTHON_VERSION}; the '
        'previous ones predate it. Packages an assignment adds on its own are '
        'left untouched.'
    )


def main() -> int:
    """Walk every template and bring its pins in line."""
    if len(sys.argv) < 3:
        print(f'usage: {sys.argv[0]} <org> <classroom> [--apply]', file=sys.stderr)
        print(f'example: {sys.argv[0]} m320-ix25 m320-ix25 --apply', file=sys.stderr)
        return 2
    org, classroom, apply = sys.argv[1], sys.argv[2], '--apply' in sys.argv[3:]

    repos = templates_for(org, classroom)
    print(f'== {len(repos)} templates ==')
    if not apply:
        print('(dry run — pass --apply to write)')

    tally = {'changed': 0, 'unchanged': 0, 'failed': 0}
    for repo in repos:
        work = pending(repo)
        if not work:
            print(f'ok       {repo}')
            tally['unchanged'] += 1
        elif not apply:
            print(f'would    {repo}  ({", ".join(sorted(work))})')
            tally['changed'] += 1
        elif all(put_file(repo, p, c, commit_message()) for p, c in work.items()):
            print(f'written  {repo}  ({", ".join(sorted(work))})')
            tally['changed'] += 1
        else:
            print(f'FAILED   {repo}')
            tally['failed'] += 1

    print('== ' + '  '.join(f'{k}: {v}' for k, v in tally.items()) + ' ==')
    return 1 if tally['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
