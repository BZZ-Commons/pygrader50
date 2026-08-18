"""Grade example repositories with the real engine.

The one place that knows how to start the engine as a subprocess — used by the
fixture corpus, by `test_pytest_runner.py`, and by
`scripts/refresh-fixture-expectations.py`, so a change to how grading is invoked
lands once.

The subprocess is not optional: `pytest_runner.run()` starts nested pytest
sessions, and running those inside the session that checks them would share the
module cache and the assertion-rewrite state between scenarios.
"""

import json
import os
import pathlib
import shutil
import re
import subprocess
import sys

from conftest import SRC

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures'
EXPECTATION_FILENAME = 'expected.json'
CASE_POINTS = 2
CASE_TIMEOUT = 10

DRIVER = '''\
"""Grade the checkout this script sits in and dump the section result."""
import json
import sys

from pygrader50 import pytest_runner
from pygrader50.config import Testcase

output, names, timeout, points = sys.argv[1], json.loads(sys.argv[2]), *map(int, sys.argv[3:])
cases = [Testcase(name=name, function=name, timeout=timeout, points=points) for name in names]
with open(output, 'w', encoding='UTF-8') as handle:
    json.dump(pytest_runner.run(cases), handle)
'''


def grade_checkout(checkout: pathlib.Path, names: list[str], *,
                   points: int = CASE_POINTS, timeout: int = CASE_TIMEOUT) -> dict:
    """Grade `checkout` for the named cases; returns the section plus the log.

    The section result is what `pytest_runner.run()` returned, with the console
    output of the run added under `console` — several tests are about what the
    student sees in the Actions log, not only about the table.
    """
    driver = checkout / 'grade_checkout.py'
    driver.write_text(DRIVER, encoding='UTF-8')
    output = checkout / 'section.json'

    completed = subprocess.run(
        [sys.executable, str(driver), str(output), json.dumps(names), str(timeout), str(points)],
        cwd=checkout, env=dict(os.environ, PYTHONPATH=str(SRC)),
        capture_output=True, text=True, check=False,
    )
    if not output.is_file():
        raise RuntimeError(f'the grader wrote nothing in {checkout}\n{completed.stderr}')
    section = json.loads(output.read_text(encoding='UTF-8'))
    section['console'] = completed.stdout
    return section


def fixtures() -> list[pathlib.Path]:
    """Every vendored example repository, in a stable order."""
    return sorted(path for path in FIXTURES.iterdir() if path.is_dir())


def case_names(fixture: pathlib.Path) -> list[str]:
    """The test functions declared in the fixture, deduplicated and sorted.

    A name that two classes both declare is one case for us: `-k` selects both
    and the first failure decides, which is what a `unittests.json` entry naming
    that function would do in a real assignment too.
    """
    names: set[str] = set()
    for test_file in sorted(fixture.glob('*_test.py')):
        names.update(re.findall(r'def (test_\w+)', test_file.read_text(encoding='UTF-8')))
    return sorted(names)


def grade(fixture: pathlib.Path, workdir: pathlib.Path) -> list[dict]:
    """Copy the fixture to `workdir`, grade it, and return the feedback rows."""
    checkout = workdir / fixture.name
    shutil.copytree(fixture, checkout, ignore=shutil.ignore_patterns(EXPECTATION_FILENAME))
    return grade_checkout(checkout, case_names(fixture))['feedback']


def expectation(fixture: pathlib.Path) -> dict:
    """The recorded expectation for a fixture."""
    return json.loads((fixture / EXPECTATION_FILENAME).read_text(encoding='UTF-8'))


def matches(want, got) -> bool:
    """Whether one recorded cell still describes what the engine produced.

    A cell is either a literal, or `{"contains": [...]}` for the few whose text
    is quoted from CPython itself — the wording of a SyntaxError or an
    ImportError can differ between the Python versions the CI matrix covers, so
    those pin the fragments that carry the meaning instead of the sentence.
    """
    if isinstance(want, dict):
        return all(fragment in got for fragment in want['contains'])
    return want == got


def mismatches(expected: dict, actual: list[dict]) -> list[str]:
    """Human-readable differences between a recorded and a fresh grading."""
    rows = expected['cases']
    if len(rows) != len(actual):
        return [f'{len(rows)} cases recorded, {len(actual)} graded']

    problems = []
    for want, got in zip(rows, actual):
        for field, value in want.items():
            if not matches(value, got[field]):
                problems.append(f'{want["name"]}.{field}: {got[field]!r} does not match {value!r}')
    return problems
