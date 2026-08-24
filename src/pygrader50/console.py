"""Terminal output helpers shared by the runners.

The Actions log renders ANSI codes, so the console output stays colored while
`release-body.md` (Markdown) never sees them.
"""

import os
import sys


class bcolors:  # pylint: disable=invalid-name,too-few-public-methods
    """ANSI escape codes used across the grader output.

    Lower-case name kept from pygrader so existing autograders read the same.
    """

    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


RULE = '#' * 80


def section(title: str, color: str = bcolors.HEADER) -> None:
    """Print a framed section header."""
    print('\n')
    print(f'{color}{RULE}{bcolors.ENDC}')
    print(f'{color}{bcolors.BOLD}{title}{bcolors.ENDC}')
    print(f'{color}{RULE}{bcolors.ENDC}')


def info(message: str) -> None:
    """Print an informational line."""
    print(f'{bcolors.OKCYAN}{message}{bcolors.ENDC}')


def warn(message: str) -> None:
    """Warning that also shows up as an annotation in the Actions UI."""
    print(f'::warning::{message}')


def error(message: str) -> None:
    """Error that also shows up as an annotation in the Actions UI."""
    print(f'::error::{message}', file=sys.stderr)


def fail(message: str) -> None:
    """Print an error line in red."""
    print(f'{bcolors.FAIL}{message}{bcolors.ENDC}')


def ok(message: str) -> None:
    """Print a success line in green."""
    print(f'{bcolors.OKGREEN}{bcolors.BOLD}{message}{bcolors.ENDC}')


def step_summary(text: str) -> None:
    """Append `text` to `$GITHUB_STEP_SUMMARY`, if the runner set it.

    Lives next to the `::warning::` / `::error::` writers above: this is the
    same layer — output that only GitHub Actions reads. A local run has the
    variable unset and simply writes nothing.
    """
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    try:
        with open(path, 'a', encoding='UTF-8') as handle:
            handle.write(text)
    except OSError as exc:
        warn(f'Job-Summary nicht schreibbar ({exc})')


def points(scored: float, maximum: float) -> None:
    """Print the exact (unrounded) score of a section."""
    print(
        f'{bcolors.OKCYAN}{bcolors.BOLD}🏆 Points: '
        f'{scored:.2f}/{maximum:.2f}{bcolors.ENDC}'
    )
