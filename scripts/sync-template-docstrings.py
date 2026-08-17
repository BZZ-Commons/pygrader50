#!/usr/bin/env python3
"""Give every template's main.py a docstring that links its wiki assignment.

    scripts/sync-template-docstrings.py <org> <classroom>           # dry run
    scripts/sync-template-docstrings.py <org> <classroom> --apply    # write

The module docstring names the exercise and points at its page on wiki.bzz.ch:

    \"\"\"Funktionaler Bubblesort.

    Aufgabenstellung: https://wiki.bzz.ch/modul/m323/learningunits/
                      lu01/aufgaben/funktionalerbubblesort
    \"\"\"

(the URL is one line in the file; it is wrapped here to keep this one short)

German on purpose — it is material students read, unlike the rest of the code
in this repo.

The assignment slug does NOT map to the wiki page name: `m323-lu01-a04-funktionaler-ggt`
lives at `lu01/aufgaben/funktionalereuklid`, `m323-lu06-a05-authentication` at
`lu06/aufgaben/auth`, and in lu04 the numbering is shifted against the names
(`sorting2` is A11, `sorting` is A12). What does hold is the `LUxx.Ayy` code
every page carries in its heading, so that code is the key. An assignment whose
code matches no page, or more than one, is reported and skipped rather than
guessed at — except for the entries in OVERRIDES.

The target list comes from the `template` block of assignments.json, never from
listing the template organisation: that org also holds templates for modules on
other toolchains.

Requires `gh` on PATH and authenticated.
"""
# Hyphenated on purpose: this is a command, not an importable module, and it
# sits next to sync-template-pins.py.
# pylint: disable=invalid-name

from __future__ import annotations

import ast
import base64
import json
import re
import subprocess
import sys
import urllib.request

WIKI = 'https://wiki.bzz.ch'
# Where the link goes when lint.json names no file, and the file preferred when
# it names several.
ENTRYPOINT = 'main.py'
LINT_CONFIG = '.github/autograding/lint.json'

# Assignments whose code matches several pages. LU01.A03 heads both the exercise
# and its extended variant; the plain one is what the template implements.
OVERRIDES = {
    'm323-lu01-a03-funktionaler-bubblesort': 'lu01/aufgaben/funktionalerbubblesort',
}

# `LU01.A03 - Funktionaler Bubblesort` in a page heading.
HEADING_RE = re.compile(r'^\s*=+\s*(.+?)\s*=+\s*$', re.M)
CODE_RE = re.compile(r'^\s*(LU\d\d)\.(A\d\d)\s*-\s*(.*)$', re.I)
# `m323-lu01-a03-funktionaler-bubblesort` -> module, learning unit, exercise.
SLUG_RE = re.compile(r'^(?P<module>[a-z0-9]+)-(?P<lu>lu\d\d)-(?P<nr>a\d\d)-')


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


def http_get(url: str) -> str:
    """Fetch `url` as text."""
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode('utf-8', 'replace')


def wiki_pages(module: str, lu: str) -> dict[str, str]:
    """Map of `LUxx.Ayy` -> page id for one learning unit's exercises.

    The page ids come from the links the learning unit's start page renders,
    the codes from each page's own heading — a page whose heading carries no
    code is not an exercise and drops out here.
    """
    namespace = f'modul/{module}/learningunits/{lu}'
    html = http_get(f'{WIKI}/{namespace}/start')
    names = sorted(set(re.findall(
        rf'href="{re.escape(WIKI)}/{re.escape(namespace)}/aufgaben/([^"?#]+)"', html
    )))
    pages: dict[str, list[str]] = {}
    for name in names:
        heading = HEADING_RE.search(http_get(f'{WIKI}/_export/raw/{namespace}/aufgaben/{name}'))
        match = CODE_RE.match(heading.group(1)) if heading else None
        if match:
            code = f'{match.group(1)}.{match.group(2)}'.lower()
            pages.setdefault(code, []).append(f'{lu}/aufgaben/{name}')
    return {code: ids[0] if len(ids) == 1 else '' for code, ids in pages.items()}


def wiki_title(module: str, page: str) -> str:
    """The exercise title of `page`, with its `LUxx.Ayy` code stripped off."""
    heading = HEADING_RE.search(
        http_get(f'{WIKI}/_export/raw/modul/{module}/learningunits/{page}')
    )
    text = heading.group(1) if heading else ''
    match = CODE_RE.match(text)
    if match:
        text = match.group(3)
    return ' '.join(text.split())


def docstring_for(title: str, module: str, page: str) -> str:
    """The wanted module docstring, quotes included, without a trailing newline."""
    headline = title if title.endswith(('.', '!', '?', ':')) else f'{title}.'
    url = f'{WIKI}/modul/{module}/learningunits/{page}'
    return f'"""{headline}\n\nAufgabenstellung: {url}\n"""'


def opens_with_docstring(lines: list[str]) -> bool:
    """True when the first code line of `lines` starts a string literal."""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        return stripped.startswith(('"""', "'''", '"', "'", 'r"', "r'"))
    return False


