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
from typing import NamedTuple

import pytest
from _pytest.config import ExitCode

from .config import Testcase
from .console import bcolors, fail, points, section

CATEGORY = 'pytest'
TITLE = 'Unittests'

# How much of the student's own output to echo under a failed case. The number
# is the one GitHub Classroom's Python grader settled on: long enough for a few
# debug prints, short enough to keep the log readable.
OUTPUT_LIMIT = 500

# How much of pytest's own excerpt around the failure to echo. Longer than the
# student's output: this is the source line, the values and the frames that led
# there — the part that answers "why". A runaway recursion still must not turn
# one case into a megabyte of log.
DETAIL_LIMIT = 4000

# Fields of a feedback entry that reach the student and must not carry the
# runner's absolute paths.
STUDENT_FIELDS = ('feedback', 'expected', 'actual')


class Outcome(NamedTuple):
    """What one graded case produced: status, feedback entry, console text."""

    status: str
    result: dict
    message: str
    detail: str = ''
    output: str = ''


class Discard:
    """Sink for pytest's terminal report, which nothing here reads.

    A `StringIO` would assemble every rendered traceback in memory only to drop
    it when the case ends.
    """

    encoding = 'UTF-8'

    def write(self, text: str) -> int:
        """Accept the text and forget it."""
        return len(text)

    def flush(self) -> None:
        """Nothing is buffered."""

    def isatty(self) -> bool:
        """Never a terminal, so pytest renders without control codes."""
        return False


class CaseCollector:
    """Everything one `-k` selected pytest run produced.

    One slot per thing the verdict can rest on, not a list of everything: `-k`
    matches by substring and a test may have many subtests, so keeping every
    report would hold dozens of tracebacks and their captured output alive at
    once.
    """

    def __init__(self) -> None:
        self.failed = None
        self.call = None
        self.skipped = None
        self.comparison: tuple[str, object, object] | None = None
        self.excinfo = None

    @property
    def verdict(self):
        """The report that decides the case, or None if nothing ever ran.

        A failing phase wins — a broken fixture is the verdict even though the
        call never happened. Otherwise the call phase, and a case skipped before
        it ever got there falls back to the phase that recorded the skip.
        """
        return self.failed or self.call or self.skipped

    def pytest_runtest_logreport(self, report) -> None:
        """Keep the first report of each kind the verdict can rest on."""
        if report.failed and self.failed is None:
            self.failed = report
        elif report.skipped and self.skipped is None:
            self.skipped = report
        if report.when == 'call' and self.call is None:
            self.call = report

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
        """Record the first failed comparison without claiming its rendering.

        `tryfirst` plus a `None` return is deliberate on both ends: the hook is
        `firstresult`, so returning a value would suppress pytest's own diff,
        and running last would let a conftest.py in the student checkout hide
        the values from us.
        """
        if self.comparison is None:
            self.comparison = (op, left, right)
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
        with redirect_stdout(Discard()):
            exitcode = pytest.main(args, plugins=[collector])

        outcome = _evaluate(case, collector, exitcode)
        if outcome.status == 'passed':
            passed_cases += 1

        _case_header(case.name, number, len(cases), outcome.status)
        if outcome.message:
            fail(outcome.message)
        if outcome.detail:
            print(f'{bcolors.OKBLUE}Details from pytest:{bcolors.ENDC}')
            print(outcome.detail)
            print()
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
    """Classify one finished case and strip the checkout path from its texts.

    Sanitizing here rather than in each branch is the point: every string that
    reaches the student passes through this one place, so a new branch cannot
    forget it and leak `/home/runner/work/...` into the feedback table.
    """
    outcome = _classify(case, collector, exitcode)
    for field in STUDENT_FIELDS:
        outcome.result[field] = _relative(str(outcome.result[field]))
    return outcome._replace(
        message=_relative(outcome.message), detail=_relative(outcome.detail)
    )


def _classify(case: Testcase, collector: CaseCollector, exitcode) -> Outcome:
    """Status, feedback entry and console text for one finished case."""
    result = _initial_result(case)
    report = collector.verdict

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
    return _failed(collector, result, report)


def _without_report(result: dict, collector: CaseCollector, exitcode) -> Outcome:
    """Outcome of a run that never reached a runtest phase.

    For the three states a beginner hits most — a syntax error, a function they
    never defined, an empty solution file — this cell is the whole feedback, so
    it names the exception instead of an exit code.
    """
    if collector.excinfo is not None:
        # The whole message, not just its first line: a template can raise an
        # ImportError with a hand-written hint spanning several lines, and that
        # hint is the most useful thing the student will read all run.
        reason = _exception_reason(collector.excinfo)
        result['feedback'] = _summary('Test file could not be loaded', _single_line(reason))
        # The wrapper pytest raised is the rendered traceback of the import —
        # useless in a table cell, but exactly what belongs in the log.
        return Outcome('error', result, reason,
                       _truncate(str(collector.excinfo.value), DETAIL_LIMIT))
    if exitcode not in (ExitCode.OK, ExitCode.NO_TESTS_COLLECTED):
        result['feedback'] = f'Unknown error "{exitcode}", check GitHub Actions for details'
        return Outcome('error', result, str(exitcode))
    result['feedback'] = 'This test was not executed, maybe the name was wrong?'
    return Outcome('not_run', result, '')


