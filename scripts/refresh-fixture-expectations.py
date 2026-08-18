#!/usr/bin/env python3
"""Record what the engine currently produces for every vendored fixture.

    python scripts/refresh-fixture-expectations.py [--check] [fixture ...]

Writes `tests/fixtures/<name>/expected.json`. This is a snapshot: run it only
after reading the diff and agreeing that the new output is the better one — the
whole point of the corpus is that a change in student-facing wording has to be
seen and accepted, not absorbed silently.

`--check` writes nothing and only reports which fixtures drifted, which is what
`test_fixture_corpus.py` enforces in CI.
"""

import argparse
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tests'))

import fixture_corpus  # noqa: E402  pylint: disable=wrong-import-position

FIELDS = ('name', 'feedback', 'expected', 'actual', 'points')


def record(rows: list[dict], previous: dict | None) -> dict:
    """Fresh expectation, keeping every cell a human pinned as `contains`.

    Only those cells are hand-maintained; points, case list and the rest of a
    pinned fixture are regenerated like anywhere else.
    """
    pinned = {case['name']: case for case in (previous or {}).get('cases', [])}
    cases = []
    for row in rows:
        recorded = {field: row[field] for field in FIELDS}
        for field, value in pinned.get(row['name'], {}).items():
            if isinstance(value, dict):
                recorded[field] = value
        cases.append(recorded)
    return {'cases': cases}


def main() -> int:
    """Refresh or check every requested fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('names', nargs='*', help='fixture directories, default all')
    parser.add_argument('--check', action='store_true', help='report drift, write nothing')
    arguments = parser.parse_args()

    selected = [
        fixture for fixture in fixture_corpus.fixtures()
        if not arguments.names or fixture.name in arguments.names
    ]
    if not selected:
        print('no fixture matched', file=sys.stderr)
        return 1

    drifted = 0
    for fixture in selected:
        with tempfile.TemporaryDirectory() as workdir:
            rows = fixture_corpus.grade(fixture, pathlib.Path(workdir))
        path = fixture / fixture_corpus.EXPECTATION_FILENAME
        previous = fixture_corpus.expectation(fixture) if path.is_file() else None
        problems = fixture_corpus.mismatches(previous, rows) if previous else ['no expectation']

        if not problems:
            print(f'unchanged  {fixture.name}')
            continue

        drifted += 1
        if arguments.check:
            print(f'DRIFT      {fixture.name}')
            for problem in problems:
                print(f'             {problem}')
            continue

        document = record(rows, previous)
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='UTF-8')
        print(f'written    {fixture.name}')

    if arguments.check and drifted:
        print(f'\n{drifted} fixture(s) drifted', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
