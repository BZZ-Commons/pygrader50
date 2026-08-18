"""Check the engine against the vendored example repositories.

The corpus comes from GitHub Classroom's own Python grader (see
`fixtures/README.md`); the expectations are ours. It covers what the handwritten
tests do not: unittest-style assertions, missing imports, an empty solution
file, a syntax error, `print()` output, and partial failures across several test
files.
"""

import pytest

import fixture_corpus


@pytest.mark.parametrize(
    'fixture', fixture_corpus.fixtures(), ids=lambda path: path.name
)
def test_fixture_grades_as_recorded(fixture, tmp_path):
    expected = fixture_corpus.expectation(fixture)
    actual = fixture_corpus.grade(fixture, tmp_path)

    problems = fixture_corpus.mismatches(expected, actual)
    assert not problems, f'{fixture.name}:\n  ' + '\n  '.join(problems)
