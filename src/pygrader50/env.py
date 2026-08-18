"""Identity of a grading run, as handed over by the Classroom 50 runner.

`runner.py` execs the entrypoint with cwd set to the student checkout and these
variables in the environment (see the Autograders wiki page):

    CLASSROOM, ASSIGNMENT, SUBMISSION_TAG, USERNAME / OWNER, ASSIGNMENT_TYPE,
    COMMIT_URL, RELEASE_URL, REVIEW_URL, PAGES_BASE_URL, all GITHUB_* vars

`owner`, `assignment_type` and the timestamps are re-stamped by the runner after
we exit, but they still have to be present and correct or `validate_result`
rejects the payload.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

REQUIRED = ('CLASSROOM', 'ASSIGNMENT', 'SUBMISSION_TAG')


class MissingEnvironment(RuntimeError):
    """Raised when the run is not driven by the Classroom 50 runner."""


@dataclass(frozen=True)
class Identity:  # pylint: disable=too-many-instance-attributes
    """Everything the result payload needs about *who* and *what* is graded."""

    classroom: str
    assignment: str
    owner: str
    assignment_type: str
    submission_tag: str
    commit_url: str
    release_url: str
    review_url: str
    workspace: pathlib.Path
    runner_temp: pathlib.Path | None

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> 'Identity':
        """Read the identity of the current run, raising when it is not a runner run."""
        env = dict(os.environ if environ is None else environ)

        missing = [name for name in REQUIRED if not env.get(name, '').strip()]
        if missing:
            raise MissingEnvironment(
                f'missing {", ".join(missing)} — pygrader50 expects to be started by the '
                'Classroom 50 autograde runner'
            )

        repository = env.get('GITHUB_REPOSITORY', '')
        sha = env.get('GITHUB_SHA', '')
        server = env.get('GITHUB_SERVER_URL', 'https://github.com')
        commit_url = env.get('COMMIT_URL') or f'{server}/{repository}/commit/{sha}'

        assignment_type = (env.get('ASSIGNMENT_TYPE') or 'individual').strip().lower()
        if assignment_type not in ('individual', 'group'):
            assignment_type = 'individual'

        runner_temp = env.get('RUNNER_TEMP', '').strip()

        return cls(
            classroom=env['CLASSROOM'].strip(),
            assignment=env['ASSIGNMENT'].strip(),
            owner=(
                env.get('OWNER') or env.get('USERNAME') or env.get('GITHUB_ACTOR') or ''
            ).strip(),
            assignment_type=assignment_type,
            submission_tag=env['SUBMISSION_TAG'].strip(),
            commit_url=commit_url,
            release_url=env.get('RELEASE_URL') or commit_url,
            review_url=env.get('REVIEW_URL') or commit_url,
            workspace=pathlib.Path.cwd(),
            runner_temp=pathlib.Path(runner_temp) if runner_temp else None,
        )
