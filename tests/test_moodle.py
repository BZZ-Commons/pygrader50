import json

import pytest

from pygrader50 import moodle


def submission(**overrides):
    payload = {
        'schema': 'classroom50/result/v1',
        'classroom': 'm323-ix24',
        'assignment_type': 'individual',
        'owner': 'graphics80',
        'submission': 'submit/2026-08-13T08-41-09Z-35bdcb2',
        'commit': 'https://github.com/m323-ix24/m323-ix24-slug-graphics80/commit/abc',
        'release': 'https://github.com/m323-ix24/m323-ix24-slug-graphics80/releases/tag/submit%2Fx',
        'datetime': '2026-08-13T08:40:58Z',
        'graded_at': '2026-08-13T08:41:19Z',
        'score': 5,
        'max-score': 7,
        'tests': [],
    }
    payload.update(overrides)
    return payload


def scores(*submissions, slug='m323-lu01-a02-imperativer-ggt', owner='graphics80'):
    return {
        'schema': 'classroom50/scores/v1',
        'assignments': {
            slug: {'type': 'individual',
                   'entries': [{'owner': owner, 'submissions': list(submissions)}]},
        },
    }


def test_latest_submission_wins():
    document = scores(
        submission(submission='submit/old', datetime='2026-07-09T09:42:58Z', score=1),
        submission(submission='submit/new', datetime='2026-08-13T08:40:58Z', score=5),
    )

    found = moodle.latest_submissions(document)

    assert len(found) == 1
    assert (found[0].submission, found[0].score) == ('submit/new', 5)


def test_filters():
    document = scores(submission())

    assert moodle.latest_submissions(document, assignment='other') == []
    assert moodle.latest_submissions(document, owner='someone-else') == []
    assert len(moodle.latest_submissions(document, owner='GRAPHICS80')) == 1


def test_entries_without_submissions_are_ignored():
    document = scores()

    assert moodle.latest_submissions(document) == []


def test_wrong_schema_raises():
    with pytest.raises(ValueError):
        moodle.latest_submissions({'schema': 'something/else'})


def test_repository_is_derived_from_the_release_url():
    found = moodle.latest_submissions(scores(submission()))[0]

    assert found.repository == 'm323-ix24/m323-ix24-slug-graphics80'


def test_payload_carries_score_and_identity():
    found = moodle.latest_submissions(scores(submission()))[0]

    payload = moodle.build_payload(found, 'Feedback')

    assert payload['assignment_name'] == 'm323-lu01-a02-imperativer-ggt'
    assert payload['user_name'] == 'graphics80'
    assert (payload['points'], payload['max']) == (5, 7)
    assert 'Feedback' in payload['feedback']


def test_late_submissions_are_marked_in_the_feedback():
    found = moodle.latest_submissions(scores(submission(late=True)))[0]

    assert '%E2%8F%B0' in moodle.build_payload(found, '')['feedback']  # ⏰, quotiert


def test_state_skips_unchanged_and_records_new(tmp_path):
    found = moodle.latest_submissions(scores(submission()))[0]
    state = moodle.State(path=tmp_path / 'state.json')

    assert state.is_current(found) is False
    state.record(found)
    assert state.is_current(found) is True

    state.save()
    assert moodle.State.load(tmp_path / 'state.json').is_current(found) is True


def test_state_detects_a_regrade(tmp_path):
    first = moodle.latest_submissions(scores(submission()))[0]
    state = moodle.State(path=tmp_path / 'state.json')
    state.record(first)

    regraded = moodle.latest_submissions(scores(submission(score=7)))[0]

    assert state.is_current(regraded) is False


def test_sync_sends_only_what_changed():
    found = moodle.latest_submissions(scores(submission()))[0]
    state = moodle.State()
    state.record(found)
    calls = []

    sent, skipped, failed = moodle.sync(
        [found], sender=lambda payload: calls.append(payload) or (True, 'ok'),
        feedback_provider=lambda _: '', state=state,
    )

    assert (sent, skipped, failed) == (0, 1, 0)
    assert calls == []


