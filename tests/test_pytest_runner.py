"""Score real pytest runs and check what lands in the feedback table.

Every case runs the true `pytest_runner.run()` in a subprocess: nesting
`pytest.main()` inside the session that runs these tests would share the module
cache and the assertion-rewrite state between scenarios. The subprocess also
keeps the point of the change honest — the verdict has to come out of pytest
itself, not out of a hand-built report object.
"""

import json
import os
import pathlib
import subprocess
import sys

import pytest

from conftest import SRC

DRIVER = '''\
import json
import sys

from pygrader50 import pytest_runner
from pygrader50.config import Testcase

case = Testcase(name='case', function=sys.argv[2], timeout=int(sys.argv[3]), points=2)
result = pytest_runner.run([case])
with open(sys.argv[1], 'w', encoding='UTF-8') as handle:
    json.dump(result, handle)
'''


def run_case(workspace: pathlib.Path, source: str, *,
             function: str = 'test_case', timeout: int = 10) -> dict:
    """Grade `source` as the single declared case and return its feedback entry."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / 'case_test.py').write_text(source, encoding='UTF-8')
    driver = workspace / 'driver.py'
    driver.write_text(DRIVER, encoding='UTF-8')
    output = workspace / 'section.json'

    env = dict(os.environ)
    env['PYTHONPATH'] = str(SRC)
    completed = subprocess.run(
        [sys.executable, str(driver), str(output), function, str(timeout)],
        cwd=workspace, env=env, capture_output=True, text=True, check=False,
    )
    assert output.is_file(), completed.stderr
    section = json.loads(output.read_text(encoding='UTF-8'))
    return section['feedback'][0]


def test_a_passing_test_scores_the_full_points(tmp_path):
    entry = run_case(tmp_path, 'def test_case():\n    assert 1 == 1\n')

    assert (entry['points'], entry['max']) == (2, 2)
    assert entry['feedback'] == 'Success'


def test_a_failed_comparison_reports_both_values(tmp_path):
    """The columns the students actually read, without the conftest.py copy."""
    entry = run_case(tmp_path, 'def test_case():\n    assert None == 8\n')

    assert entry['feedback'] == 'Assertion Error'
    assert (entry['expected'], entry['actual']) == ('8', 'None')
    assert entry['points'] == 0


def test_a_raised_exception_reports_its_message(tmp_path):
    entry = run_case(tmp_path, 'def test_case():\n    raise ValueError("kaputt")\n')

    assert entry['feedback'].startswith('Test failed - ')
    assert 'kaputt' in entry['feedback']
    assert (entry['expected'], entry['actual'], entry['points']) == ('', '', 0)


def test_a_skipped_test_scores_nothing(tmp_path):
    entry = run_case(
        tmp_path,
        'import pytest\n\n\ndef test_case():\n    pytest.skip("später")\n',
    )

    assert entry['feedback'] == 'Test was skipped at this time'
    assert entry['points'] == 0


def test_an_expected_failure_scores(tmp_path):
    entry = run_case(
        tmp_path,
        'import pytest\n\n\n@pytest.mark.xfail\ndef test_case():\n    assert False\n',
    )

    assert entry['feedback'] == 'Success: Fails as expected'
    assert entry['points'] == 2


def test_an_unexpected_pass_still_scores(tmp_path):
    """Non-strict xfail: pytest lets it through, so we do too."""
    entry = run_case(
        tmp_path,
        'import pytest\n\n\n@pytest.mark.xfail\ndef test_case():\n    assert True\n',
    )

    assert entry['feedback'] == 'Success'
    assert entry['points'] == 2


@pytest.mark.skipif(os.name == 'nt', reason='--timeout-method=signal needs POSIX signals')
def test_a_hanging_test_is_cut_off_and_scores_nothing(tmp_path):
    entry = run_case(
        tmp_path,
        'def test_case():\n    while True:\n        pass\n',
        timeout=1,
    )

    assert entry['points'] == 0
    assert 'Timeout' in entry['feedback']


def test_a_missing_function_is_reported_as_not_run(tmp_path):
    entry = run_case(tmp_path, 'def test_case():\n    assert True\n', function='test_other')

    assert entry['feedback'] == 'This test was not executed, maybe the name was wrong?'
    assert entry['points'] == 0


def test_a_broken_test_file_is_not_reported_as_a_wrong_name(tmp_path):
    """A collection error has no report at all — it must not read as a typo."""
    entry = run_case(tmp_path, 'def test_case(:\n    assert True\n')

    assert entry['points'] == 0
    assert 'Unknown error' in entry['feedback']


def test_a_broken_fixture_is_reported_as_an_error(tmp_path):
    entry = run_case(
        tmp_path,
        'import pytest\n\n\n@pytest.fixture\ndef broken():\n    raise RuntimeError("boom")\n'
        '\n\ndef test_case(broken):\n    assert True\n',
    )

    assert entry['points'] == 0
    assert 'setup' in entry['feedback']


def test_no_cases_yields_an_empty_section(tmp_path):
    workspace = tmp_path / 'empty'
    workspace.mkdir()
    driver = workspace / 'driver.py'
    driver.write_text(
        'import json\nimport sys\n\nfrom pygrader50 import pytest_runner\n\n'
        'with open(sys.argv[1], "w", encoding="UTF-8") as handle:\n'
        '    json.dump(pytest_runner.run([]), handle)\n',
        encoding='UTF-8',
    )
    output = workspace / 'section.json'
    env = dict(os.environ)
    env['PYTHONPATH'] = str(SRC)
    subprocess.run(
        [sys.executable, str(driver), str(output)],
        cwd=workspace, env=env, capture_output=True, text=True, check=True,
    )

    assert json.loads(output.read_text(encoding='UTF-8')) == {
        'category': 'pytest', 'name': 'Unittests', 'points': 0, 'max': 0, 'feedback': [],
    }
