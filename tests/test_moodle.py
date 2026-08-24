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


def test_cli_falls_back_to_the_default_function_when_the_variable_is_empty(
    tmp_path, monkeypatch
):
    """An empty MOODLE_FUNCTION must not produce an empty `wsfunction`.

    GitHub Actions sets `MOODLE_FUNCTION: ${{ vars.MOODLE_FUNCTION }}` even when
    the variable does not exist, so the name is present but blank — the default
    of os.environ.get never applies. Moodle answers a blank wsfunction with
    `invalidparameter` / "Missing function name", and only on a real transfer:
    a dry run never builds the endpoint, so this stays invisible until the first
    live run.
    """
    repo = config_repo(tmp_path, 'm323-ix24')
    monkeypatch.setenv('MOODLE_URL', 'https://moodle.example.org')
    monkeypatch.setenv('MOODLE_TOKEN', 'abc123')
    monkeypatch.setenv('MOODLE_FUNCTION', '')

    seen = {}

    def fake_post(endpoint, payload, timeout=30):  # pylint: disable=unused-argument
        seen['endpoint'] = endpoint
        return True, 'ok'

    monkeypatch.setattr(moodle, 'post', fake_post)
    monkeypatch.setattr(moodle, 'release_feedback', lambda submission, token: '')

    assert moodle.main(['--config-repo', str(repo), '--classroom', 'm323-ix24']) == 0
    assert f'wsfunction={moodle.DEFAULT_FUNCTION}' in seen['endpoint']


def test_cli_requires_credentials(tmp_path, monkeypatch, capsys):
    repo = config_repo(tmp_path, 'm323-ix24')
    monkeypatch.delenv('MOODLE_URL', raising=False)
    monkeypatch.delenv('MOODLE_TOKEN', raising=False)

    assert moodle.main(['--config-repo', str(repo), '--classroom', 'm323-ix24']) == 1
    assert 'MOODLE_URL' in capsys.readouterr().err


def test_cli_dry_run_works_without_credentials(tmp_path, monkeypatch):
    repo = config_repo(tmp_path, 'm323-ix24')
    monkeypatch.delenv('MOODLE_URL', raising=False)
    monkeypatch.delenv('MOODLE_TOKEN', raising=False)

    assert moodle.main(['--config-repo', str(repo), '--classroom', 'm323-ix24',
                        '--dry-run', '--no-feedback']) == 0


# --- Scope-Auflösung -------------------------------------------------------
#
# Der Scope ist die äusserste Grenze: er bestimmt, wessen Noten überhaupt
# angefasst werden. Diese Tests halten fest, dass Schweigen ein Abbruch ist und
# nicht »alle« — die Regel lebte vorher in einem Shell-Snippet je Config-Repo
# und war damit weder testbar noch gegen Drift geschützt.


def config_repo(tmp_path, *names, empty_dirs=(), document=None):
    """Ein Config-Repo mit je einer scores.json pro Classroom bauen."""
    for name in names:
        room = tmp_path / name
        room.mkdir(parents=True, exist_ok=True)
        (room / 'scores.json').write_text(
            json.dumps(scores(submission()) if document is None else document), encoding='UTF-8')
    for name in empty_dirs:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(name='moodle_stub')
def fixture_moodle_stub(monkeypatch):
    """Zugangsdaten setzen und die beiden Netzaufrufe abfangen.

    Gibt die Liste der gesendeten Payloads zurück — leer heisst: nichts ging raus.
    """
    monkeypatch.setenv('MOODLE_URL', 'https://moodle.example.org')
    monkeypatch.setenv('MOODLE_TOKEN', 'abc123')
    sent = []

    def fake_post(endpoint, payload, timeout=30):  # pylint: disable=unused-argument
        sent.append(payload)
        return True, 'ok'

    monkeypatch.setattr(moodle, 'post', fake_post)
    monkeypatch.setattr(moodle, 'release_feedback', lambda submission, token: '')
    return sent


def test_scope_without_an_argument_aborts(tmp_path):
    """Ein fehlender Scope darf nicht »alle« heissen."""
    repo = config_repo(tmp_path, 'm323-ix24', 'm450-ix25')
    with pytest.raises(moodle.ScopeError, match='Scope fehlt'):
        moodle.resolve_scope(repo, None, False)


def test_scope_rejects_an_empty_classroom(tmp_path):
    """`--classroom ""` ist derselbe Abbruch wie ein fehlendes Argument.

    Sonst wandert die Lücke nur aus der Shell nach Python: GitHub Actions
    liefert eine nicht ausgefüllte Eingabe als leeren String.
    """
    repo = config_repo(tmp_path, 'm323-ix24')
    with pytest.raises(moodle.ScopeError, match='leer'):
        moodle.resolve_scope(repo, [''], False)
    with pytest.raises(moodle.ScopeError, match='leer'):
        moodle.resolve_scope(repo, ['   '], False)


