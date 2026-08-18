"""Run the declared pytest cases one at a time and score them.

Each case from unittests.json is executed as its own `pytest.main()` invocation
selected by `-k <function>`, so one hanging or crashing test cannot take the
others down and every case gets its own timeout.

The verdict comes from the report objects a `CaseCollector` plugin receives, not
from the terminal output. pytest's `-q` wording is not an API: reading the grade
out of it made a phrasing change in any pytest release able to move everyone's
score without a commit here.
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


class CaseCollector:
    """Everything one `-k` selected pytest run produced.

    Registered as a plugin for a single `pytest.main()` call, so its state
    always belongs to exactly one case.
    """

    def __init__(self) -> None:
        self.reports: list = []
        self.comparisons: list[tuple[str, object, object]] = []

    def pytest_runtest_logreport(self, report) -> None:
        """Keep every phase report; `_verdict_report` picks the deciding one."""
        self.reports.append(report)

    # The explicit `return None` below is the hook contract, not a leftover.
    @pytest.hookimpl(tryfirst=True)
    def pytest_assertrepr_compare(self, op, left, right):  # pylint: disable=useless-return
        """Record the operands of a failed comparison without claiming the repr.

        `tryfirst` plus a `None` return is deliberate on both ends: the hook is
        `firstresult`, so returning a value would suppress pytest's own diff,
        and running last would let a conftest.py in the student checkout hide
        the values from us.
        """
        self.comparisons.append((op, left, right))
        return None


def run(cases: list[Testcase]) -> dict:
    """Execute every case and return the section result."""
    results = {'category': CATEGORY, 'name': TITLE, 'points': 0, 'max': 0, 'feedback': []}
    if not cases:
        return results

    section(f'Running {len(cases)} Tests')

    passed_cases = 0
    for number, case in enumerate(cases, start=1):
        collector = CaseCollector()
        args = [
            '-k', case.function,
            '--disable-warnings',
            f'--timeout={case.timeout}',
            '--timeout-method=signal',
            '-q',
        ]

        # The student's own output would otherwise drown the graded sections in
        # the Actions log; the verdict no longer depends on what lands here.
        with redirect_stdout(StringIO()):
            exitcode = pytest.main(args, plugins=[collector])

        status, result, message = _evaluate(case, collector, exitcode)
        if status == 'passed':
            passed_cases += 1

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


def _evaluate(case: Testcase, collector: CaseCollector, exitcode) -> tuple[str, dict, str]:
    """Status, feedback entry and console message for one finished case."""
    result = _initial_result(case)
    report = _verdict_report(collector.reports)

    if report is None:
        return _without_report(result, exitcode)

    if report.skipped:
        return _skipped(case, result, report)

    if report.passed:
        result['feedback'] = 'Success'
        result['points'] = case.points
        return 'passed', result, ''

    if report.when != 'call':
        reason = _crash_message(report)
        result['feedback'] = f'Error during {report.when}, check GitHub Actions for details'
        return 'error', result, reason

    fields, message = _failure(collector, report)
    result.update(fields)
    return 'failed', result, message


def _without_report(result: dict, exitcode) -> tuple[str, dict, str]:
    """Outcome of a run that never reached a runtest phase.

    A collection error (a syntax error in the test file, an import that raises)
    produces no report at all, so only the exit code separates it from a `-k`
    pattern that matched nothing.
    """
    if exitcode not in (ExitCode.OK, ExitCode.NO_TESTS_COLLECTED):
        result['feedback'] = f'Unknown error "{exitcode}", check GitHub Actions for details'
        return 'error', result, str(exitcode)
    result['feedback'] = 'This test was not executed, maybe the name was wrong?'
    return 'not_run', result, ''


def _skipped(case: Testcase, result: dict, report) -> tuple[str, dict, str]:
    """Outcome of a case pytest skipped.

    An xfail arrives as a skip carrying `wasxfail`; failing on purpose is what
    the case asked for, so it scores.
    """
    if hasattr(report, 'wasxfail'):
        result['feedback'] = 'Success: Fails as expected'
        result['points'] = case.points
        return 'passed', result, ''
    result['feedback'] = 'Test was skipped at this time'
    return 'skipped', result, ''


def _initial_result(case: Testcase) -> dict:
    return {
        'name': case.name,
        'feedback': '',
        'expected': '',
        'actual': '',
        'points': 0,
        'max': case.points,
    }


def _verdict_report(reports: list):
    """The report that decides the case.

    A failing phase wins — a broken fixture is the verdict even though the call
    never ran. Otherwise the call phase, and a case skipped before it ever got
    there falls back to whichever phase recorded the skip.
    """
    for report in reports:
        if report.failed:
            return report
    for report in reports:
        if report.when == 'call':
            return report
    for report in reports:
        if report.skipped:
            return report
    return None


def _failure(collector: CaseCollector, report) -> tuple[dict, str]:
    """Feedback fields and console message for a failed call phase.

    A comparison recorded by the hook gives the student the two values; without
    one (a raised exception, a bare `assert`, a timeout) the crash line is all
    there is.
    """
    if collector.comparisons:
        _, left, right = collector.comparisons[0]
        expected, actual = str(right), str(left)
        return (
            {'feedback': 'Assertion Error', 'expected': expected, 'actual': actual},
            f'Expected :\t {expected}\nActual :\t {actual}\n',
        )

    reason = _crash_message(report)
    summary = f'Test failed - {_first_line(reason)}' if reason else (
        'Test failed, check GitHub Actions for more details.'
    )
    return {'feedback': summary}, reason


def _crash_message(report) -> str:
    """The reason pytest recorded for a crash, or the whole representation.

    `longrepr.reprcrash` is not part of pytest's public API, but it is a far
    steadier target than the wording of the summary line — hence the fallback.
    """
    crash = getattr(report.longrepr, 'reprcrash', None)
    message = getattr(crash, 'message', '') if crash is not None else ''
    return (message or str(report.longrepr or '')).strip()


def _first_line(text: str) -> str:
    """The first line of a possibly multi-line message."""
    lines = text.splitlines()
    return lines[0].strip() if lines else ''


def _case_header(test_name: str, current: int, total: int, status: str) -> None:
    styles = {
        'passed': (bcolors.OKGREEN, '✅', 'Test Passed'),
        'failed': (bcolors.FAIL, '❌', 'Test Failed'),
        'skipped': (bcolors.WARNING, '💤', 'Skipped Test'),
        'not_run': (bcolors.FAIL, '⛔', 'Test not run, contact your teacher'),
    }
    color, icon, message = styles.get(status, (bcolors.FAIL, '❌', 'Unknown Status'))
    section(f'{icon} {message}: {test_name} {current}/{total}', color=color)
