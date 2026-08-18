"""Run the declared pytest cases one at a time and score them.

Each case from unittests.json is executed as its own `pytest.main()` invocation
selected by `-k <function>`, so one hanging or crashing test cannot take the
others down and every case gets its own timeout.

The expected/actual values in the feedback come from the `pytest_assertrepr_compare`
hook in `data/conftest.py`, which is copied into the student checkout before the
run.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO

import pytest
from _pytest.config import ExitCode

from .config import Testcase
from .console import bcolors, points, section

CATEGORY = 'pytest'
TITLE = 'Unittests'


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

        buffer = StringIO()
        with redirect_stdout(buffer):
            exitcode = pytest.main(args)
        output = buffer.getvalue().splitlines()

        status, message = 'error', ''
        if exitcode == ExitCode.OK:
            passed_cases += 1
            summary = output[-1] if output else ''
            if 'skipped' in summary:
                status = 'skipped'
                result['feedback'] = 'Test was skipped at this time'
            else:
                status = 'passed'
                result['feedback'] = (
                    'Success: Fails as expected' if 'xfailed' in summary else 'Success'
                )
                result['points'] = case.points
        elif exitcode == ExitCode.TESTS_FAILED:
            status = 'failed'
            details = _assertion_details(output)
            if details is None:
                result['feedback'] = _failure_summary(output)
                message = _failure_lines(output)
            else:
                result.update(details)
                message = (
                    f'Expected :\t {details["expected"]}\n'
                    f'Actual :\t {details["actual"]}\n'
                )
        elif exitcode == ExitCode.NO_TESTS_COLLECTED:
            status = 'not_run'
            result['feedback'] = 'This test was not executed, maybe the name was wrong?'
        else:
            result['feedback'] = f'Unknown error "{exitcode}", check GitHub Actions for details'
            message = str(output)

        _case_header(case.name, number, len(cases), status)
        if message:
            print(f'{bcolors.FAIL}{message}{bcolors.ENDC}')

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


def _assertion_details(output: list[str]) -> dict | None:
    """Expected and actual value from the comparison hook, or None if absent.

    The two lines come from `pytest_assertrepr_compare` in `data/conftest.py`,
    which is copied into the checkout before the run.
    """
    index = next((i for i, line in enumerate(output) if 'Comparing values:' in line), None)
    if index is None:
        return None
    return {
        'feedback': 'Assertion Error',
        'expected': _value_at(output, index + 1),
        'actual': _value_at(output, index + 2),
    }


def _value_at(output: list[str], index: int) -> str:
    """The value behind the colon on that line, or 'N/A' when it is not there."""
    if index >= len(output) or ':' not in output[index]:
        return 'N/A'
    return output[index].split(':', 1)[1].strip()


def _failure_lines(output: list[str]) -> str:
    """The `E   ...` lines pytest prints for a failure, one per line."""
    collected = []
    for line in output:
        if len(line) > 1 and line[0] == 'E' and not line[1].isalpha():
            stripped = line[1:].strip()
            if stripped and stripped[0] != '[':
                collected.append(stripped)
    return ''.join(f'{line}\n' for line in collected)


def _failure_summary(output: list[str]) -> str:
    """The short reason from pytest's summary line, or a generic fallback."""
    if len(output) >= 2 and '-' in output[-2]:
        details = output[-2].split('-')[1].strip()
        if details:
            return f'Test failed - {details}'
    return 'Test failed, check GitHub Actions for more details.'