def with_docstring(source: str, docstring: str) -> str | None:
    """`source` with its module docstring replaced by `docstring`.

    A file that does not parse still gets the docstring prepended, as long as it
    does not already open with a string literal: a few templates are stubs with
    deliberate holes (`add =  # Ihr Code hier`), and prepending cannot make an
    already broken file worse. Only the case where a docstring may be there but
    cannot be located is left alone — that would risk two of them.
    """
    lines = source.splitlines()
    try:
        body = ast.parse(source).body
    except SyntaxError:
        if opens_with_docstring(lines):
            return None
        body = []

    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        head = lines[:body[0].lineno - 1]
        tail = lines[body[0].end_lineno:]
    else:
        # No docstring yet: keep a shebang first, then the docstring, then a
        # blank line before whatever the file started with.
        head = lines[:1] if lines and lines[0].startswith('#!') else []
        rest = lines[len(head):]
        tail = ([''] if rest and rest[0].strip() else []) + rest

    return '\n'.join(head + docstring.splitlines() + tail).rstrip('\n') + '\n'


def entrypoint_of(repo: str) -> str:
    """The file the link belongs in: what lint.json grades, main.py preferred.

    lint.json is the only place that says which file an assignment is actually
    about — m323-lu04-a12-sorting has no main.py at all, its work happens in
    countries_data.py.
    """
    raw = fetch_raw(repo, LINT_CONFIG)
    try:
        files = json.loads(raw)['files'] if raw else []
    except (json.JSONDecodeError, KeyError, TypeError):
        files = []
    if not files:
        return ENTRYPOINT
    return ENTRYPOINT if ENTRYPOINT in files else files[0]


def assignments_of(org: str, classroom: str) -> list[dict]:
    """The classroom's assignments, as assignments.json lists them."""
    code, out = gh_run([
        'api', f'repos/{org}/classroom50/contents/{classroom}/assignments.json',
        '-H', 'Accept: application/vnd.github.raw',
    ])
    if code != 0:
        sys.exit(f'could not read {classroom}/assignments.json from {org}/classroom50')
    return json.loads(out)['assignments']


def page_for(slug: str, pages: dict[str, str], lu: str, nr: str) -> tuple[str, str]:
    """(page id, reason it is missing) for one assignment."""
    if slug in OVERRIDES:
        return OVERRIDES[slug], ''
    code = f'{lu}.{nr}'
    if code not in pages:
        return '', f'no wiki page carries {code.upper()}'
    if not pages[code]:
        return '', f'several wiki pages carry {code.upper()}'
    return pages[code], ''


COMMIT_MESSAGE = (
    'docs: link the assignment description from main.py\n\n'
    'The module docstring names the exercise and points at its page on '
    'wiki.bzz.ch, so the task is one click away from the code students edit. '
    'It also answers the missing-module-docstring every template was losing '
    'lint points to.'
)


def process(  # pylint: disable=too-many-return-statements
    assignment: dict, catalogue: dict, apply: bool
) -> tuple[str, str]:
    """(tally key, log line) for one assignment, writing when `apply`.

    Every early return is one reason a template drops out; flattening them into
    a nested expression would only hide which one fired.
    """
    slug = assignment['slug']
    repo = f"{assignment['template']['owner']}/{assignment['template']['repo']}"
    parts = SLUG_RE.match(slug)
    if not parts:
        return 'skipped', f'SKIP     {repo}  (slug does not name a learning unit)'

    module, lu, nr = parts.group('module'), parts.group('lu'), parts.group('nr')
    if (module, lu) not in catalogue:
        catalogue[(module, lu)] = wiki_pages(module, lu)
    page, why = page_for(slug, catalogue[(module, lu)], lu, nr)
    if not page:
        return 'skipped', f'SKIP     {repo}  ({why})'

    entrypoint = entrypoint_of(repo)
    source = fetch_raw(repo, entrypoint)
    if source is None:
        return 'skipped', f'SKIP     {repo}  (no {entrypoint})'

    wanted = with_docstring(source, docstring_for(wiki_title(module, page), module, page))
    if wanted is None:
        return 'skipped', f'SKIP     {repo}  ({entrypoint} already opens with a string)'
    if wanted == source:
        return 'unchanged', f'ok       {repo}'
    if not apply:
        return 'changed', f'would    {repo}  {entrypoint} -> {page}'
    if put_file(repo, entrypoint, wanted, COMMIT_MESSAGE):
        return 'changed', f'written  {repo}  {entrypoint} -> {page}'
    return 'failed', f'FAILED   {repo}'


def main() -> int:
    """Walk every template and put the assignment link in its main.py."""
    if len(sys.argv) < 3:
        print(f'usage: {sys.argv[0]} <org> <classroom> [--apply]', file=sys.stderr)
        print(f'example: {sys.argv[0]} m323-ix24 m323-ix24 --apply', file=sys.stderr)
        return 2
    org, classroom, apply = sys.argv[1], sys.argv[2], '--apply' in sys.argv[3:]

    assignments = assignments_of(org, classroom)
    print(f'== {len(assignments)} assignments ==')
    if not apply:
        print('(dry run — pass --apply to write)')

    catalogue: dict[tuple[str, str], dict[str, str]] = {}
    tally = {'changed': 0, 'unchanged': 0, 'skipped': 0, 'failed': 0}
    for assignment in sorted(assignments, key=lambda a: a['slug']):
        key, line = process(assignment, catalogue, apply)
        tally[key] += 1
        print(line)

    print('== ' + '  '.join(f'{k}: {v}' for k, v in tally.items()) + ' ==')
    return 1 if tally['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
