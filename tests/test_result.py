import pytest

from pygrader50 import result


def pytest_section(cases):
    return {'category': 'pytest', 'name': 'Unittests', 'points': sum(c['points'] for c in cases),
            'max': sum(c['max'] for c in cases), 'feedback': cases}


def lint_section(points, maximum=5):
    return {'category': 'pylint', 'name': 'Linting', 'points': points, 'max': maximum,
            'feedback': []}


def case(name, points, maximum):
    return {'name': name, 'feedback': '', 'expected': '', 'actual': '',
            'points': points, 'max': maximum}


def validate(payload, identity):
    return result.validate(payload, classroom=identity.classroom, assignment=identity.assignment,
                           assignment_type=identity.assignment_type, owner=identity.owner)


def test_build_is_schema_valid(identity):
    payload = result.build(identity, [pytest_section([case('test_ggt', 2, 2)]), lint_section(3.4)])

    assert validate(payload, identity) is None
    assert payload['score'] == 5      # 2 + round(3.4)
    assert payload['max-score'] == 7


def test_lint_counts_as_passed_while_it_scores(identity):
    payload = result.build(identity, [lint_section(0.4)])
    entry = payload['tests'][0]

    assert entry['score'] == 0        # round(0.4)
    assert entry['passed'] is False   # nothing scored -> red

    payload = result.build(identity, [lint_section(1.2)])
    assert payload['tests'][0]['passed'] is True


def test_failed_case_is_not_passed(identity):
    payload = result.build(identity, [pytest_section([case('test_ggt', 0, 2)])])

    assert payload['tests'][0]['passed'] is False
    assert payload['score'] == 0


def test_scores_are_integers(identity):
    payload = result.build(identity, [lint_section(3.4)])

    for value in (payload['score'], payload['max-score'],
                  payload['tests'][0]['score'], payload['tests'][0]['max-score']):
        assert isinstance(value, int) and not isinstance(value, bool)


def test_empty_run_is_a_valid_zero_payload(identity):
    payload = result.build(identity, [])

    assert validate(payload, identity) is None
    assert (payload['score'], payload['max-score'], payload['tests']) == (0, 0, [])


@pytest.mark.parametrize('mutation, fragment', [
    ({'schema': 'other'}, 'schema'),
    ({'owner': 'someone-else'}, 'owner'),
    ({'assignment_type': 'group'}, 'assignment_type'),
    ({'submission': 'v1.0'}, 'submission'),
    ({'score': 99}, 'score'),
    ({'score': 1.5}, 'score'),
    ({'tests': 'nope'}, 'tests'),
    ({'classroom': 'other'}, 'classroom'),
])
def test_validate_rejects(identity, mutation, fragment):
    payload = result.build(identity, [pytest_section([case('test_ggt', 2, 2)])])
    payload.update(mutation)

    error = validate(payload, identity)

    assert error is not None and fragment in error


def test_write_emits_both_files(identity, tmp_path):
    payload = result.build(identity, [])
    result.write(tmp_path, payload, '### body\n')

    assert (tmp_path / result.RESULT_FILENAME).is_file()
    assert (tmp_path / result.RELEASE_BODY_FILENAME).read_text() == '### body\n'
