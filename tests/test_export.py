"""Stage 2: export builds the trainer bundle from the verified hands in the hand store."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from logparser.drills import Conditions, Drill
from logparser.export import HandStoreOutOfDate, export_bundle
from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore
from logparser.recalculation import FU_KEYS
from logparser.tags import TAGS
from logparser.yaku import TENHOU_YAKU_KEYS
from test_situation import AGREEING
from tenhou_xml import (CLOSED_HAND, KAMICHA, Wall, added_kan, agari, called_win, chi, closed_kan, closed_win, game,
                        ids, init, m, short_win, turns, win)

SCHEMA_PATH = Path(__file__).parents[1] / "src" / "logparser" / "schema" / "trainer-bundle.schema.json"
LOG_ID = "2024010112gm-00a9-0000-0123abcd"
BUILT_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
EVERYTHING = [Drill(key="everything", target=500)]


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


def test_every_bundle_file_validates_against_the_schema_at_version_2_0_0(hand_store, tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)

    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    files = bundle_files(tmp_path / "bundle")
    for name, data in files.items():
        Draft202012Validator(schema).validate(data)
    assert files["manifest.json"]["schemaVersion"] == "2.0.0"


def test_the_manifest_lists_each_drill_with_the_ids_of_its_hands_and_counts_them(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT, seed=7)

    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text())

    assert manifest["drills"] == [{"key": "everything", "handIds": [f"{LOG_ID}/0/0", f"{LOG_ID}/2/0", f"{LOG_ID}/3/0"]}]
    assert (manifest["counts"]["hands"], manifest["counts"]["drills"]) == (3, {"everything": 3})
    assert manifest["build"] == {"builtAt": "2026-01-02T03:04:05Z", "generator": "mahjong-logparser 2.0.0.dev0", "seed": 7}


def test_each_hand_appears_once_with_its_id_situation_tiles_answer_key_plain_values_and_tags(hand_store, tmp_path):
    drills = [Drill(key="everything", target=500), Drill(key="everything-again", target=500)]

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
            "secondWinner": False,
            "tsumo": False,
            "riichi": False,
            "ippatsu": False,
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
            "limitTier": "none",
            "points": 1000,
            "payments": {"base": {"fromDiscarder": 1000}, "honbaBonus": 0, "riichiSticksCollected": 0},
            "rawFu": 30,
            "fuBreakdown": [{"key": "base", "fu": 20}, {"key": "closed-ron", "fu": 10}],
        },
        "plainValues": {
            "han": 1,
            "fu": 30,
            "rawFu": 30,
            "limitTier": "none",
            "dealer": False,
            "tsumo": False,
            "open": False,
            "yaku": ["pinfu"],
            "doraCount": 0,
            "honba": 0,
            "riichiSticks": 0,
            "callTypes": [],
        },
        "tags": [],
    }


@pytest.fixture
def payments_hand_store(tmp_path):
    """Three verified hands: a dealer tsumo, a non-dealer tsumo with honba and riichi sticks, and a ron."""
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        # Dealer tsumo on its second draw: menzen tsumo and pinfu, 2 han 20 fu, 700 all.
        init(round_number=0), turns(4),
        agari(who=0, from_who=0, hai=CLOSED_HAND, machi=84, ten="20,2100,0", yaku="0,1,7,1"),
        # Non-dealer tsumo on its second draw, with 1 honba and 1 stick, and 8p as dora indicator so
        # the pair of 9p is dora: menzen tsumo, pinfu and dora 2, 4 han 20 fu, 1300 / 2600.
        init(round_number=1, honba=1, sticks=1), turns(5, first_seat=1),
        agari(who=2, from_who=2, ba="1,1", hai=CLOSED_HAND, machi=84, ten="20,5200,0", yaku="0,1,7,1,52,2",
              dora=ids(64), dealer=1),
        # Ron: 1 han 30 fu, 1000 from the discarder.
        init(round_number=2), closed_win(who=3, from_who=0),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        yield hands


def test_the_bundle_carries_each_kind_of_payment_with_the_honba_and_riichi_sticks_apart(payments_hand_store, tmp_path):
    export_bundle(payments_hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    payments = {hand["id"]: hand["answerKey"]["payments"] for hand in bundle_hands(tmp_path / "bundle")}

    assert payments == {
        f"{LOG_ID}/0/0": {"base": {"fromEachPlayer": 700}, "honbaBonus": 0, "riichiSticksCollected": 0},
        f"{LOG_ID}/1/0": {"base": {"fromDealer": 2600, "fromEachNonDealer": 1300},
                          "honbaBonus": 300, "riichiSticksCollected": 1000},
        f"{LOG_ID}/2/0": {"base": {"fromDiscarder": 1000}, "honbaBonus": 0, "riichiSticksCollected": 0},
    }


def test_a_hand_with_calls_reaches_the_bundle_with_each_call_as_its_call_string(tmp_path):
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

    assert calls == [["c034m", "7c77z"], ["f505f5m", "c5c055p"]]


def test_export_refuses_a_hand_store_whose_calls_have_no_call_strings_and_writes_nothing(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(init(), called_win(who=1)))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        [hand] = hands.log_hands(LOG_ID)
        for call in hand["tiles"]["calls"]:
            del call["string"]  # as ingest wrote calls before they had call strings
        hands.replace_log(LOG_ID, [hand])

        with pytest.raises(HandStoreOutOfDate, match=f"{LOG_ID}/0/0"):
            export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    assert not (tmp_path / "bundle").exists()


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
        # 222m 345p 678p 34s+2s 88s: tanyao, 1 han. The closed triplet of 2m gives raw fu 34, so 40 fu either side.
        init(round_number=2), agari(who=3, from_who=0, hai=ids(4, 5, 6, 44, 48, 53, 56, 60, 64, 76, 80, 84, 100, 101),
                                    machi=76, ten="40,1300,0", yaku="8,1"),
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        yield hands


def test_each_hand_in_the_bundle_carries_its_tags(tagged_hand_store, tmp_path):
    export_bundle(tagged_hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    tags = {hand["id"]: hand["tags"] for hand in bundle_hands(tmp_path / "bundle")}

    assert tags == {f"{LOG_ID}/0/0": ["kuisagari"], f"{LOG_ID}/1/0": ["wraparound-dora"], f"{LOG_ID}/2/0": []}


def test_the_manifest_counts_the_hands_with_each_tag(tagged_hand_store, tmp_path):
    manifest = export_bundle(tagged_hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT).manifest

    assert manifest["counts"]["tags"] == {"kuisagari": 1, "wraparound-dora": 1, "ambiguous-wait": 0, "open-pinfu-shape": 0,
                                           "fu-mangan": 0, "high-fu": 0, "knife-edge-fu": 0}


def test_the_manifest_counts_a_tag_no_bundle_hand_has_as_0(hand_store, tmp_path):
    manifest = export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT).manifest

    tag_counts = manifest["counts"]["tags"]
    assert (set(tag_counts), tag_counts["kuisagari"], tag_counts["wraparound-dora"]) == (set(TAGS), 0, 0)


def test_the_manifest_counts_the_hands_at_each_limit_tier_listing_every_tier(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, game(
        init(round_number=0), closed_win(who=1),  # pinfu, 1 han 30 fu
        # A closed kan of North; 123m 567m 78m 33z, won on 9m: honitsu, 3 han 70 fu, mangan.
        init(round_number=1), agari(who=2, from_who=0, hai=ids(0, 4, 8, 17, 20, 24, 25, 28, 32, 116, 117),
                                    m=m(closed_kan(120)), machi=32, ten="70,8000,1", yaku="34,3"),
        # Triplets of Haku, Hatsu and Chun with 123m, won on 9p: daisangen.
        init(round_number=2), win(Wall(), who=3, concealed="555z666z777z123m9p", winning="9p", dora="1p",
                                  ten="60,32000,5", yakuman="39"),
        init(round_number=3), short_win(who=0, from_who=3),  # quarantined, so not in the bundle
    ))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        manifest = export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT).manifest

    assert manifest["counts"]["limitTiers"] == {
        "none": 1, "mangan": 1, "haneman": 0, "baiman": 0, "sanbaiman": 0, "kazoe-yakuman": 0, "yakuman": 1}


@pytest.mark.parametrize("yaku", ["double-riichi", "haitei", "houtei", "rinshan", "chankan", "tenhou", "chiihou"])
def test_a_verified_hand_won_in_a_situation_the_trainer_leaves_out_never_reaches_the_bundle(yaku, tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, AGREEING[yaku])
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        verified = len(list(hands.verified_hands()))
        manifest = export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT).manifest

    assert (verified, manifest["counts"]["hands"], manifest["drills"]) == (1, 0, [{"key": "everything", "handIds": []}])


def test_a_hand_won_with_ippatsu_reaches_the_bundle_and_its_situation_says_so(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(LOG_ID, AGREEING["ippatsu"])
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        export_bundle(hands, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    [hand] = bundle_hands(tmp_path / "bundle")
    assert (hand["situation"]["riichi"], hand["situation"]["ippatsu"]) == (True, True)
    assert set(hand["situation"]) == {"roundWind", "seatWind", "dealer", "honba", "riichiSticks", "secondWinner", "tsumo",
                                      "riichi", "ippatsu"}


@pytest.mark.parametrize("call", ["c423p", "5c55p", "66c6z", "c1111z", "1c111z", "111c1z", "c5c055p", "5c0c55p",
                                  "55c5c5p", "f505f5m", "f111f1z"])
def test_the_schema_takes_every_shape_of_call_string(call):
    assert call_validator().is_valid(call)


@pytest.mark.parametrize("call", ["423p", "cc555p", "c55p", "c5c55p", "c11111z", "f1111z", "c888z", "c423",
                                  {"type": "pon", "tiles": "111z", "calledTile": "1z", "calledFrom": "toimen"}])
def test_the_schema_refuses_a_call_that_is_no_call_string(call):
    assert not call_validator().is_valid(call)


def call_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    return Draft202012Validator({"$ref": "#/$defs/call", "$defs": schema["$defs"]})


def test_quarantined_hands_player_names_and_replay_links_never_reach_the_bundle(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", EVERYTHING, built_at=BUILT_AT)

    text = "".join(path.read_text() for path in (tmp_path / "bundle").iterdir())

    assert f"{LOG_ID}/1/0" not in text
    assert "tenhou.net" not in text
    assert not any(name in text for name in ("Alice", "Bob", "Carol", "Dave"))


def test_export_builds_each_drill_in_the_catalogue_from_the_hand_store_storing_a_hand_in_several_drills_once(
        payments_hand_store, tmp_path):
    drills = [Drill(key="everything", target=500), Drill(key="payments", target=500, pool=Conditions({"tsumo": True}))]

    manifest = export_bundle(payments_hand_store, tmp_path / "bundle", drills, built_at=BUILT_AT).manifest

    assert manifest["drills"] == [
        {"key": "everything", "handIds": [f"{LOG_ID}/0/0", f"{LOG_ID}/1/0", f"{LOG_ID}/2/0"]},
        {"key": "payments", "handIds": [f"{LOG_ID}/0/0", f"{LOG_ID}/1/0"]},
    ]
    assert (manifest["counts"]["hands"], manifest["counts"]["drills"]) == (3, {"everything": 3, "payments": 2})
    assert [hand["id"] for hand in bundle_hands(tmp_path / "bundle")] == [f"{LOG_ID}/0/0", f"{LOG_ID}/1/0", f"{LOG_ID}/2/0"]


def test_export_says_which_drills_the_hand_store_leaves_short_and_by_how_much(payments_hand_store, tmp_path):
    drills = [Drill(key="everything", target=2), Drill(key="payments", target=500, pool=Conditions({"tsumo": True}))]

    # No hand has 5 honba, so the trap part of this drill is made up from the rest of its pool.
    made_up = Drill(key="made-up", target=1, trap=Conditions({"honba": 5}), lookalikes=0.0)

    export = export_bundle(payments_hand_store, tmp_path / "bundle", [*drills, made_up], built_at=BUILT_AT)

    assert [(drill.key, drill.target, drill.short_by) for drill in export.drills_with_a_short_part] == [
        ("payments", 500, 498), ("made-up", 1, 0)]


def test_a_drill_takes_no_more_hands_than_it_aims_for(hand_store, tmp_path):
    export_bundle(hand_store, tmp_path / "bundle", [Drill(key="everything", target=2)], built_at=BUILT_AT)

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



def test_the_schema_knows_every_yaku_key_the_parser_can_write():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert set(schema["$defs"]["yakuKey"]["enum"]) == set(TENHOU_YAKU_KEYS.values())


def test_the_schema_knows_every_tag_key_the_parser_can_write():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert set(schema["$defs"]["tagKey"]["enum"]) == set(TAGS)


def test_the_schema_knows_every_fu_key_the_parser_can_write():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert schema["$defs"]["fuKey"]["enum"] == list(FU_KEYS)


def test_the_schema_knows_every_limit_tier_lowest_first():
    schema = json.loads(SCHEMA_PATH.read_text())

    assert schema["$defs"]["limitTier"]["enum"] == [
        "none", "mangan", "haneman", "baiman", "sanbaiman", "kazoe-yakuman", "yakuman"]
