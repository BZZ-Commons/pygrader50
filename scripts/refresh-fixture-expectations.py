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


def record(rows: list[dict], match: str | None) -> dict:
    """Build the expectation document for one fixture."""
    document: dict = {}
    if match is not None:
        document['match'] = match
    document['cases'] = [{field: row[field] for field in FIELDS} for row in rows]
    return document


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
        match = previous.get('match') if previous else None

        # A `contains` expectation lists substrings a human chose; regenerating
        # it would replace them with the full sentence and quietly undo the
        # portability it was written for. Check it instead.
        if match == 'contains':
            problems = fixture_corpus.mismatches(previous, rows)
            print(f'{"DRIFT     " if problems else "unchanged "} {fixture.name}')
            for problem in problems:
                print(f'             {problem}')
            drifted += 1 if problems else 0
            continue

        document = record(rows, match)
        if previous == document:
            print(f'unchanged  {fixture.name}')
            continue
        drifted += 1
        if arguments.check:
            problems = fixture_corpus.mismatches(previous, rows) if previous else ['no expectation']
            print(f'DRIFT      {fixture.name}')
            for problem in problems:
                print(f'             {problem}')
            continue
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='UTF-8')
        print(f'written    {fixture.name}')

    if arguments.check and drifted:
        print(f'\n{drifted} fixture(s) drifted', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
