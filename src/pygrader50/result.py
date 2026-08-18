"""Build and validate the `classroom50/result/v1` payload.

The schema is strict and carries no room for extra fields — the CLI and the web
dashboard parse it exactly. Everything human-readable therefore goes into
`release-body.md` (see `render.py`), which the runner mirrors to the job summary
and publishes as the release description.

`validate` is a by-value copy of `runner.py::validate_result`. Keeping it here
means a payload that would be rejected mid-pipeline fails loudly in our own log
instead — and the test suite pins it against the upstream rules.
"""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from .env import Identity

SCHEMA_V1 = 'classroom50/result/v1'
RESULT_FILENAME = 'result.json'
RELEASE_BODY_FILENAME = 'release-body.md'


def test_entries(sections: list[dict]) -> list[dict[str, Any]]:
    """Flatten the section results into the `tests` array of the payload.

    Every pytest case becomes one entry. Linting becomes a single entry whose
    score is the rounded pylint result; it counts as passed as long as it scored
    at all, so a convention message costs points without turning the student's
    commit status red.
    """
    entries: list[dict[str, Any]] = []
    for section in sections:
        if section['category'] == 'pytest':
            entries.extend(
                _entry(case['name'], case['points'], case['max'])
                for case in section['feedback']
            )
        else:
            entries.append(
                _entry(section['name'], section['points'], section['max'], any_point=True)
            )
    return entries


def _entry(name: str, points: float, maximum: float, *, any_point: bool = False) -> dict[str, Any]:
    """One gradebook entry with the score rounded to the integers it demands.

    `any_point` switches the pass rule from "full marks" to "scored at all" —
    the lint entry uses it so a convention message costs points without turning
    the commit status red.
    """
    scored = round(points)
    total = round(maximum)
    return {
        'test-name': name,
        'passed': scored > 0 if any_point else scored >= total,
        'score': scored,
        'max-score': total,
    }


def build(identity: Identity, sections: list[dict],
          when: datetime.datetime | None = None) -> dict[str, Any]:
    """Assemble the v1 payload for a finished grading run."""
    entries = test_entries(sections)
    stamp = (when or datetime.datetime.now(datetime.UTC)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'schema': SCHEMA_V1,
        'classroom': identity.classroom,
        'assignment': identity.assignment,
        'assignment_type': identity.assignment_type,
        'owner': identity.owner,
        'submission': identity.submission_tag,
        'commit': identity.commit_url,
        'release': identity.release_url,
        'review': identity.review_url,
        'datetime': stamp,
        'score': sum(entry['score'] for entry in entries),
        'max-score': sum(entry['max-score'] for entry in entries),
        'tests': entries,
    }


def validate(  # pylint: disable=too-many-return-statements,too-many-branches,too-many-locals
    data: Any, *, classroom: str, assignment: str,
    assignment_type: str, owner: str | None = None,
) -> str | None:
    """None when `data` is v1-shaped, else a human-readable error.

    Deliberately flat: a by-value mirror of the upstream validator, so the two
    can be diffed line by line when Classroom 50 changes its rules.
    """
    if not isinstance(data, dict):
        return f'{RESULT_FILENAME} is not a JSON object'
    if data.get('schema') != SCHEMA_V1:
        return f'{RESULT_FILENAME} schema is {data.get("schema")!r}, want {SCHEMA_V1!r}'
    if data.get('classroom') != classroom:
        return f'{RESULT_FILENAME} classroom is {data.get("classroom")!r}, want {classroom!r}'
    if data.get('assignment') != assignment:
        return f'{RESULT_FILENAME} assignment is {data.get("assignment")!r}, want {assignment!r}'

    result_owner = data.get('owner')
    if not isinstance(result_owner, str) or not result_owner:
        return f"{RESULT_FILENAME} 'owner' must be a non-empty string"
    if owner is not None and result_owner.lower() != owner.lower():
        return f"{RESULT_FILENAME} 'owner' is {result_owner!r}, want {owner!r}"

    if data.get('assignment_type') != assignment_type:
        return (
            f"{RESULT_FILENAME} 'assignment_type' is {data.get('assignment_type')!r}, "
            f'want {assignment_type!r}'
        )

    submission = data.get('submission')
    if not isinstance(submission, str) or not submission.startswith('submit/'):
        return f"{RESULT_FILENAME} 'submission' must be a 'submit/*' string"

    for field in ('commit', 'release', 'review', 'datetime'):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            return f'{RESULT_FILENAME} {field!r} must be a non-empty string'

    score, max_score = data.get('score'), data.get('max-score')
    if isinstance(score, bool) or not isinstance(score, int) or score < 0:
        return f"{RESULT_FILENAME} 'score' must be a non-negative integer"
    if isinstance(max_score, bool) or not isinstance(max_score, int) or max_score < 0:
        return f"{RESULT_FILENAME} 'max-score' must be a non-negative integer"
    if score > max_score:
        return f'{RESULT_FILENAME} score ({score}) > max-score ({max_score})'

    tests = data.get('tests')
    if not isinstance(tests, list):
        return f"{RESULT_FILENAME} 'tests' is not a list"
    for index, entry in enumerate(tests):
        if not isinstance(entry, dict):
            return f"{RESULT_FILENAME} 'tests[{index}]' is not an object"
        name = entry.get('test-name')
        if not isinstance(name, str) or not name:
            return f"{RESULT_FILENAME} 'tests[{index}].test-name' must be a non-empty string"
        if not isinstance(entry.get('passed'), bool):
            return f"{RESULT_FILENAME} 'tests[{index}].passed' must be a boolean"
        scored, maximum = entry.get('score'), entry.get('max-score')
        if isinstance(scored, bool) or not isinstance(scored, int) or scored < 0:
            return f"{RESULT_FILENAME} 'tests[{index}].score' must be a non-negative integer"
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
            return f"{RESULT_FILENAME} 'tests[{index}].max-score' must be a non-negative integer"
        if scored > maximum:
            return f"{RESULT_FILENAME} 'tests[{index}].score' ({scored}) > 'max-score' ({maximum})"
    return None


def write(workspace: pathlib.Path, payload: dict[str, Any], body: str) -> None:
    """Write both output files the runner picks up."""
    (workspace / RESULT_FILENAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='UTF-8'
    )
    (workspace / RELEASE_BODY_FILENAME).write_text(body, encoding='UTF-8')
