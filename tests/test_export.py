"""Stage 2: export builds the trainer bundle from the verified hands in the hand store."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from logparser.export import Drill, export_bundle, load_catalogue
from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore
from logparser.yaku import TENHOU_YAKU_KEYS
from tenhou_xml import called_win, closed_win, game, init

SCHEMA_PATH = Path(__file__).parents[1] / "src" / "logparser" / "schema" / "trainer-bundle.schema.json"
LOG_ID = "2024010112gm-00a9-0000-0123abcd"
BUILT_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
EVERYTHING = [Drill(key="everything", pool="all", target=500)]


@pytest.fixture
def hand_store(tmp_path):
    """Four rounds: three closed wins (verified) and one win with calls (quarantined)."""
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        init(round_number=0), closed_win(who=1),
        init(round_number=1), called_win(who=2),
        init(round_number=2), closed_win(who=3),
        init(round_number=3), closed_win(who=0),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        yield hands


def bundle_files(folder: Path) -> dict[str, dict]:
    return {path.name: json.loads(path.read_text()) for path in sorted(folder.iterdir())}


def bundle_hands(folder: Path) -> list[dict]:
    manifest = json.loads((folder / "manifest.json").read_text())
    return [hand for chunk in manifest["chunks"] for hand in json.loads((folder / chunk).read_text())["hands"]]


def test_every_bundle_file_validates_against_the_schema_at_version_1_0_0(hand_store, tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)

    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    files = bundle_files(tmp_path / "bundle")
    for name, data in files.items():
        Draft202012Validator(schema).validate(data)
    assert files["manifest.json"]["schemaVersion"] == "1.0.0"


def test_the_manifest_lists_each_drill_with_the_ids_of_its_hands_and_counts_them(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT, seed=7)

    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text())

    assert manifest["drills"] == [{"key": "everything", "handIds": [f"{LOG_ID}/0/0", f"{LOG_ID}/2/0", f"{LOG_ID}/3/0"]}]
    assert manifest["counts"] == {"hands": 3, "drills": {"everything": 3}}
    assert manifest["build"] == {"builtAt": "2026-01-02T03:04:05Z", "generator": "mahjong-logparser 2.0.0.dev0", "seed": 7}


def test_each_hand_appears_once_with_its_id_situation_tiles_and_answer_key(hand_store, tmp_path):
    drills = [Drill(key="everything", pool="all", target=500), Drill(key="everything-again", pool="all", target=500)]

    export_bundle(hand_store, tmp_path / "bundle", drills, built_at=BUILT_AT)

    hands = bundle_hands(tmp_path / "bundle")
    assert [hand["id"] for hand in hands] == [f"{LOG_ID}/0/0", f"{LOG_ID}/2/0", f"{LOG_ID}/3/0"]
    assert hands[0] == {
        "id": f"{LOG_ID}/0/0",
        "situation": {
            "roundWind": "east",
            "seatWind": "south",
            "dealer": False,
            "honba": 0,
            "riichiSticks": 0,
            "tsumo": False,
            "riichi": False,
        },
        "tiles": {
            "concealed": "123m45699p234789s",
            "winningTile": "4s",
            "doraIndicators": "6z",
            "uraDoraIndicators": "",
        },
        "answerKey": {
            "yaku": [{"key": "pinfu", "han": 1}],
            "han": 1,
            "fu": 30,
            "points": 1000,
            "payments": {"base": {"fromDiscarder": 1000}, "honbaBonus": 0, "riichiSticksCollected": 0},
        },
    }


def test_quarantined_hands_player_names_and_replay_links_never_reach_the_bundle(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    text = "".join(path.read_text() for path in (tmp_path / "bundle").iterdir())

    assert f"{LOG_ID}/1/0" not in text
    assert "tenhou.net" not in text
    assert not any(name in text for name in ("Alice", "Bob", "Carol", "Dave"))


def test_a_drill_takes_no_more_hands_than_it_aims_for(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", [Drill(key="everything", pool="all", target=2)], built_at=BUILT_AT)

    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text())

    assert (manifest["counts"]["drills"], len(bundle_hands(tmp_path / "bundle"))) == ({"everything": 2}, 2)


def test_hands_are_split_into_chunk_files_listed_in_the_manifest(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT, chunk_size=2)

    files = bundle_files(tmp_path / "bundle")

    assert files["manifest.json"]["chunks"] == ["hands-000.json", "hands-001.json"]
    assert [len(files[name]["hands"]) for name in ("hands-000.json", "hands-001.json")] == [2, 1]


def test_exporting_again_leaves_no_stale_chunk_files(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT, chunk_size=1)
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT, chunk_size=2)

    assert sorted(bundle_files(tmp_path / "bundle")) == ["hands-000.json", "hands-001.json", "manifest.json"]


def test_the_drill_catalogue_holds_the_everything_drill_aiming_for_500_random_hands():
    assert load_catalogue() == [Drill(key="everything", pool="all", target=500)]


def test_the_schema_knows_every_yaku_key_the_parser_can_write():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert set(schema["$defs"]["yakuKey"]["enum"]) == set(TENHOU_YAKU_KEYS.values())
