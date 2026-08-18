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
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gh import (  # noqa: E402  pylint: disable=wrong-import-position
    GitHubError, assignments_of, fetch_raw, parse_args, put_file, report,
)

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


class WikiError(RuntimeError):
    """The wiki could not be read."""


def http_get(url: str) -> str:
    """Fetch `url` as text, or raise WikiError.

    Raising rather than letting urllib escape keeps one slow or missing page
    from aborting an --apply run half-way, with no tally of what was written.
    """
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WikiError(f'{url}: {exc}') from exc


def wiki_pages(module: str, lu: str) -> dict[str, list[tuple[str, str]]]:
    """Map of `LUxx.Ayy` -> [(page id, title)] for one learning unit's exercises.

    The page ids come from the links the learning unit's start page renders,
    the codes and titles from each page's own heading — a page whose heading
    carries no code is not an exercise and drops out here.

    A code with more than one entry is ambiguous; the caller decides what to do
    about it. Keeping the list (rather than collapsing it to a sentinel) also
    keeps the title, so nothing has to be fetched twice.
    """
    namespace = f'modul/{module}/learningunits/{lu}'
    html = http_get(f'{WIKI}/{namespace}/start')
    names = sorted(set(re.findall(
        rf'href="{re.escape(WIKI)}/{re.escape(namespace)}/aufgaben/([^"?#]+)"', html
    )))
    pages: dict[str, list[tuple[str, str]]] = {}
    for name in names:
        heading = HEADING_RE.search(http_get(f'{WIKI}/_export/raw/{namespace}/aufgaben/{name}'))
        match = CODE_RE.match(heading.group(1)) if heading else None
        if match:
            code = f'{match.group(1)}.{match.group(2)}'.lower()
            title = ' '.join(match.group(3).split())
            pages.setdefault(code, []).append((f'{lu}/aufgaben/{name}', title))
    return pages


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
    # A BOM would sit before the docstring and stop the file from compiling; it
    # is put back untouched at the very front.
    bom, source = ('\ufeff', source[1:]) if source.startswith('\ufeff') else ('', source)
    lines = source.splitlines()
    try:
        body = ast.parse(source).body
    except SyntaxError:
        if opens_with_docstring(lines):
            return None
        body = []

    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        node = body[0]
        head = lines[:node.lineno - 1]
        # Code can share the docstring's closing line; slicing whole lines
        # away would delete it silently.
        rest = lines[node.end_lineno - 1][node.end_col_offset:].lstrip()
        rest = rest[1:].lstrip() if rest.startswith(';') else rest
        tail = ([rest] if rest else []) + lines[node.end_lineno:]
    else:
        # No docstring yet: keep a shebang first, then the docstring, then a
        # blank line before whatever the file started with.
        head = lines[:1] if lines and lines[0].startswith('#!') else []
        rest = lines[len(head):]
        tail = ([''] if rest and rest[0].strip() else []) + rest

    return bom + '\n'.join(head + docstring.splitlines() + tail).rstrip('\n') + '\n'


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


def page_for(
    slug: str, pages: dict[str, list[tuple[str, str]]], lu: str, nr: str
) -> tuple[str, str, str]:
    """(page id, title, reason it is missing) for one assignment."""
    if slug in OVERRIDES:
        page = OVERRIDES[slug]
        title = next((t for entries in pages.values() for pid, t in entries if pid == page), '')
        if not title:
            return '', '', f'override page {page} carries no exercise heading'
        return page, title, ''
    code = f'{lu}.{nr}'
    entries = pages.get(code)
    if not entries:
        return '', '', f'no wiki page carries {code.upper()}'
    if len(entries) != 1:
        return '', '', f'several wiki pages carry {code.upper()}'
    page, title = entries[0]
    return page, title, ''


COMMIT_MESSAGE = (
    'docs: link the assignment description from main.py\n\n'
    'The module docstring names the exercise and points at its page on '
    'wiki.bzz.ch, so the task is one click away from the code students edit. '
    'It also answers the missing-module-docstring every template was losing '
    'lint points to.'
)


def _page_of(slug: str, parts: re.Match, catalogue: dict) -> tuple[str, str, str]:
    """(page id, title, reason it is missing), filling the LU catalogue on demand."""
    module, lu, nr = parts.group('module'), parts.group('lu'), parts.group('nr')
    if (module, lu) not in catalogue:
        catalogue[(module, lu)] = wiki_pages(module, lu)
    return page_for(slug, catalogue[(module, lu)], lu, nr)


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

    try:
        page, title, why = _page_of(slug, parts, catalogue)
        if not page:
            return 'skipped', f'SKIP     {repo}  ({why})'

        entrypoint = entrypoint_of(repo)
        source = fetch_raw(repo, entrypoint)
    except (WikiError, GitHubError) as exc:
        return 'failed', f'FAILED   {repo}  ({exc})'
    if source is None:
        return 'skipped', f'SKIP     {repo}  (no {entrypoint})'

    wanted = with_docstring(source, docstring_for(title, parts.group('module'), page))
    if wanted is None:
        return 'skipped', f'SKIP     {repo}  ({entrypoint} already opens with a string)'
    if wanted == source:
        return 'unchanged', f'ok       {repo}'
    if not apply:
        return 'changed', f'would    {repo}  {entrypoint} -> {page}'
    error = put_file(repo, entrypoint, wanted, COMMIT_MESSAGE)
    if not error:
        return 'changed', f'written  {repo}  {entrypoint} -> {page}'
    return 'failed', f'FAILED   {repo}  ({error})'


def _one_per_template(assignments: list[dict], tally: dict[str, int]):
    """Yield assignments, skipping any whose template repo was handled already.

    Two assignments can share one template. Writing it twice would commit the
    second assignment's link over the first and double-count the tally.
    """
    seen: set[str] = set()
    for assignment in assignments:
        template = assignment.get('template') or {}
        repo = f"{template.get('owner')}/{template.get('repo')}"
        if repo in seen:
            tally['skipped'] += 1
            print(f'SKIP     {repo}  (template already handled)')
            continue
        seen.add(repo)
        yield assignment


def main() -> int:
    """Walk every template and put the assignment link in its main.py."""
    org, classroom, apply = parse_args(
        sys.argv,
        f'usage: {sys.argv[0]} <org> <classroom> [--apply]\n'
        f'example: {sys.argv[0]} <org> <classroom> --apply',
    )

    assignments = assignments_of(org, classroom)
    print(f'== {len(assignments)} assignments ==')
    if not apply:
        print('(dry run — pass --apply to write)')

    catalogue: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {}
    tally = {'changed': 0, 'unchanged': 0, 'skipped': 0, 'failed': 0}
    for assignment in _one_per_template(sorted(assignments, key=lambda a: a['slug']), tally):
        key, line = process(assignment, catalogue, apply)
        tally[key] += 1
        print(line)

    return report(tally)


if __name__ == '__main__':
    sys.exit(main())
