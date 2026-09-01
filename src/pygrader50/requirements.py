"""Install the extra packages an assignment declares in `requirements.txt`.

The file is the one the students already install locally, so using it here is
what makes "works on my machine" mean something. It is not used verbatim: it
also pins `pytest` and `pylint`, and a plain `pip install -r` happily
*downgrades* the very tools the grade is computed with — printing `ERROR:` and
still exiting 0. The pins in `pyproject.toml` would then decide nothing.

So the file is filtered. Every requirement naming a package the engine owns is
dropped with a warning; the rest is installed under a constraint file that pins
those same packages to the versions currently installed. A student pin can add
`httpx`, never move `pylint`.

Transitive versions are the remaining gap, the same one `pyproject.toml`
documents: a package that itself demands `astroid<4` is not stopped by a
constraint on `pylint`. It fails the install rather than passing silently, which
is the direction that keeps the grade honest.

Failure is never fatal. A typo in a pin, or an index that is down, is not an
infrastructure failure of ours: the step warns and grading continues, so the
submission records a score with a readable `ModuleNotFoundError` instead of an
`error` with no feedback at all.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile
from importlib import metadata
from typing import NamedTuple

from .console import bcolors, info, section, warn

REQUIREMENTS_FILENAME = 'requirements.txt'

# A hanging package index must not hold the job open until Actions kills it —
# at that point there is no result.json and the submission records as `error`.
INSTALL_TIMEOUT = 180

# The packages the grade is computed with, plus the engine itself. A student pin
# naming one of these is dropped, never installed. Mirrors the dependencies in
# `pyproject.toml`; `tests/test_requirements.py` fails if the two drift apart.
PROTECTED = ('pygrader50', 'pytest', 'pytest-timeout', 'pylint')

# Leading name of a requirement line, up to whatever ends it: a version
# specifier, an extras bracket, an environment marker or a direct URL.
NAME = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[\[<>=!~;@]|$)')


class Plan(NamedTuple):
    """A requirements file split into what we do with each of its lines."""

    install: list[str]
    dropped: list[str]
    unsupported: list[str]


def canonical(name: str) -> str:
    """Normalise a distribution name per PEP 503, so `Pytest_Timeout` matches."""
    return re.sub(r'[-_.]+', '-', name).lower()


PROTECTED_NAMES = frozenset(canonical(name) for name in PROTECTED)


def strip_comment(line: str) -> str:
    """Remove a pip-style comment: whole-line, or one preceded by whitespace."""
    if line.lstrip().startswith('#'):
        return ''
    return re.split(r'\s#', line, maxsplit=1)[0]


def plan(text: str) -> Plan:
    """Sort the lines of a requirements file into installable, dropped and unsupported.

    Unsupported covers what a name-based filter cannot vouch for: pip options
    (`-r`, `--index-url`, `-e`) and continued lines. Dropping them is the safe
    direction — `-r` can pull in a second file the filter never sees.
    """
    installable: list[str] = []
    dropped: list[str] = []
    unsupported: list[str] = []
    for raw in text.splitlines():
        line = strip_comment(raw).strip()
        if not line:
            continue
        match = NAME.match(line)
        if match is None or line.endswith('\\'):
            unsupported.append(line)
        elif canonical(match.group(1)) in PROTECTED_NAMES:
            dropped.append(line)
        else:
            installable.append(line)
    return Plan(installable, dropped, unsupported)


def constraints() -> list[str]:
    """Pin every protected package to the version installed right now."""
    pins = []
    for name in PROTECTED:
        try:
            pins.append(f'{name}=={metadata.version(name)}')
        except metadata.PackageNotFoundError:
            # Running from a source checkout, or an optional pin absent: nothing
            # to protect, because nothing is installed to be downgraded.
            continue
    return pins


def pip_install(lines: list[str], pins: list[str]) -> subprocess.CompletedProcess:
    """Run pip over `lines`, constrained by `pins`, in a directory of our own."""
    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch)
        wanted = root / 'extra.txt'
        limits = root / 'constraints.txt'
        wanted.write_text('\n'.join(lines) + '\n', encoding='UTF-8')
        limits.write_text('\n'.join(pins) + '\n', encoding='UTF-8')
        return subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
             '--no-input', '-r', str(wanted), '-c', str(limits)],
            capture_output=True, text=True, timeout=INSTALL_TIMEOUT, check=False,
        )


def install(workspace: pathlib.Path) -> None:
    """Install the extra packages the checkout declares, if it declares any."""
    path = workspace / REQUIREMENTS_FILENAME
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding='UTF-8')
    except OSError as exc:
        warn(f'{REQUIREMENTS_FILENAME} is unreadable ({exc}); grading without it')
        return

    wanted = plan(text)
    if wanted.dropped:
        # Not a warning: every template pins pytest and pylint, so an annotation
        # here would put two yellow markers on all 63 assignments, every run.
        info(
            f'{REQUIREMENTS_FILENAME}: the grading engine pins its own version of '
            f'{", ".join(wanted.dropped)}'
        )
    for line in wanted.unsupported:
        warn(f'{REQUIREMENTS_FILENAME}: ignoring "{line}" — unsupported in a graded run')
    if not wanted.install:
        return

    section(f'Installing from {REQUIREMENTS_FILENAME}', color=bcolors.OKBLUE)
    for line in wanted.install:
        info(f'  {line}')
    try:
        completed = pip_install(wanted.install, constraints())
    except subprocess.TimeoutExpired:
        warn(
            f'{REQUIREMENTS_FILENAME}: install timed out after {INSTALL_TIMEOUT}s; '
            'grading without it'
        )
        return
    if completed.returncode != 0:
        warn(f'{REQUIREMENTS_FILENAME}: install failed; grading without it')
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
