"""Lint the student's files and scale pylint's global note to the configured max.

lint.json controls the run:

    {"files": ["main.py"], "ignore": [], "max": 5}

`files` wins when present; otherwise every *.py in the checkout root is linted
except those matching an `ignore` pattern. Points are `global_note / 10 * max`,
clamped at zero.
"""

from __future__ import annotations

import glob
import pathlib
import re

from pylint import lint
from pylint.reporters import CollectingReporter

from .console import bcolors, points, section

CATEGORY = 'pylint'
TITLE = 'Linting'
DEFAULT_MAX = 10


def run(config: dict, pylintrc: pathlib.Path | None) -> dict:
    """Lint according to `config` and return the section result."""
    results = {
        'category': CATEGORY,
        'name': TITLE,
        'points': 0,
        'max': config.get('max', DEFAULT_MAX),
        'feedback': [],
    }

    options: list[str] = []
    if pylintrc is not None:
        options.append(f'--rcfile={pylintrc}')

    targets = _targets(config)
    if not targets:
        section('Linting: no files to lint', color=bcolors.WARNING)
        return results
    options.extend(targets)

    reporter = CollectingReporter()
    run_result = lint.Run(options, reporter=reporter, exit=False)

    for message in reporter.messages:
        results['feedback'].append(
            {
                'category': message.category,
                'message': f'{message.msg_id} {message.msg}',
                'path': message.path,
                'line': message.line,
            }
        )

    note = run_result.linter.stats.global_note
    results['points'] = max(round(note / 10 * results['max'], 2), 0)

    _print(results, targets)
    return results


def _targets(config: dict) -> list[str]:
    files = config.get('files')
    if files:
        return [name for name in files if pathlib.Path(name).is_file()]

    candidates = glob.glob('*.py')
    for pattern in config.get('ignore') or []:
        regex = re.compile(pattern)
        candidates = [name for name in candidates if not regex.match(name)]
    return sorted(set(candidates))


def _print(results: dict, targets: list[str]) -> None:
    section(f'Linting Files {targets}')
    colors = {
        'error': bcolors.FAIL,
        'warning': bcolors.WARNING,
        'refactor': bcolors.OKBLUE,
        'convention': bcolors.OKCYAN,
    }
    for feedback in results['feedback']:
        color = colors.get(feedback['category'], bcolors.ENDC)
        print(
            f'{color}{feedback["category"]} in {feedback["path"]} '
            f'line {feedback["line"]}: {feedback["message"]}{bcolors.ENDC}'
        )
    points(results['points'], results['max'])
