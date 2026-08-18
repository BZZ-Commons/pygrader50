"""Shared GitHub plumbing for the teacher-side maintenance scripts.

`sync-template-pins.py` and `sync-template-docstrings.py` both walk the template
repos of a classroom and rewrite a file in each. Everything they need from
GitHub lives here so a fix lands once instead of twice.

Deliberately NOT part of `src/pygrader50`: that package is pip-installed into
every student grading run and must not grow teacher tooling or a `gh`
dependency.

Underscore-prefixed because the scripts next to it are hyphenated commands and
cannot be imported; this one is a module.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys

TIMEOUT = 60


class GitHubError(RuntimeError):
    """A `gh` call failed for a reason other than "the file is not there"."""


def gh_run(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    """Run `gh` and return (returncode, stdout, stderr).

    stderr is returned rather than swallowed: without it a failure reports only
    `FAILED <repo>` and the operator has no HTTP status to act on.
    """
    proc = subprocess.run(
        ['gh', *args], input=stdin, capture_output=True, text=True,
        check=False, timeout=TIMEOUT,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _contents(repo: str, path: str, extra: list[str]) -> tuple[int, str, str]:
    return gh_run(['api', f'repos/{repo}/contents/{path}', *extra])


def fetch_raw(repo: str, path: str) -> str | None:
    """File contents, or None when the file genuinely does not exist.

    A 404 means "absent" and returns None. Any other failure — rate limit,
    network, permissions — raises, because silently treating it as "absent"
    makes a run report SKIP and still exit 0.
    """
    code, out, err = _contents(repo, path, ['-H', 'Accept: application/vnd.github.raw'])
    if code == 0:
        return out
    if _is_missing(err):
        return None
    raise GitHubError(f'{repo}/{path}: {err.strip() or f"gh exited {code}"}')


def fetch_json(repo: str, path: str) -> dict | None:
    """The contents API object (carries both `.content` and `.sha`), or None."""
    code, out, err = _contents(repo, path, [])
    if code == 0:
        return json.loads(out)
    if _is_missing(err):
        return None
    raise GitHubError(f'{repo}/{path}: {err.strip() or f"gh exited {code}"}')


def _is_missing(stderr: str) -> bool:
    """True when `gh` failed because the resource is not there."""
    lowered = stderr.lower()
    return 'not found' in lowered or 'http 404' in lowered


def put_file(repo: str, path: str, content: str, message: str, sha: str | None = None) -> str:
    """Create or update `path`. Returns '' on success, else the error text.

    Pass `sha` when the caller already fetched the contents object; otherwise it
    is looked up, which costs one extra call.
    """
    if sha is None:
        existing = fetch_json(repo, path)
        sha = existing.get('sha') if existing else None
    args = [
        'api', '-X', 'PUT', f'repos/{repo}/contents/{path}',
        '-f', f'message={message}',
        '-f', f'content={base64.b64encode(content.encode()).decode()}',
    ]
    if sha:
        args += ['-f', f'sha={sha}']
    code, _, err = gh_run(args)
    return '' if code == 0 else (err.strip() or f'gh exited {code}')


def assignments_of(org: str, classroom: str) -> list[dict]:
    """The `assignments` list from `<classroom>/assignments.json` in the config repo.

    This is the authoritative target list. Never list the template organisation
    instead — it also holds templates of modules on other toolchains, and
    touching those stops their grading silently.
    """
    code, out, err = gh_run([
        'api', f'repos/{org}/classroom50/contents/{classroom}/assignments.json',
        '-H', 'Accept: application/vnd.github.raw',
    ])
    if code != 0:
        raise GitHubError(
            f'could not read {classroom}/assignments.json from {org}/classroom50: '
            f'{err.strip() or f"gh exited {code}"}'
        )
    return json.loads(out).get('assignments') or []


def template_repos(org: str, classroom: str) -> list[str]:
    """Distinct `owner/repo` of every template the classroom uses, sorted.

    Distinct on purpose: two assignments may share one template, and writing to
    it twice would double-count the tally and produce a redundant commit.
    """
    return sorted({
        f"{entry['template']['owner']}/{entry['template']['repo']}"
        for entry in assignments_of(org, classroom)
        if entry.get('template')
    })


def parse_args(argv: list[str], usage: str) -> tuple[str, str, bool]:
    """(org, classroom, apply) from argv, or exit with `usage`."""
    if len(argv) < 3:
        print(usage, file=sys.stderr)
        sys.exit(2)
    return argv[1], argv[2], '--apply' in argv[3:]


def report(tally: dict[str, int]) -> int:
    """Print the trailing `== k: v ==` line; exit code 1 when anything failed."""
    print('== ' + '  '.join(f'{key}: {value}' for key, value in tally.items()) + ' ==')
    return 1 if tally.get('failed') else 0
