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

import os
import pathlib
from contextlib import redirect_stdout
from io import StringIO
from typing import NamedTuple

import pytest
from _pytest.config import ExitCode

from .config import Testcase
from .console import bcolors, points, section

CATEGORY = 'pytest'
TITLE = 'Unittests'

# How much of the student's own output to echo under a failed case. The number
# is the one GitHub Classroom's Python grader settled on: long enough for a few
# debug prints, short enough to keep the log readable.
OUTPUT_LIMIT = 500


class Outcome(NamedTuple):
    """What one graded case produced: status, feedback entry, console text."""

    status: str
    result: dict
    message: str
    output: str = ''


class CaseCollector:
    """Everything one `-k` selected pytest run produced.

    Registered as a plugin for a single `pytest.main()` call, so its state
    always belongs to exactly one case.
    """

    def __init__(self) -> None:
        self.reports: list = []
        self.comparisons: list[tuple[str, object, object]] = []
        self.excinfo = None

    def pytest_runtest_logreport(self, report) -> None:
        """Keep every phase report; `_verdict_report` picks the deciding one."""
        self.reports.append(report)

    def pytest_exception_interact(self, call) -> None:
        """Keep the exception itself, the only handle on a collection error.

        A test file that does not import — a syntax error in the solution, a
        function the student never defined, an empty file — fails before any
        runtest phase and produces no report to read. This hook still fires,
        and `excinfo` carries the exception object instead of a rendered
        traceback we would have to parse back apart.
        """
        if self.excinfo is None and call.excinfo is not None:
            self.excinfo = call.excinfo

    # The explicit `return None` below is the hook contract, not a leftover.
    @pytest.hookimpl(tryfirst=True)
    def pytest_assertrepr_compare(self, op, left, right):  # pylint: disable=useless-return
        """Record a failed comparison without claiming the representation.

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

        # pytest's own chatter would drown out the graded sections in the
        # Actions log; what the student's code printed is echoed below instead.
        with redirect_stdout(StringIO()):
            exitcode = pytest.main(args, plugins=[collector])

        outcome = _evaluate(case, collector, exitcode)
        if outcome.status == 'passed':
            passed_cases += 1

        _case_header(case.name, number, len(cases), outcome.status)
        if outcome.message:
            print(f'{bcolors.FAIL}{outcome.message}{bcolors.ENDC}')
        if outcome.output:
            print(f'{bcolors.WARNING}Output of your program:{bcolors.ENDC}')
            print(outcome.output)

        results['points'] += outcome.result['points']
        results['max'] += outcome.result['max']
        results['feedback'].append(outcome.result)

    print('\n')
    print(
        f'{bcolors.OKCYAN}{bcolors.BOLD}🏆 Grand total tests passed: '
        f'{passed_cases}/{len(cases)}{bcolors.ENDC}'
    )
    points(results['points'], results['max'])
    return results


def _evaluate(case: Testcase, collector: CaseCollector, exitcode) -> Outcome:
    """Status, feedback entry and console text for one finished case."""
    result = _initial_result(case)
    report = _verdict_report(collector.reports)

    if report is None:
        return _without_report(result, collector, exitcode)

    if report.skipped:
        return _skipped(case, result, report)

    if report.passed:
        result['feedback'] = 'Success'
        result['points'] = case.points
        return Outcome('passed', result, '')

    if report.when != 'call':
        return _phase_error(result, report)

    fields, message = _failure(collector, report)
    result.update(fields)
    return Outcome('failed', result, message, _captured(report))


def _without_report(result: dict, collector: CaseCollector, exitcode) -> Outcome:
    """Outcome of a run that never reached a runtest phase.

    For the three states a beginner hits most — a syntax error, a function they
    never defined, an empty solution file — this cell is the whole feedback, so
    it names the exception instead of an exit code.
    """
    if collector.excinfo is not None:
        reason = _exception_reason(collector.excinfo)
        # Whole message, not just its first line: a template can raise an
        # ImportError with a hand-written hint spanning several lines, and that
        # hint is the most useful thing the student will read all run.
        result['feedback'] = f'Test file could not be loaded - {_single_line(reason)}'
        return Outcome('error', result, reason)
    if exitcode not in (ExitCode.OK, ExitCode.NO_TESTS_COLLECTED):
        result['feedback'] = f'Unknown error "{exitcode}", check GitHub Actions for details'
        return Outcome('error', result, str(exitcode))
    result['feedback'] = 'This test was not executed, maybe the name was wrong?'
    return Outcome('not_run', result, '')


def _phase_error(result: dict, report) -> Outcome:
    """Outcome of a failure outside the call phase — a fixture, a teardown."""
    message = _crash_message(report)
    reason = _first_line(message)
    result['feedback'] = (
        f'Error during {report.when} - {reason}' if reason
        else f'Error during {report.when}, check GitHub Actions for details'
    )
    return Outcome('error', result, message, _captured(report))


def _skipped(case: Testcase, result: dict, report) -> Outcome:
    """Outcome of a case pytest skipped.

    An xfail arrives as a skip carrying `wasxfail`; failing on purpose is what
    the case asked for, so it scores.
    """
    if hasattr(report, 'wasxfail'):
        result['feedback'] = 'Success: Fails as expected'
        result['points'] = case.points
        return Outcome('passed', result, '')
    reason = _skip_reason(report)
    result['feedback'] = (
        f'Test was skipped at this time - {reason}' if reason
        else 'Test was skipped at this time'
    )
    return Outcome('skipped', result, '')


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
    one (a raised exception, a `unittest` assertion, a timeout) the crash line
    is all there is.
    """
    if collector.comparisons:
        operator, left, right = collector.comparisons[0]
        # `==` is the overwhelming case and reads fine bare. For anything else
        # the two values alone are a riddle: a failed `!=` would otherwise
        # claim expected 5, actual 5.
        expected = str(right) if operator == '==' else f'{operator} {right}'
        actual = str(left)
        where = _location(report)
        return (
            {
                'feedback': f'Assertion Error ({where})' if where else 'Assertion Error',
                'expected': expected,
                'actual': actual,
            },
            f'Expected :\t {expected}\nActual :\t {actual}\n',
        )

    reason = _crash_message(report)
    summary = f'Test failed - {_first_line(reason)}' if reason else (
        'Test failed, check GitHub Actions for more details.'
    )
    return {'feedback': summary}, reason


