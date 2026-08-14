import json

import pytest

from pygrader50 import config


def write(directory, name, payload):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload,
                    encoding='UTF-8')
    return path


CASES = [{'name': 'test_ggt', 'function': 'test_ggt', 'timeout': 10, 'points': 2}]


def test_bundle_wins_over_student_repo(tmp_path):
    runner_temp = tmp_path / 'temp'
    workspace = tmp_path / 'repo'
    bundle = runner_temp / config.BUNDLE_SUBDIR / 'slug'
    write(bundle, 'unittests.json', CASES)
    write(workspace / '.github' / 'autograding', 'unittests.json',
          [{'name': 'cheat', 'function': 'test_ggt', 'timeout': 1, 'points': 99}])

    resolved = config.load('slug', runner_temp, workspace)

    assert [case.points for case in resolved.cases] == [2]
    assert resolved.sources['unittests.json'] == str(bundle / 'unittests.json')


def test_student_repo_is_the_fallback(tmp_path):
    workspace = tmp_path / 'repo'
    write(workspace / '.github' / 'autograding', 'unittests.json', CASES)

    resolved = config.load('slug', tmp_path / 'temp', workspace)

    assert resolved.has_unittests
    assert not resolved.has_lint


def test_files_resolve_independently(tmp_path):
    """A bundle may override only unittests.json and leave the rest in the repo."""
    runner_temp = tmp_path / 'temp'
    workspace = tmp_path / 'repo'
    write(runner_temp / config.BUNDLE_SUBDIR / 'slug', 'unittests.json', CASES)
    student = workspace / '.github' / 'autograding'
    write(student, 'lint.json', {'files': ['main.py'], 'max': 5})
    write(student, 'pylintrc', '[MAIN]\n')

    resolved = config.load('slug', runner_temp, workspace)

    assert resolved.lint['max'] == 5
    assert resolved.pylintrc == student / 'pylintrc'


def test_missing_configuration_is_empty_not_an_error(tmp_path):
    resolved = config.load('slug', None, tmp_path)

    assert resolved.is_empty
    assert resolved.sources == {}


def test_fractional_points_are_rounded_at_load_time(tmp_path):
    write(tmp_path / '.github' / 'autograding', 'unittests.json',
          [{'name': 'a', 'function': 'test_a', 'timeout': 1, 'points': 2.6}])

    resolved = config.load('slug', None, tmp_path)

    assert resolved.cases[0].points == 3


def test_malformed_unittests_raise(tmp_path):
    write(tmp_path / '.github' / 'autograding', 'unittests.json', {'not': 'a list'})

    with pytest.raises(ValueError):
        config.load('slug', None, tmp_path)
