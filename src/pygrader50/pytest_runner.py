"""Run the declared pytest cases one at a time and score them.

Each case from unittests.json is executed as its own `pytest.main()` invocation
selected by `-k <function>`, so one hanging or crashing test cannot take the
others down and every case gets its own timeout.

The expected/actual values in the feedback come from the `pytest_assertrepr_compare`
hook in `data/conftest.py`, which is copied into the student checkout before the
run.
"""

from __future__ import annotations

import sys
from io import StringIO

import pytest
from _pytest.config import ExitCode

from .config import Testcase
from .console import bcolors, points, section

CATEGORY = 'pytest'
TITLE = 'Unittests'


class Capturing(list):
    """Capture stdout of a block into a list of lines."""

    def __init__(self, *args):
        super().__init__(*args)
        self._stdout = None
        self._stringio = None

    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio
        sys.stdout = self._stdout


def run(cases: list[Testcase]) -> dict:
    """Execute every case and return the section result."""
    results = {'category': CATEGORY, 'name': TITLE, 'points': 0, 'max': 0, 'feedback': []}
    if not cases:
        return results

    section(f'Running {len(cases)} Tests')

    passed_cases = 0
    for number, case in enumerate(cases, start=1):
        result = _initial_result(case)
        args = [
            '-k', case.function,
            '--disable-warnings',
            f'--timeout={case.timeout}',
            '--timeout-method=signal',
            '-q',
        ]

        with Capturing() as output:
            exitcode = pytest.main(args)

        if exitcode == ExitCode.OK:
            passed_cases += 1
            summary = output[-1] if output else ''
            if 'xfailed' in summary:
                result['feedback'] = 'Success: Fails as expected'
                result['points'] = case.points
                _case_header(case.name, number, len(cases), 'passed')
            elif 'skipped' in summary:
                result['feedback'] = 'Test was skipped at this time'
                _case_header(case.name, number, len(cases), 'skipped')
            else:
                result['feedback'] = 'Success'
                result['points'] = case.points
                _case_header(case.name, number, len(cases), 'passed')
        elif exitcode == ExitCode.TESTS_FAILED:
            _case_header(case.name, number, len(cases), 'failed')
            message = _error_message(output, result)
            if message:
                print(f'{bcolors.FAIL}{message}{bcolors.ENDC}')
        elif exitcode == ExitCode.NO_TESTS_COLLECTED:
            result['feedback'] = 'This test was not executed, maybe the name was wrong?'
            _case_header(case.name, number, len(cases), 'not_run')
        else:
            result['feedback'] = f'Unknown error "{exitcode}", check GitHub Actions for details'
            _case_header(case.name, number, len(cases), 'error')
            print(f'{bcolors.FAIL}{output}{bcolors.ENDC}')

        results['points'] += result['points']
        results['max'] += result['max']
        results['feedback'].append(result)

    print('\n')
    print(
        f'{bcolors.OKCYAN}{bcolors.BOLD}🏆 Grand total tests passed: '
        f'{passed_cases}/{len(cases)}{bcolors.ENDC}'
    )
    points(results['points'], results['max'])
    return results


def _initial_result(case: Testcase) -> dict:
    return {
        'name': case.name,
        'feedback': '',
        'expected': '',
        'actual': '',
        'points': 0,
        'max': case.points,
    }


def _case_header(test_name: str, current: int, total: int, status: str) -> None:
    styles = {
        'passed': (bcolors.OKGREEN, '✅', 'Test Passed'),
        'failed': (bcolors.FAIL, '❌', 'Test Failed'),
        'skipped': (bcolors.WARNING, '💤', 'Skipped Test'),
        'not_run': (bcolors.FAIL, '⛔', 'Test not run, contact your teacher'),
    }
    color, icon, message = styles.get(status, (bcolors.FAIL, '❌', 'Unknown Status'))
    section(f'{icon} {message}: {test_name} {current}/{total}', color=color)


def _error_message(output: list[str], result: dict) -> str:
    """Pull the assertion details out of the captured pytest output."""
    message = ''
    try:
        comparison = next((line for line in output if 'Comparing values:' in line), None)
        if comparison:
            index = output.index(comparison)
            result['feedback'] = 'Assertion Error'
            result['expected'] = (
                output[index + 1].split(':', 1)[1].strip() if index + 1 < len(output) else 'N/A'
            )
            result['actual'] = (
                output[index + 2].split(':', 1)[1].strip() if index + 2 < len(output) else 'N/A'
            )
            message += f'Expected :\t {result["expected"]}\n'
            message += f'Actual :\t {result["actual"]}\n'
            return message

        for line in output:
            if len(line) > 1 and line[0] == 'E' and not line[1].isalpha():
                stripped = line[1:].strip()
                if stripped and stripped[0] != '[':
                    message += f'{stripped}\n'
        try:
            details = output[-2].split('-')[1].strip()
            result['feedback'] = f'Test failed - {details}'
        except (IndexError, ValueError):
            result['feedback'] = 'Test failed, check GitHub Actions for more details.'
    except Exception:  # pylint: disable=broad-except
        result['feedback'] = 'Test failed, run local pytest for more infos'
        message = message or 'Test failed, run local pytest for more infos'
    return message
