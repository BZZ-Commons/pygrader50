"""The filter that lets an assignment add packages but not move the grading tools."""

import pathlib
import subprocess
import sys
import tomllib

import pytest

from pygrader50 import requirements

PYPROJECT = pathlib.Path(__file__).resolve().parents[1] / 'pyproject.toml'

A10 = '''\
pylint==4.0.7
pytest==9.1.1
httpx==0.28.1
pytest-asyncio==1.4.0
'''


def test_the_protected_list_covers_every_pin_in_pyproject():
    """A new pin in pyproject.toml must not silently leave a hole in the filter."""
    with PYPROJECT.open('rb') as handle:
        declared = tomllib.load(handle)['project']['dependencies']
    names = {requirements.canonical(requirements.NAME.match(line).group(1))
             for line in declared}
    assert names <= set(requirements.PROTECTED_NAMES)


def test_the_real_a10_file_keeps_only_the_extras():
    """m323-lu03-a10-timer: httpx and pytest-asyncio in, the grading tools out."""
    wanted = requirements.plan(A10)
    assert wanted.install == ['httpx==0.28.1', 'pytest-asyncio==1.4.0']
    assert wanted.dropped == ['pylint==4.0.7', 'pytest==9.1.1']
    assert wanted.unsupported == []


def test_a_plugin_is_not_dropped_for_starting_with_a_protected_name():
    """`pytest-asyncio` is not `pytest`; a prefix match here would break a10."""
    assert requirements.plan('pytest-asyncio==1.4.0').install == ['pytest-asyncio==1.4.0']
    assert requirements.plan('pylint-django').install == ['pylint-django']


@pytest.mark.parametrize('line', [
    'PyTest==9.1.1',
    'pytest_timeout>=2',
    'Pylint',
    'pygrader50 @ git+https://example.invalid/x',
    'pytest[extra]==9.1.1',
    'pylint==3.2.7 ; python_version < "3.12"',
])
def test_a_protected_pin_is_dropped_however_it_is_written(line):
    """Name normalisation, extras, markers and URLs must not slip past the filter."""
    assert requirements.plan(line).dropped == [line]


def test_comments_and_blank_lines_are_ignored():
    text = '# lokal\n\nhttpx==0.28.1  # fuer die API\n   \n'
    assert requirements.plan(text).install == ['httpx==0.28.1']


def test_a_hash_inside_a_line_only_counts_after_whitespace():
    """pip's own rule; `#egg=` fragments are part of the requirement, not a comment."""
    assert requirements.strip_comment('httpx==0.28.1#nope') == 'httpx==0.28.1#nope'
    assert requirements.strip_comment('httpx==0.28.1 # yes') == 'httpx==0.28.1'


@pytest.mark.parametrize('line', [
    '-r andere.txt',
    '--index-url https://example.invalid/simple',
    '-e .',
    'httpx \\',
])
def test_pip_options_and_continued_lines_are_refused(line):
    """A name-based filter cannot vouch for these — `-r` hides a whole second file."""
    assert requirements.plan(line).unsupported == [line]


def test_constraints_pin_what_is_installed():
    pins = requirements.constraints()
    assert any(pin.startswith('pytest==') for pin in pins)
    assert all('==' in pin for pin in pins)


def test_a_checkout_without_the_file_installs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(requirements, 'pip_install', _forbidden)
    requirements.install(tmp_path)


def test_a_file_of_nothing_but_protected_pins_never_calls_pip(tmp_path, monkeypatch, capsys):
    (tmp_path / 'requirements.txt').write_text('pylint==4.0.7\npytest==9.1.1\n', encoding='UTF-8')
    monkeypatch.setattr(requirements, 'pip_install', _forbidden)
    requirements.install(tmp_path)
    out = capsys.readouterr().out
    assert 'pins its own version of pylint==4.0.7, pytest==9.1.1' in out
    # An annotation here would mark all 63 assignments yellow on every run.
    assert '::warning::' not in out


def test_the_install_receives_the_filtered_lines_and_the_pins(tmp_path, monkeypatch):
    (tmp_path / 'requirements.txt').write_text(A10, encoding='UTF-8')
    seen = {}

    def record(lines, pins):
        seen['lines'] = lines
        seen['pins'] = pins
        return subprocess.CompletedProcess([], 0, '', '')

    monkeypatch.setattr(requirements, 'pip_install', record)
    requirements.install(tmp_path)
    assert seen['lines'] == ['httpx==0.28.1', 'pytest-asyncio==1.4.0']
    assert any(pin.startswith('pylint==') for pin in seen['pins'])


def test_a_failed_install_warns_and_lets_grading_continue(tmp_path, monkeypatch, capsys):
    (tmp_path / 'requirements.txt').write_text('nichtdawirklich==1.0\n', encoding='UTF-8')
    monkeypatch.setattr(
        requirements, 'pip_install',
        lambda lines, pins: subprocess.CompletedProcess([], 1, 'out', 'boom'),
    )
    requirements.install(tmp_path)
    captured = capsys.readouterr()
    assert '::warning::' in captured.out
    assert 'install failed' in captured.out
    assert 'boom' in captured.err


def test_a_hanging_index_warns_and_lets_grading_continue(tmp_path, monkeypatch, capsys):
    (tmp_path / 'requirements.txt').write_text('httpx==0.28.1\n', encoding='UTF-8')

    def hang(lines, pins):
        raise subprocess.TimeoutExpired(cmd='pip', timeout=requirements.INSTALL_TIMEOUT)

    monkeypatch.setattr(requirements, 'pip_install', hang)
    requirements.install(tmp_path)
    assert 'timed out' in capsys.readouterr().out


def test_an_unreadable_file_warns_and_lets_grading_continue(tmp_path, monkeypatch, capsys):
    (tmp_path / 'requirements.txt').write_text('httpx==0.28.1\n', encoding='UTF-8')
    monkeypatch.setattr(requirements, 'pip_install', _forbidden)
    monkeypatch.setattr(
        pathlib.Path, 'read_text',
        lambda self, **kwargs: (_ for _ in ()).throw(OSError('nope')),
    )
    requirements.install(tmp_path)
    assert 'unreadable' in capsys.readouterr().out


def test_pip_is_invoked_with_a_requirements_and_a_constraints_file(monkeypatch):
    """The two files must reach pip as -r and -c, and never be written into the checkout."""
    seen = {}

    def fake_run(argv, **kwargs):
        seen['argv'] = argv
        seen['timeout'] = kwargs['timeout']
        seen['wanted'] = pathlib.Path(argv[argv.index('-r') + 1]).read_text(encoding='UTF-8')
        seen['limits'] = pathlib.Path(argv[argv.index('-c') + 1]).read_text(encoding='UTF-8')
        return subprocess.CompletedProcess(argv, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    requirements.pip_install(['httpx==0.28.1'], ['pytest==9.1.1'])
    assert seen['argv'][:3] == [sys.executable, '-m', 'pip']
    assert seen['timeout'] == requirements.INSTALL_TIMEOUT
    assert seen['wanted'].strip() == 'httpx==0.28.1'
    assert seen['limits'].strip() == 'pytest==9.1.1'


def _forbidden(*args, **kwargs):
    raise AssertionError('pip must not run for this input')
