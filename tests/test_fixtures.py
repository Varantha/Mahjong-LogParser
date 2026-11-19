"""Real-log fixtures: a real Tenhou log plus hand-written expected hands.

Fixtures are local data and are never committed, because Tenhou forbids
redistributing its logs. They live in `local/fixtures/` at the repo root,
which git ignores. Set LOGPARSER_FIXTURES to use another folder, for example
the main checkout's `local/fixtures` when working in a git worktree.

Each case is a folder named after what it covers:

    <case>/<logId>.xml     one or more real logs, player names blanked
    <case>/expected.json   a list of expected hands, written by hand from the
                           raw log. Each gives the hand's "id" and the fields
                           to check; fields left out are not checked.

Every case is ingested on its own and each expected hand is compared with the
hand store. The tests skip, with a reason, when there are no fixtures.
"""

import json
import os
from pathlib import Path

import pytest

from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore

FIXTURES = Path(os.environ.get("LOGPARSER_FIXTURES", Path(__file__).parents[1] / "local" / "fixtures"))


def fixture_cases() -> list:
    cases = sorted(path for path in FIXTURES.iterdir() if path.is_dir()) if FIXTURES.is_dir() else []
    if not cases:
        reason = f"no real-log fixtures in {FIXTURES} (set LOGPARSER_FIXTURES to the fixtures folder)"
        return [pytest.param(None, marks=pytest.mark.skip(reason=reason), id="no-fixtures")]
    return [pytest.param(case, id=case.name) for case in cases]


def checked_fields(actual, expected):
    """The parts of `actual` that `expected` names, so the comparison ignores fields a case leaves out."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: checked_fields(actual.get(key, "<missing>"), value) for key, value in expected.items()}
    return actual


@pytest.mark.parametrize("case", fixture_cases())
def test_real_log_gives_the_expected_hands(case, tmp_path):
    logs = LogStore(tmp_path / "log-store")
    for log in case.glob("*.xml"):
        logs.add_file(log)
    expected_hands = json.loads((case / "expected.json").read_text(encoding="utf-8"))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        actual_hands = [hands.get(expected["id"]) for expected in expected_hands]

    for actual, expected in zip(actual_hands, expected_hands):
        assert checked_fields(actual, expected) == expected
