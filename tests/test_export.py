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
from logparser.tags import TAGS
from logparser.yaku import TENHOU_YAKU_KEYS
from tenhou_xml import (CLOSED_HAND, KAMICHA, added_kan, agari, called_win, chi, closed_kan, closed_win, game, ids,
                        init, m, short_win)

SCHEMA_PATH = Path(__file__).parents[1] / "src" / "logparser" / "schema" / "trainer-bundle.schema.json"
LOG_ID = "2024010112gm-00a9-0000-0123abcd"
BUILT_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
EVERYTHING = [Drill(key="everything", pool="all", target=500)]


@pytest.fixture
def hand_store(tmp_path):
    """Four rounds: three closed wins (verified) and one win with a tile missing (quarantined)."""
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        init(round_number=0), closed_win(who=1),
        init(round_number=1), short_win(who=2),
        init(round_number=2), closed_win(who=3),
        init(round_number=3), closed_win(who=0, from_who=3),
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


def test_each_hand_appears_once_with_its_id_situation_tiles_answer_key_and_tags(hand_store, tmp_path):
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
            "calls": [],
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
        "tags": [],
    }


def test_the_bundle_carries_each_kind_of_payment_with_the_honba_and_riichi_sticks_apart(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        # Dealer tsumo: 3 han 30 fu, 2000 all.
        init(round_number=0), agari(who=0, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,6000,0", yaku="0,1,52,2"),
        # Non-dealer tsumo with 1 honba and 1 stick: 3 han 40 fu, 1300 / 2600.
        init(round_number=1, honba=1, sticks=1),
        agari(who=2, from_who=2, ba="1,1", hai=CLOSED_HAND, machi=84, ten="40,5200,0", yaku="0,1,52,2", dealer=1),
        # Ron: 1 han 30 fu, 1000 from the discarder.
        init(round_number=2), closed_win(who=3, from_who=0),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    payments = {hand["id"]: hand["answerKey"]["payments"] for hand in bundle_hands(tmp_path / "bundle")}

    assert payments == {
        f"{LOG_ID}/0/0": {"base": {"fromEachPlayer": 2000}, "honbaBonus": 0, "riichiSticksCollected": 0},
        f"{LOG_ID}/1/0": {"base": {"fromDealer": 2600, "fromEachNonDealer": 1300},
                          "honbaBonus": 300, "riichiSticksCollected": 1000},
        f"{LOG_ID}/2/0": {"base": {"fromDiscarder": 1000}, "honbaBonus": 0, "riichiSticksCollected": 0},
    }


def test_a_hand_with_calls_reaches_the_bundle_with_each_call_as_an_object(tmp_path):
    # A chi with the red 5m and a pon of Chun (CALLED_HAND). Then a closed kan of 5m and an
    # added kan of 5p whose added tile is the red 5p, with 234s 678s 33m concealed: tanyao and
    # two aka dora, 3 han 50 fu on a ron of 3m.
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        init(round_number=0), called_win(who=1),
        init(round_number=1), agari(who=2, from_who=0, hai=ids(8, 9, 76, 80, 84, 92, 96, 100), machi=9,
                                    m=m(closed_kan(16), added_kan((53, 54, 55), called=54, from_seat=KAMICHA)),
                                    ten="50,6400,0", yaku="8,1,54,2"),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    calls = [hand["tiles"]["calls"] for hand in bundle_hands(tmp_path / "bundle")]

    assert calls == [
        [
            {"type": "chi", "tiles": "340m", "calledTile": "0m", "calledFrom": "kamicha"},
            {"type": "pon", "tiles": "777z", "calledTile": "7z", "calledFrom": "toimen"},
        ],
        [
            {"type": "closed-kan", "tiles": "0555m", "calledTile": None, "calledFrom": None},
            {"type": "added-kan", "tiles": "0555p", "calledTile": "5p", "calledFrom": "kamicha"},
        ],
    ]


@pytest.fixture
def tagged_hand_store(tmp_path):
    """Three verified hands: one with kuisagari, one with wraparound-dora and one with no tags."""
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        # Chi 123m; 567m 78m+9m 444z 33z: open honitsu, 2 han 30 fu.
        init(round_number=0), agari(who=1, from_who=0, hai=ids(17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
                                    m=m(chi((0, 4, 8), called=0)), machi=32, ten="30,2000,0", yaku="34,2"),
        # Chiitoitsu with the 9m as indicator, so the pair of 1m is dora: 4 han 25 fu.
        init(round_number=1), agari(who=2, from_who=0, hai=ids(0, 1, 32, 33, 36, 37, 40, 41, 72, 73, 108, 109, 124, 125),
                                    machi=125, ten="25,6400,0", yaku="22,2,52,2", dora=ids(34)),
        init(round_number=2), closed_win(who=3),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        yield hands


def test_each_hand_in_the_bundle_carries_its_tags(tagged_hand_store, tmp_path):
    export_bundle(tagged_hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    tags = {hand["id"]: hand["tags"] for hand in bundle_hands(tmp_path / "bundle")}

    assert tags == {f"{LOG_ID}/0/0": ["kuisagari"], f"{LOG_ID}/1/0": ["wraparound-dora"], f"{LOG_ID}/2/0": []}


def test_the_schema_requires_a_closed_kan_to_have_no_called_tile_and_other_calls_to_have_one():
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    call_schema = {"$ref": "#/$defs/call", "$defs": validator.schema["$defs"]}
    closed_kan_call = {"type": "closed-kan", "tiles": "1111z", "calledTile": None, "calledFrom": None}
    pon_call = {"type": "pon", "tiles": "111z", "calledTile": "1z", "calledFrom": "toimen"}

    assert Draft202012Validator(call_schema).is_valid(closed_kan_call)
    assert Draft202012Validator(call_schema).is_valid(pon_call)
    assert not Draft202012Validator(call_schema).is_valid({**closed_kan_call, "calledTile": "1z", "calledFrom": "toimen"})
    assert not Draft202012Validator(call_schema).is_valid({**pon_call, "calledTile": None, "calledFrom": None})


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


def test_the_schema_knows_every_tag_key_the_parser_can_write():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert set(schema["$defs"]["tagKey"]["enum"]) == set(TAGS)