def _phase_error(result: dict, report) -> Outcome:
    """Outcome of a failure outside the call phase — a fixture, a teardown."""
    message = _crash_message(report)
    result['feedback'] = _summary(
        f'Error during {report.when}', _first_line(message),
        fallback=f'Error during {report.when}, check GitHub Actions for details',
    )
    return Outcome('error', result, message, _crash_detail(report), _captured(report))


def _skipped(case: Testcase, result: dict, report) -> Outcome:
    """Outcome of a case pytest skipped.

    An xfail arrives as a skip carrying `wasxfail`; failing on purpose is what
    the case asked for, so it scores.
    """
    if hasattr(report, 'wasxfail'):
        result['feedback'] = 'Success: Fails as expected'
        result['points'] = case.points
        return Outcome('passed', result, '')
    result['feedback'] = _summary('Test was skipped at this time', _skip_reason(report))
    return Outcome('skipped', result, '')


def _failed(collector: CaseCollector, result: dict, report) -> Outcome:
    """Outcome of a failed call phase.

    A comparison recorded by the hook gives the student the two values; without
    one (a raised exception, a `unittest` assertion, a timeout) the crash line
    is all there is.
    """
    if collector.comparison is not None:
        operator, left, right = collector.comparison
        # `==` is the overwhelming case and reads fine bare. For anything else
        # the two values alone are a riddle: a failed `!=` would otherwise
        # claim expected 5, actual 5.
        expected = str(right) if operator == '==' else f'{operator} {right}'
        actual = str(left)
        result.update({
            'feedback': _summary(
                'Assertion Error', _location(report), template='{stem} ({detail})'
            ),
            'expected': expected,
            'actual': actual,
        })
        message = f'Expected :\t {expected}\nActual :\t {actual}\n'
        return Outcome('failed', result, message, _crash_detail(report), _captured(report))

    message = _crash_message(report)
    result['feedback'] = _summary(
        'Test failed', _first_line(message),
        fallback='Test failed, check GitHub Actions for more details.',
    )
    return Outcome('failed', result, message, _crash_detail(report), _captured(report))


def _initial_result(case: Testcase) -> dict:
    return {
        'name': case.name,
        'feedback': '',
        'expected': '',
        'actual': '',
        'points': 0,
        'max': case.points,
    }


def _summary(stem: str, detail: str, *, fallback: str = '',
             template: str = '{stem} - {detail}') -> str:
    """A feedback sentence: the stem, plus the detail when there is one.

    Every student-facing line is joined here, so the wording the fixture corpus
    guards can be reviewed in one place.
    """
    if not detail:
        return fallback or stem
    return template.format(stem=stem, detail=detail)


def _exception_reason(excinfo) -> str:
    """`Type: message` of the exception that actually broke the import.

    pytest wraps an import failure in a `CollectError` whose message is the
    rendered traceback — unusable in a table cell. The `raise ... from` chain
    still carries the SyntaxError or ImportError underneath, and that one line
    is the whole story for the student. Templates raise their own hints with
    `from None`, so unwrapping to the root keeps them.
    """
    error = excinfo.value
    for _ in range(10):  # bounded: a cyclic __cause__ must not hang the grader
        cause = getattr(error, '__cause__', None)
        if cause is None:
            break
        error = cause
    return f'{type(error).__name__}: {error}'


def _reprcrash(report):
    """pytest's record of where a run died, or None.

    `longrepr.reprcrash` is not part of pytest's public API. It is still a far
    steadier target than the wording of the summary line — this one accessor is
    the whole surface that would have to move if it ever changes.
    """
    return getattr(report.longrepr, 'reprcrash', None)


def _crash_detail(report) -> str:
    """pytest's own excerpt around the failure: source line, values, frames.

    This is what the terminal report used to carry and nobody could read — the
    whole run went into a buffer the grader parsed for a verdict and dropped.
    """
    return _truncate(str(report.longrepr or ''), DETAIL_LIMIT)


def _crash_message(report) -> str:
    """The reason pytest recorded for a crash, or the whole representation."""
    crash = _reprcrash(report)
    message = getattr(crash, 'message', '') if crash is not None else ''
    return (message or str(report.longrepr or '')).strip()


def _location(report) -> str:
    """`file:line` of the failing assertion, or '' when pytest recorded none."""
    crash = _reprcrash(report)
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
    those along with pytest's chatter left them nothing to look at. `capstdout`
    rebuilds the whole capture on every access, so it is read once — a print in
    a loop is exactly the bug this exists for.
    """
    return _truncate(getattr(report, 'capstdout', ''), OUTPUT_LIMIT)


def _truncate(text: str, limit: int) -> str:
    """`text` without surrounding blank lines, cut visibly when it is too long."""
    if len(text) > limit:
        return f'{text[:limit].strip()}\n[... truncated at {limit} characters]'
    return text.strip()


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
