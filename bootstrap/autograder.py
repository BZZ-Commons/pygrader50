#!/usr/bin/env python3
"""Classroom 50 default autograder for the BZZ Python classrooms.

Install it once per classroom:

    gh teacher autograder set-default <org> <classroom> --from bootstrap/autograder.py

It is published verbatim to the classroom's Pages site as
`<classroom>/autograder.py` and fetched by runner.py on every submission. Pages
serves this single file without siblings, so the grading engine is installed
from PyPI-style git at a PINNED tag: grading stays reproducible, and upgrading a
classroom is a one-line edit here plus a publish-pages run.

Everything else — grading, result.json, release-body.md — lives in
https://github.com/BZZ-Commons/pygrader50
"""

import subprocess
import sys

# The rollout gate: this line is what every student's run installs. Moving it
# reaches them on their next push, so it moves between assignments, never in the
# middle of one, and only together with a `gh teacher autograder set-default`.
VERSION = 'v2.2.2'
PACKAGE = f'pygrader50 @ git+https://github.com/BZZ-Commons/pygrader50@{VERSION}'


def install() -> None:
    """Install the pinned grading engine into the runner's Python."""
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--quiet',
         '--disable-pip-version-check', PACKAGE],
        check=True,
    )


def main() -> int:
    """Install the engine, then hand over to it; its exit code is ours."""
    try:
        install()
    except subprocess.CalledProcessError as exc:
        # Infrastructure failure (network, yanked tag): a non-zero exit makes the
        # runner record the submission as `error` instead of as a zero score.
        print(f'::error::could not install {PACKAGE}: {exc}', file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, '-m', 'pygrader50'], check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
