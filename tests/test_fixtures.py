"""Real-log fixtures: a real Tenhou log plus hand-written expected hands.

Fixtures are local data and are never committed, because Tenhou forbids
redistributing its logs. They live in `local/fixtures/` at the repo root,
which git ignores. Set LOGPARSER_FIXTURES to use another folder.

Each case is a folder named after what it covers:

    <case>/<logId>.xml     one or more real logs, player names blanked
    <case>/expected.json   a list of expected hands, written by hand from the
                           raw log. Each gives the hand's "id" and the fields
                           to check; fields left out are not checked.

Every case is ingested on its own and each expected hand is compared with the
hand store. Corrupted copies of every case's logs, made in memory, must fail
the checks their corruption breaks. The tests skip, with a reason, when there
are no fixtures.
"""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore
from logparser.tenhou import parse_log

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


def add_dora_indicators(agari: ET.Element, *tile_ids: int) -> None:
    agari.set("doraHai", ",".join([agari.get("doraHai"), *map(str, tile_ids)]))


def fifth_copy(agari: ET.Element) -> None:
    """All four copies of the winning tile's kind join the dora indicators, so the hand's copy is a fifth."""
    kind = int(agari.get("machi")) // 4
    add_dora_indicators(agari, *range(kind * 4, kind * 4 + 4))


def second_red_five(agari: ET.Element) -> None:
    """The red 5p shows twice among the dora indicators."""
    add_dora_indicators(agari, 52, 52)


def concealed(agari: ET.Element) -> list[int]:
    return [int(tile_id) for tile_id in agari.get("hai").split(",")]


def winning_tile_not_concealed(agari: ET.Element) -> None:
    agari.set("machi", str(next(tile_id for tile_id in range(136) if tile_id not in concealed(agari))))


def winning_tile_not_handed_over(agari: ET.Element) -> None:
    """Another of the concealed tiles becomes the winning tile, though no move handed it over."""
    machi = int(agari.get("machi"))
    agari.set("machi", str(next(tile_id for tile_id in concealed(agari) if tile_id != machi)))


def fifth_copy_and_winning_tile_not_concealed(agari: ET.Element) -> None:
    fifth_copy(agari)
    winning_tile_not_concealed(agari)


def corrupted_copy(xml_text: str, corrupt) -> str:
    root = ET.fromstring(xml_text)
    for agari in root.iter("AGARI"):
        corrupt(agari)
    return ET.tostring(root, encoding="unicode")


@pytest.mark.parametrize("case", fixture_cases())
@pytest.mark.parametrize(
    ("corrupt", "failed_checks"),
    [
        pytest.param(fifth_copy, {"tile-limits"}, id="fifth-copy"),
        pytest.param(second_red_five, {"tile-limits"}, id="second-red-five"),
        pytest.param(winning_tile_not_concealed, {"winning-tile"}, id="winning-tile-not-concealed"),
        pytest.param(winning_tile_not_handed_over, {"winning-tile"}, id="winning-tile-not-handed-over"),
        pytest.param(fifth_copy_and_winning_tile_not_concealed, {"tile-limits", "winning-tile"},
                     id="fifth-copy-and-winning-tile-not-concealed"),
    ],
)
def test_a_corrupted_copy_of_a_real_hand_fails_the_checks_its_corruption_breaks(case, corrupt, failed_checks):
    for log in case.glob("*.xml"):
        xml_text = log.read_text(encoding="utf-8")
        real_hands = parse_log(log.stem, xml_text).hands
        corrupted_hands = parse_log(log.stem, corrupted_copy(xml_text, corrupt)).hands

        assert real_hands
        for real, corrupted in zip(real_hands, corrupted_hands, strict=True):
            assert not failed_checks & set(real["quarantineReasons"]), real["id"]
            assert failed_checks <= set(corrupted["quarantineReasons"]), corrupted["id"]
