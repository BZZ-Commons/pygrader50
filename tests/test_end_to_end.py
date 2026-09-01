"""Grade a throwaway student repository through the real entrypoint.

Runs `python -m pygrader50` as a subprocess so the nested pytest session cannot
interfere with the one running these tests — and so the test exercises exactly
what the runner invokes.
"""

import json
import os
import pathlib
import subprocess
import sys

import pytest

from conftest import SRC
from pygrader50 import config

SOLUTION = '''\
"""Berechnet den groessten gemeinsamen Teiler."""


def ggt(first, second):
    """Gibt den groessten gemeinsamen Teiler von first und second zurueck."""
    while second:
        first, second = second, first % second
    return abs(first)
'''

STUB = '''\
def ggt(a, b):
    pass
'''

TEST_FILE = '''\
import main


def test_ggt():
    assert main.ggt(56, 48) == 8
    assert main.ggt(0, 5) == 5
'''

UNITTESTS = [{'name': 'test_ggt', 'function': 'test_ggt', 'timeout': 10, 'points': 2}]
LINT = {'files': ['main.py'], 'ignore': [], 'max': 5}


def build_repo(root: pathlib.Path, source: str) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / 'main.py').write_text(source, encoding='UTF-8')
    (root / 'main_test.py').write_text(TEST_FILE, encoding='UTF-8')
    autograding = root / '.github' / 'autograding'
    autograding.mkdir(parents=True)
    (autograding / 'unittests.json').write_text(json.dumps(UNITTESTS), encoding='UTF-8')
    (autograding / 'lint.json').write_text(json.dumps(LINT), encoding='UTF-8')
    return root


def grade(workspace: pathlib.Path, **overrides):
    env = dict(os.environ)
    env.update(
        {
            'PYTHONPATH': str(SRC),
            'CLASSROOM': 'm323-ix24',
            'ASSIGNMENT': 'm323-lu01-a02-imperativer-ggt',
            'SUBMISSION_TAG': 'submit/2026-08-13T08-41-09Z-35bdcb2',
            'OWNER': 'graphics80',
            'ASSIGNMENT_TYPE': 'individual',
            'COMMIT_URL': 'https://github.com/o/r/commit/abc',
            'RELEASE_URL': 'https://github.com/o/r/releases/tag/submit',
            'REVIEW_URL': 'https://github.com/o/r/compare/a...b',
        }
    )
    env.pop('RUNNER_TEMP', None)
    env.update(overrides)
    completed = subprocess.run(
        [sys.executable, '-m', 'pygrader50'],
        cwd=workspace, env=env, capture_output=True, text=True, check=False,
    )
    payload = workspace / 'result.json'
    return completed, json.loads(payload.read_text()) if payload.is_file() else None


@pytest.fixture(scope='module')
def solved(tmp_path_factory):
    workspace = build_repo(tmp_path_factory.mktemp('solved'), SOLUTION)
    return grade(workspace) + (workspace,)


def test_solution_scores_the_unittest(solved):
    completed, payload, _ = solved

    assert completed.returncode == 0, completed.stderr
    entry = next(t for t in payload['tests'] if t['test-name'] == 'test_ggt')
    assert entry == {'test-name': 'test_ggt', 'passed': True, 'score': 2, 'max-score': 2}


def test_solution_is_schema_valid(solved):
    _, payload, _ = solved

    assert payload['schema'] == 'classroom50/result/v1'
    assert payload['owner'] == 'graphics80'
    assert payload['submission'].startswith('submit/')
    assert payload['max-score'] == 7
    assert isinstance(payload['score'], int)


def test_release_body_carries_the_feedback(solved):
    _, payload, workspace = solved
    body = (workspace / 'release-body.md').read_text()

    assert f'### classroom50 autograde: {payload["score"]}/7' in body
    assert '## Unittests' in body and '## Linting' in body


def test_stub_fails_the_unittest_but_still_records(tmp_path):
    workspace = build_repo(tmp_path / 'stub', STUB)

    completed, payload = grade(workspace)

    assert completed.returncode == 0, completed.stderr
    entry = next(t for t in payload['tests'] if t['test-name'] == 'test_ggt')
    assert entry['passed'] is False and entry['score'] == 0


def test_stub_feedback_shows_the_compared_values(tmp_path):
    """Expected/actual reach the table without a conftest.py in the checkout."""
    workspace = build_repo(tmp_path / 'values', STUB)

    grade(workspace)
    body = (workspace / 'release-body.md').read_text()

    assert '| test_ggt | Assertion Error (main_test.py:5) | 8 | None | 0 | 2 |' in body
    assert not (workspace / 'conftest.py').exists()


def test_bundle_configuration_takes_precedence(tmp_path):
    """The teacher's bundle overrides a student-edited unittests.json."""
    workspace = build_repo(tmp_path / 'tampered', SOLUTION)
    (workspace / '.github' / 'autograding' / 'unittests.json').write_text(
        json.dumps([{'name': 'test_ggt', 'function': 'test_ggt', 'timeout': 10, 'points': 999}]),
        encoding='UTF-8',
    )
    runner_temp = tmp_path / 'runner-temp'
    bundle = runner_temp / config.BUNDLE_SUBDIR / 'm323-lu01-a02-imperativer-ggt'
    bundle.mkdir(parents=True)
    (bundle / 'unittests.json').write_text(json.dumps(UNITTESTS), encoding='UTF-8')
    (bundle / 'lint.json').write_text(json.dumps(LINT), encoding='UTF-8')

    _, payload = grade(workspace, RUNNER_TEMP=str(runner_temp))

    assert payload['max-score'] == 7


def test_missing_configuration_records_a_zero_submission(tmp_path):
    workspace = tmp_path / 'bare'
    workspace.mkdir()

    completed, payload = grade(workspace)

    assert completed.returncode == 0, completed.stderr
    assert (payload['score'], payload['max-score'], payload['tests']) == (0, 0, [])
    assert 'keine Bewertungs-Konfiguration' in (workspace / 'release-body.md').read_text()


def test_missing_environment_is_an_infrastructure_failure(tmp_path):
    workspace = build_repo(tmp_path / 'noenv', SOLUTION)

    completed, payload = grade(workspace, CLASSROOM='')

    assert completed.returncode == 1
    assert payload is None
    assert 'CLASSROOM' in completed.stderr


def test_a_requirements_file_of_grading_pins_changes_nothing(tmp_path):
    """The 63 templates ship exactly these two lines; both must be ignored.

    No pip call happens for this input, so the test needs no package index —
    which is also the point: a normal assignment installs nothing extra.
    """
    workspace = build_repo(tmp_path / 'pins', SOLUTION)
    (workspace / 'requirements.txt').write_text(
        'pylint==4.0.7\npytest==9.1.1\n', encoding='UTF-8'
    )

    completed, payload = grade(workspace)

    assert completed.returncode == 0, completed.stderr
    assert payload['max-score'] == 7
    assert 'pins its own version of pylint==4.0.7, pytest==9.1.1' in completed.stdout
    assert '::warning::' not in completed.stdout
