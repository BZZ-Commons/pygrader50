import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))

from pygrader50.env import Identity  # noqa: E402

# The vendored example repositories are graded by the engine, never collected as
# tests of ours — half of them do not even import.
collect_ignore_glob = ['fixtures/*']


@pytest.fixture
def identity(tmp_path):
    return Identity(
        classroom='m323-ix24',
        assignment='m323-lu01-a02-imperativer-ggt',
        owner='graphics80',
        assignment_type='individual',
        submission_tag='submit/2026-08-13T08-41-09Z-35bdcb2',
        commit_url='https://github.com/o/r/commit/abc',
        release_url='https://github.com/o/r/releases/tag/submit%2Fx',
        review_url='https://github.com/o/r/compare/a...b',
        workspace=tmp_path,
        runner_temp=None,
    )
