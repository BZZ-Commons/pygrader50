"""Locate and load the grading configuration.

Three files drive a run, all in the format the BZZ templates already use:

    unittests.json   list of pytest cases  [{name, function, timeout, points}]
    lint.json        {"files": [...], "ignore": [...], "max": 5}
    pylintrc         pylint configuration

They are looked up per file, most trustworthy source first:

    1. the Classroom 50 bundle, extracted by runner.py to
       $RUNNER_TEMP/classroom50-runtime/<assignment>/  — teacher-controlled,
       students cannot edit it
    2. ./.github/autograding/ in the student checkout — the legacy location, kept
       as a fallback so repos work before their bundle exists
    3. $PYGRADER50_CONFIG_DIR — local development / tests only

A missing configuration is NOT an error: grading yields 0/0 with a warning, so a
non-Python assignment that inherits the classroom default still records a
submission instead of failing the job.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, field

UNITTESTS_FILENAME = 'unittests.json'
LINT_FILENAME = 'lint.json'
PYLINTRC_FILENAME = 'pylintrc'

# Where runner.py extracts <classroom>/autograders/<slug>.tar.gz. Mirrors
# runner.py::runtime_root() + the tarball's internal <slug>/ layout; the test
# suite pins this string so an upstream change is caught here, not in production.
BUNDLE_SUBDIR = 'classroom50-runtime'

STUDENT_CONFIG_DIR = pathlib.Path('.github') / 'autograding'


@dataclass(frozen=True)
class Testcase:
    """A single pytest case as declared in unittests.json."""

    name: str
    function: str
    timeout: int
    points: int


@dataclass
class GradingConfig:
    """Resolved configuration plus a record of where each part came from."""

    cases: list[Testcase] = field(default_factory=list)
    lint: dict = field(default_factory=dict)
    pylintrc: pathlib.Path | None = None
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def has_unittests(self) -> bool:
        """True when at least one pytest case is configured."""
        return bool(self.cases)

    @property
    def has_lint(self) -> bool:
        """True when a lint configuration was found."""
        return bool(self.lint)

    @property
    def is_empty(self) -> bool:
        """True when nothing at all is configured for this assignment."""
        return not self.has_unittests and not self.has_lint


def search_path(assignment: str, runner_temp: pathlib.Path | None,
                workspace: pathlib.Path) -> list[pathlib.Path]:
    """Configuration directories, most trustworthy first."""
    candidates: list[pathlib.Path] = []
    override = os.environ.get('PYGRADER50_CONFIG_DIR', '').strip()
    if runner_temp is not None:
        candidates.append(runner_temp / BUNDLE_SUBDIR / assignment)
    candidates.append(workspace / STUDENT_CONFIG_DIR)
    if override:
        candidates.append(pathlib.Path(override))
    return candidates


def _find(filename: str, path: list[pathlib.Path]) -> pathlib.Path | None:
    for directory in path:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def _load_json(path: pathlib.Path):
    with path.open(encoding='UTF-8') as handle:
        return json.load(handle)


def _parse_cases(raw) -> list[Testcase]:
    if not isinstance(raw, list):
        raise ValueError(f'{UNITTESTS_FILENAME} must contain a JSON array')
    cases = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f'{UNITTESTS_FILENAME}[{index}] is not an object')
        try:
            cases.append(
                Testcase(
                    name=str(item['name']),
                    function=str(item['function']),
                    timeout=int(item.get('timeout', 10)),
                    # Classroom 50 scores are integers; a fractional weight in the
                    # template would silently disappear at result-build time, so
                    # round it here where the source file is still in view.
                    points=round(float(item.get('points', 0))),
                )
            )
        except KeyError as exc:
            raise ValueError(f'{UNITTESTS_FILENAME}[{index}] misses {exc}') from exc
    return cases


def load(assignment: str, runner_temp: pathlib.Path | None,
         workspace: pathlib.Path) -> GradingConfig:
    """Resolve every configuration file along the search path."""
    path = search_path(assignment, runner_temp, workspace)
    config = GradingConfig()

    unittests = _find(UNITTESTS_FILENAME, path)
    if unittests is not None:
        config.cases = _parse_cases(_load_json(unittests))
        config.sources[UNITTESTS_FILENAME] = str(unittests)

    lint = _find(LINT_FILENAME, path)
    if lint is not None:
        loaded = _load_json(lint)
        config.lint = loaded if isinstance(loaded, dict) else {}
        config.sources[LINT_FILENAME] = str(lint)

    pylintrc = _find(PYLINTRC_FILENAME, path)
    if pylintrc is not None:
        config.pylintrc = pylintrc
        config.sources[PYLINTRC_FILENAME] = str(pylintrc)

    return config
