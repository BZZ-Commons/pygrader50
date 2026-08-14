"""Render the Markdown feedback the student actually reads.

Goes into `release-body.md`, which the runner publishes as the release
description and mirrors to the workflow's job summary. The table layout is the
one from pygrader, so the feedback students know does not change.
"""

from __future__ import annotations

from .env import Identity


def escape(value) -> str:
    """Make a cell safe for a Markdown table."""
    return str(value).replace('|', '\\|').replace('\n', ' ').strip()


def table(rows: list[dict]) -> str:
    """Render a list of uniform dicts as a Markdown table."""
    if not rows:
        return ''
    headers = list(rows[0].keys())
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(escape(row.get(header, '')) for header in headers) + ' |')
    return '\n'.join(lines) + '\n'


def section(result: dict) -> str:
    """One graded section (Unittests, Linting) with its table and subtotal."""
    scored, maximum = result['points'], result['max']
    percent = (scored / maximum * 100) if maximum else 0.0
    parts = [f'## {result["name"]}\n']
    body = table(result['feedback'])
    if body:
        parts.append(body)
    parts.append(f'\n**{scored:.2f}/{maximum:.2f} Points ({percent:.2f}%)**\n')
    parts.append('\n---\n')
    return ''.join(parts)


def release_body(identity: Identity, sections: list[dict], payload: dict) -> str:
    """The complete `release-body.md`."""
    parts = [
        f'### classroom50 autograde: {payload["score"]}/{payload["max-score"]}\n\n',
    ]
    exact = sum(section_result['points'] for section_result in sections)
    exact_max = sum(section_result['max'] for section_result in sections)
    if round(exact) != exact or round(exact_max) != exact_max:
        parts.append(
            f'_Exakt: {exact:.2f}/{exact_max:.2f} Punkte — '
            'im Gradebook auf ganze Punkte gerundet._\n\n'
        )
    for section_result in sections:
        parts.append(section(section_result))
    parts.append(f'\n[Änderungen ansehen]({identity.review_url})\n')
    return ''.join(parts)


def no_config_body(identity: Identity) -> str:
    """Body used when no grading configuration was found at all."""
    return (
        '### classroom50 autograde: 0/0\n\n'
        f'_Für `{identity.assignment}` ist keine Bewertungs-Konfiguration hinterlegt '
        '(`unittests.json` / `lint.json`). Die Abgabe wurde aufgezeichnet, aber nicht '
        'bewertet — bitte die Lehrperson informieren._\n\n'
        f'[Änderungen ansehen]({identity.review_url})\n'
    )