def test_sync_force_resends():
    found = moodle.latest_submissions(scores(submission()))[0]
    state = moodle.State()
    state.record(found)

    sent, skipped, failed = moodle.sync(
        [found], sender=lambda payload: (True, 'ok'),
        feedback_provider=lambda _: '', state=state, force=True,
    )

    assert (sent, skipped, failed) == (1, 0, 0)


def test_sync_reports_failures_without_recording_them():
    found = moodle.latest_submissions(scores(submission()))[0]
    state = moodle.State()

    sent, skipped, failed = moodle.sync(
        [found], sender=lambda payload: (False, 'No matching assignment found'),
        feedback_provider=lambda _: '', state=state,
    )

    assert (sent, skipped, failed) == (0, 0, 1)
    assert state.entries == {}


def test_dry_run_sends_nothing():
    found = moodle.latest_submissions(scores(submission()))[0]
    calls = []

    sent, _, _ = moodle.sync(
        [found], sender=lambda payload: calls.append(payload) or (True, 'ok'),
        feedback_provider=lambda _: '', state=moodle.State(), dry_run=True,
    )

    assert sent == 1 and calls == []


SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<RESPONSE><SINGLE><KEY name="name"><VALUE>success</VALUE></KEY></SINGLE></RESPONSE>"""

ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<RESPONSE><SINGLE><KEY name="message"><VALUE>No matching assignment found.</VALUE></KEY></SINGLE></RESPONSE>"""

# What a REST webservice returns when validate_parameters() rejects a field.
# MESSAGE is localised and says nothing about the cause; ERRORCODE and
# DEBUGINFO do.
EXCEPTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EXCEPTION class="invalid_parameter_exception">
  <ERRORCODE>invalidparameter</ERRORCODE>
  <MESSAGE>Ungueltiger Parameterwert</MESSAGE>
  <DEBUGINFO>externallink: the value is "https://x/tag/submit%2Fy"</DEBUGINFO>
</EXCEPTION>"""

EXCEPTION_XML_NO_DEBUG = """<?xml version="1.0" encoding="UTF-8"?>
<EXCEPTION class="invalid_parameter_exception">
  <ERRORCODE>invalidparameter</ERRORCODE>
  <MESSAGE>Ungueltiger Parameterwert</MESSAGE>
</EXCEPTION>"""


def test_parse_response():
    assert moodle.parse_response(SUCCESS_XML) == (True, 'ok')

    ok, message = moodle.parse_response(ERROR_XML)
    assert ok is False and 'No matching assignment' in message

    ok, message = moodle.parse_response('<html>login required</html>')
    assert ok is False and 'XML' in message


def test_parse_response_keeps_moodle_error_details():
    """The localised message alone never names the rejected field."""
    ok, message = moodle.parse_response(EXCEPTION_XML)
    assert ok is False
    assert 'Ungueltiger Parameterwert' in message
    assert 'errorcode: invalidparameter' in message
    assert 'externallink' in message


def test_parse_response_without_debuginfo():
    """A production Moodle suppresses DEBUGINFO; the errorcode still survives."""
    ok, message = moodle.parse_response(EXCEPTION_XML_NO_DEBUG)
    assert ok is False
    assert 'errorcode: invalidparameter' in message
    assert 'debuginfo' not in message


def test_endpoint_url():
    url = moodle.endpoint_url('https://moodle.example.org/', 'abc123', 'fn')

    assert url.startswith('https://moodle.example.org/webservice/rest/server.php/?')
    assert 'wstoken=abc123' in url and 'wsfunction=fn' in url


def test_cli_requires_credentials(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'scores.json'
    path.write_text(json.dumps(scores(submission())), encoding='UTF-8')
    monkeypatch.delenv('MOODLE_URL', raising=False)
    monkeypatch.delenv('MOODLE_TOKEN', raising=False)

    assert moodle.main([str(path)]) == 1
    assert 'MOODLE_URL' in capsys.readouterr().err


def test_cli_dry_run_works_without_credentials(tmp_path, monkeypatch):
    path = tmp_path / 'scores.json'
    path.write_text(json.dumps(scores(submission())), encoding='UTF-8')
    monkeypatch.delenv('MOODLE_URL', raising=False)
    monkeypatch.delenv('MOODLE_TOKEN', raising=False)

    assert moodle.main([str(path), '--dry-run', '--no-feedback']) == 0
