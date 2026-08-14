"""Entrypoint executed by the Classroom 50 runner: `python -m pygrader50`.

Contract with runner.py:
  * cwd is the student checkout
  * we write ./result.json (required) and ./release-body.md (optional)
  * exit 0 for every GRADING outcome, including a failed submission
  * exit non-zero only for an infrastructure failure — the runner then records
    the submission as `error`

A missing grading configuration is a grading outcome, not an infrastructure
failure: it produces a 0/0 payload with an explanatory release body, so the
submission is still recorded.
"""

from __future__ import annotations

import shutil
import sys
import traceback
from importlib import resources

from . import config as config_module
from . import pylint_runner, pytest_runner, render, result
from .console import bcolors, info, section, warn
from .env import Identity, MissingEnvironment


def install_conftest(workspace) -> None:
    """Drop our assertion hook into the checkout so failures report values.

    Overwrites any conftest.py in the repository root: the hook is what the
    feedback table depends on, and the file is not part of the student's task.
    """
    source = resources.files('pygrader50.data').joinpath('conftest.py')
    with resources.as_file(source) as path:
        shutil.copyfile(path, workspace / 'conftest.py')


def grade(identity: Identity) -> int:
    """Grade the checkout and write result.json / release-body.md."""
    grading = config_module.load(identity.assignment, identity.runner_temp, identity.workspace)

    if grading.is_empty:
        warn(
            f'no grading configuration found for {identity.assignment} '
            '(unittests.json / lint.json); recording a 0/0 submission'
        )
        payload = result.build(identity, [])
        result.write(identity.workspace, payload, render.no_config_body(identity))
        return 0

    for filename, source in sorted(grading.sources.items()):
        info(f'config: {filename} ← {source}')

    sections = []
    if grading.has_unittests:
        install_conftest(identity.workspace)
        sections.append(pytest_runner.run(grading.cases))
    if grading.has_lint:
        sections.append(pylint_runner.run(grading.lint, grading.pylintrc))

    payload = result.build(identity, sections)
    error = result.validate(
        payload,
        classroom=identity.classroom,
        assignment=identity.assignment,
        assignment_type=identity.assignment_type,
        owner=identity.owner,
    )
    if error is not None:
        # Our own bug, not the student's: fail loudly rather than publishing a
        # payload the gradebook would silently drop.
        print(f'::error::{error}', file=sys.stderr)
        return 1

    result.write(identity.workspace, payload, render.release_body(identity, sections, payload))

    section(
        f'🏆 Total: {payload["score"]}/{payload["max-score"]} Points',
        color=bcolors.OKCYAN,
    )
    return 0


def main() -> int:
    """Entrypoint: exit 0 for any grading outcome, non-zero only on infrastructure failure."""
    try:
        identity = Identity.from_env()
    except MissingEnvironment as exc:
        print(f'::error::{exc}', file=sys.stderr)
        return 1

    info(
        f'pygrader50: classroom={identity.classroom} assignment={identity.assignment} '
        f'owner={identity.owner} submission={identity.submission_tag}'
    )

    try:
        return grade(identity)
    except Exception:  # pylint: disable=broad-except
        traceback.print_exc()
        print('::error::pygrader50 crashed while grading — see the traceback above',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