def test_scope_rejects_the_contradiction(tmp_path):
    repo = config_repo(tmp_path, 'm323-ix24')
    with pytest.raises(moodle.ScopeError, match='schliessen sich aus'):
        moodle.resolve_scope(repo, ['m323-ix24'], True)


def test_scope_named_classroom(tmp_path):
    repo = config_repo(tmp_path, 'm323-ix24', 'm450-ix25')
    rooms = moodle.resolve_scope(repo, ['m323-ix24'], False)
    assert [room.name for room in rooms] == ['m323-ix24']
    assert rooms[0].scores == repo / 'm323-ix24' / 'scores.json'
    assert rooms[0].state == repo / 'm323-ix24' / 'moodle-state.json'


def test_scope_repeated_classrooms_are_deduplicated(tmp_path):
    repo = config_repo(tmp_path, 'a', 'b', 'c')
    rooms = moodle.resolve_scope(repo, ['a', 'b', 'a'], False)
    assert [room.name for room in rooms] == ['a', 'b']


def test_scope_unknown_classroom_is_an_error_not_an_empty_hit(tmp_path):
    """Ein Tippfehler darf nicht wie ein erfolgreicher Lauf aussehen."""
    repo = config_repo(tmp_path, 'm323-ix24')
    with pytest.raises(moodle.ScopeError, match='unbekanntes Classroom'):
        moodle.resolve_scope(repo, ['m323-ix42'], False)


def test_scope_all_classrooms_finds_every_folder_with_scores(tmp_path):
    repo = config_repo(tmp_path, 'm450-ix25', 'm323-ix24',
                       empty_dirs=('.github', 'docs'))
    rooms = moodle.resolve_scope(repo, None, True)
    assert [room.name for room in rooms] == ['m323-ix24', 'm450-ix25']


def test_scope_all_classrooms_without_any_scores_is_a_setup_error(tmp_path):
    """Kein `scores.json` heisst: der Aufruf war richtig, das Repo ist nicht so weit.

    Deshalb `SetupError` (Exit 1) und nicht `ScopeError` (Exit 2) — Exit 2 ist
    für »falsch gerufen« reserviert, und die alte Bash-Schleife gab hier auch 1.
    """
    with pytest.raises(moodle.SetupError, match='Collect Scores'):
        moodle.resolve_scope(config_repo(tmp_path), None, True)
    assert moodle.main(['--config-repo', str(tmp_path), '--all-classrooms', '--dry-run']) == 1


def test_scope_a_classroom_without_grades_is_a_normal_run(tmp_path):
    """Ein vorhandenes Classroom ohne zu übertragende Noten ist kein Fehler."""
    repo = config_repo(tmp_path, 'leer', document=scores())
    assert [room.name for room in moodle.resolve_scope(repo, ['leer'], False)] == ['leer']
    assert moodle.main(['--config-repo', str(repo), '--classroom', 'leer', '--dry-run']) == 0


def test_there_is_only_one_way_to_name_a_classroom(tmp_path):
    """Kein Positional, kein --state: jeder Aufruf geht durch `resolve_scope`.

    Zwei Aufrufformen hiessen zwei Antworten auf »was ist ein Classroom«, von
    denen nur eine validiert wurde.
    """
    repo = config_repo(tmp_path, 'm323-ix24')
    for argv in ([str(repo / 'm323-ix24' / 'scores.json')],
                 ['--classroom', 'x', '--state', str(tmp_path / 's.json')]):
        with pytest.raises(SystemExit) as exit_info:
            moodle.parse_args(argv)
        assert exit_info.value.code == 2


# --- CLI -------------------------------------------------------------------


def test_cli_without_a_scope_exits_two_and_sends_nothing(tmp_path, moodle_stub, capsys):
    """Der gefährliche Fall: Eingabe vergessen, echte Zugangsdaten. Nichts geht raus."""
    repo = config_repo(tmp_path, 'm323-ix24', 'm450-ix25')

    assert moodle.main(['--config-repo', str(repo)]) == 2
    assert 'Scope fehlt' in capsys.readouterr().err
    assert moodle_stub == []


def test_cli_unknown_classroom_exits_two(tmp_path, capsys):
    repo = config_repo(tmp_path, 'm323-ix24')
    assert moodle.main(['--config-repo', str(repo), '--classroom', 'tippfehler',
                        '--dry-run']) == 2
    assert 'unbekanntes Classroom' in capsys.readouterr().err