def _exception_reason(excinfo) -> str:
    """`Type: message` of the exception that actually broke the import.

    pytest wraps an import failure in a `CollectError` whose message is the
    rendered traceback — unusable in a table cell. The `raise ... from` chain
    still carries the SyntaxError or ImportError underneath, and that one line
    is the whole story for the student.
    """
    error = excinfo.value
    for _ in range(10):  # bounded: a cyclic __cause__ must not hang the grader
        cause = getattr(error, '__cause__', None)
        if cause is None:
            break
        error = cause
    return _relative(f'{type(error).__name__}: {error}')


def _crash_message(report) -> str:
    """The reason pytest recorded for a crash, or the whole representation.

    `longrepr.reprcrash` is not part of pytest's public API, but it is a far
    steadier target than the wording of the summary line — hence the fallback.
    """
    crash = getattr(report.longrepr, 'reprcrash', None)
    message = getattr(crash, 'message', '') if crash is not None else ''
    return _relative((message or str(report.longrepr or '')).strip())


def _location(report) -> str:
    """`file:line` of the failing assertion, or '' when pytest recorded none."""
    crash = getattr(report.longrepr, 'reprcrash', None)
    path, line = getattr(crash, 'path', ''), getattr(crash, 'lineno', None)
    if not path or line is None:
        return ''
    return f'{os.path.basename(str(path))}:{line}'


def _skip_reason(report) -> str:
    """The reason behind a skip; pytest reports it as (path, lineno, reason)."""
    longrepr = report.longrepr
    if not isinstance(longrepr, tuple) or len(longrepr) != 3:
        return ''
    reason = str(longrepr[2])
    return reason.split(':', 1)[1].strip() if reason.startswith('Skipped: ') else reason


def _captured(report) -> str:
    """What the student's own code printed, capped at `OUTPUT_LIMIT`.

    Their `print()` calls are the debugging tool they actually have; swallowing
    those along with pytest's chatter left them nothing to look at.
    """
    output = getattr(report, 'capstdout', '').strip()
    if len(output) > OUTPUT_LIMIT:
        return f'{output[:OUTPUT_LIMIT]}\n[... truncated at {OUTPUT_LIMIT} characters]'
    return output


def _relative(text: str) -> str:
    """Drop the checkout path from a message; it means nothing to the student."""
    return text.replace(f'{pathlib.Path.cwd()}{os.sep}', '')


def _single_line(text: str) -> str:
    """Collapse a message to one line so it fits a Markdown table cell."""
    return ' '.join(text.split())


def _first_line(text: str) -> str:
    """The first line with content — a message may open with blank lines."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ''


def _case_header(test_name: str, current: int, total: int, status: str) -> None:
    styles = {
        'passed': (bcolors.OKGREEN, '✅', 'Test Passed'),
        'failed': (bcolors.FAIL, '❌', 'Test Failed'),
        'skipped': (bcolors.WARNING, '💤', 'Skipped Test'),
        'not_run': (bcolors.FAIL, '⛔', 'Test not run, contact your teacher'),
    }
    color, icon, message = styles.get(status, (bcolors.FAIL, '❌', 'Unknown Status'))
    section(f'{icon} {message}: {test_name} {current}/{total}', color=color)