def test_cli_all_classrooms_covers_every_room(tmp_path, moodle_stub, capsys):
    repo = config_repo(tmp_path, 'm323-ix24', 'm450-ix25')

    assert moodle.main(['--config-repo', str(repo), '--all-classrooms']) == 0
    assert (repo / 'm323-ix24' / 'moodle-state.json').is_file()
    assert (repo / 'm450-ix25' / 'moodle-state.json').is_file()
    assert len(moodle_stub) == 2
    assert 'Scope: 2 Classroom(s)' in capsys.readouterr().out


def test_cli_one_broken_classroom_does_not_stop_the_others(tmp_path, moodle_stub):
    """Verhalten, das schon die Bash-Schleife hatte: kein `set -e` über die Räume."""
    repo = config_repo(tmp_path, 'gut', 'kaputt')
    (repo / 'kaputt' / 'scores.json').write_text('{nope', encoding='UTF-8')

    assert moodle.main(['--config-repo', str(repo), '--all-classrooms']) == 1
    assert (repo / 'gut' / 'moodle-state.json').is_file()
    assert len(moodle_stub) == 1


def test_cli_announces_the_resolved_scope_in_the_step_summary(tmp_path, monkeypatch):
    """Ein zu weiter Lauf steht oben im Log und in der Job-Summary."""
    repo = config_repo(tmp_path, 'a', 'b')
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))

    assert moodle.main(['--config-repo', str(repo), '--all-classrooms',
                        '--dry-run', '--no-feedback']) == 0
    text = summary.read_text(encoding='UTF-8')
    assert 'Scope: 2 Classroom(s) — a, b | Trockenlauf' in text
    assert '| a | 1 | 0 | 0 |' in text


# --- Isolation und Ursachen-Trennung ---------------------------------------


def test_a_folder_without_scores_is_not_reported_as_a_typo(tmp_path):
    """Ordner da, `scores.json` fehlt: richtig gerufen, Repo noch nicht so weit.

    Das ist dieselbe Lage wie `--all-classrooms` in einem leeren Repo und muss
    denselben Exit-Code haben. Als `unbekanntes Classroom` gemeldet, hiesse es
    »Tippfehler« (Exit 2) für einen Ordner, den man im Repo sieht.
    """
    (tmp_path / 'm323-ix24').mkdir()
    with pytest.raises(moodle.SetupError, match='Collect Scores'):
        moodle.resolve_scope(tmp_path, ['m323-ix24'], False)
    assert moodle.main(['--config-repo', str(tmp_path), '--classroom', 'm323-ix24',
                        '--dry-run']) == 1


def test_a_missing_folder_is_still_a_typo(tmp_path):
    repo = config_repo(tmp_path, 'm323-ix24')
    with pytest.raises(moodle.ScopeError, match='unbekanntes Classroom'):
        moodle.resolve_scope(repo, ['m323-ix42'], False)


def test_an_unexpected_error_in_one_classroom_does_not_abort_the_rest(tmp_path, moodle_stub):
    """Die Isolation muss für *jeden* Fehler halten, nicht nur für die erwarteten.

    `{"assignments": {"slug": null}}` wirft AttributeError, nicht OSError oder
    ValueError. Fängt die Schleife nur die erwarteten Typen, reisst so eine
    von Hand editierte Datei den ganzen --all-classrooms-Lauf ab: die späteren
    Classrooms werden nie übertragen und die Job-Summary nie geschrieben.
    """
    repo = config_repo(tmp_path, 'a-kaputt', 'z-gut')
    (repo / 'a-kaputt' / 'scores.json').write_text(
        json.dumps({'schema': 'classroom50/scores/v1', 'assignments': {'slug': None}}),
        encoding='UTF-8')
    summary = tmp_path / 'summary.md'

    assert moodle.main(['--config-repo', str(repo), '--all-classrooms']) == 1
    assert len(moodle_stub) == 1                       # z-gut lief trotzdem
    assert (repo / 'z-gut' / 'moodle-state.json').is_file()


def test_the_summary_table_survives_a_broken_classroom(tmp_path, monkeypatch):
    repo = config_repo(tmp_path, 'a-kaputt', 'z-gut')
    (repo / 'a-kaputt' / 'scores.json').write_text(
        json.dumps({'schema': 'classroom50/scores/v1', 'assignments': {'slug': None}}),
        encoding='UTF-8')
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))

    assert moodle.main(['--config-repo', str(repo), '--all-classrooms',
                        '--dry-run', '--no-feedback']) == 1
    text = summary.read_text(encoding='UTF-8')
    assert 'unlesbare scores.json' in text
    assert '| z-gut | 1 | 0 | 0 |' in text
