"""Reading hands out of a single Tenhou log (stage 1, one log at a time)."""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import (
    CLOSED_HAND,
    NO_AKA_HANCHAN,
    NO_KUITAN_HANCHAN,
    PHOENIX_EAST_ONLY,
    PHOENIX_HANCHAN,
    SANMA_HANCHAN,
    agari,
    called_win,
    game,
    ids,
    init,
)
from tenhou_xml import closed_win as win

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


@pytest.mark.parametrize("game_type", [PHOENIX_HANCHAN, PHOENIX_EAST_ONLY], ids=["hanchan", "east-only"])
def test_four_player_kuitan_aka_games_are_taken(game_type):
    parsed = parse_log(LOG_ID, game(init(), win(), game_type=game_type))

    assert (parsed.skipped, len(parsed.hands)) == (None, 1)


@pytest.mark.parametrize(
    ("game_type", "reason"),
    [(SANMA_HANCHAN, "sanma"), (NO_AKA_HANCHAN, "ruleset"), (NO_KUITAN_HANCHAN, "ruleset")],
    ids=["sanma", "no-red-fives", "no-open-tanyao"],
)
def test_other_games_are_skipped_without_hands(game_type, reason):
    parsed = parse_log(LOG_ID, game(init(), win(), game_type=game_type))

    assert (parsed.skipped, parsed.hands) == (reason, [])


def test_hand_ids_count_rounds_from_zero_and_a_repeated_round_is_a_new_round():
    xml = game(
        init(round_number=0), "<RYUUKYOKU/>",
        init(round_number=0, honba=1), win(who=2),          # East 1 repeated with 1 honba
        init(round_number=1), win(who=3), win(who=1),        # double ron
    )

    hand_ids = [hand["id"] for hand in parse_log(LOG_ID, xml).hands]

    assert hand_ids == [f"{LOG_ID}/1/0", f"{LOG_ID}/2/0", f"{LOG_ID}/2/1"]


def test_each_hand_records_a_replay_link_to_its_round_from_the_winners_seat():
    xml = game(init(round_number=0), "<RYUUKYOKU/>", init(round_number=1), win(who=2))

    hand = only_hand(xml)

    assert hand["replayUrl"] == f"https://tenhou.net/0/?log={LOG_ID}&ts=1&tw=2"


def test_situation_of_a_non_dealer_ron():
    # East 2 (seat 1 deals), 2 honba, 1 stick carried in; seat 2 declares riichi and rons seat 0.
    xml = game(
        init(round_number=1, honba=2, sticks=1, oya=1),
        '<REACH who="2" step="1"/><F30/><REACH who="2" step="2" ten="250,250,240,250"/>',
        agari(who=2, from_who=0, ba="2,2", hai=CLOSED_HAND, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40"),
    )

    situation = only_hand(xml)["situation"]

    assert situation == {
        "roundWind": "east",
        "seatWind": "south",
        "dealer": False,
        "honba": 2,
        "riichiSticks": 2,
        "tsumo": False,
        "riichi": True,
    }


def test_situation_of_a_dealer_tsumo_without_riichi():
    # South 2 (round number 5): seat 1 deals and wins by tsumo; seat 3 is the one in riichi.
    xml = game(
        init(round_number=5, oya=1),
        '<REACH who="3" step="1"/><G30/><REACH who="3" step="2" ten="250,250,250,240"/>',
        agari(who=1, from_who=1, ba="0,1", hai=CLOSED_HAND, machi=84, ten="30,1500,0", yaku="0,1,7,1", dealer=1),
    )

    situation = only_hand(xml)["situation"]

    assert situation == {
        "roundWind": "south",
        "seatWind": "east",
        "dealer": True,
        "honba": 0,
        "riichiSticks": 1,
        "tsumo": True,
        "riichi": False,
    }


def test_riichi_is_taken_from_the_moves_of_the_winners_own_round():
    # Seat 1 was in riichi in the first round only; in the second it wins without riichi.
    xml = game(
        init(round_number=0), '<REACH who="1" step="1"/><E30/><REACH who="1" step="2"/>', "<RYUUKYOKU/>",
        init(round_number=0, honba=1), '<REACH who="1" step="1"/>',
        agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1"),
    )

    assert only_hand(xml)["situation"]["riichi"] is False


def test_answer_key_holds_tenhous_yaku_as_contract_keys_with_han_fu_and_points():
    # Riichi 1, pinfu 1, dora 2, aka dora 1, and Tenhou's "ura dora 0" entry.
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,8000,1",
                             yaku="1,1,7,1,52,2,54,1,53,0", ura="40"))

    answer_key = only_hand(xml)["answerKey"]

    assert answer_key == {
        "yaku": [
            {"key": "riichi", "han": 1},
            {"key": "pinfu", "han": 1},
            {"key": "dora", "han": 2},
            {"key": "aka-dora", "han": 1},
        ],
        "han": 5,
        "fu": 30,
        "points": 8000,
        "payments": {"base": {"fromDiscarder": 8000}, "honbaBonus": 0, "riichiSticksCollected": 0},
    }


def test_seat_wind_and_round_wind_yaku_have_their_own_keys():
    xml = game(init(), agari(who=0, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,3900,0", yaku="0,1,10,1,14,1"))

    yaku = [y["key"] for y in only_hand(xml)["answerKey"]["yaku"]]

    assert yaku == ["menzen-tsumo", "seat-wind-east", "round-wind-east"]


def test_each_yakuman_in_the_answer_key_counts_13_han():
    # Tsuuiisou plus daisangen, a double yakuman: Tenhou lists only the yakuman.
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,64000,5", yakuman="42,39"))

    answer_key = only_hand(xml)["answerKey"]

    assert answer_key == {
        "yaku": [{"key": "tsuuiisou", "han": 13}, {"key": "daisangen", "han": 13}],
        "han": 26,
        "fu": 40,
        "points": 64000,
        "payments": {"base": {"fromDiscarder": 64000}, "honbaBonus": 0, "riichiSticksCollected": 0},
    }


def test_a_hand_that_passes_every_check_is_verified():
    assert only_hand(game(init(), win()))["quarantineReasons"] == []


def test_a_closed_hand_without_14_tiles_is_quarantined_for_its_tile_total():
    thirteen_tiles = ids(0, 4, 8, 48, 53, 56, 76, 80, 84, 96, 100, 104, 108)
    xml = game(init(), agari(who=1, from_who=0, hai=thirteen_tiles, machi=84, ten="30,1000,0", yaku="7,1"))

    assert only_hand(xml)["quarantineReasons"] == ["tile-total"]


def test_a_hand_with_calls_is_quarantined_until_calls_are_supported():
    assert only_hand(game(init(), called_win()))["quarantineReasons"] == ["calls-not-supported"]


def test_a_yaku_without_a_contract_key_quarantines_the_hand():
    # Tenhou ID 36 (renhou) is not part of Tenhou's rules and has no contract key.
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,8000,1", yaku="36,5"))

    hand = only_hand(xml)

    assert (hand["quarantineReasons"], hand["answerKey"]["yaku"]) == (["unknown-yaku"], [])


def test_concealed_tiles_are_written_in_mpsz_with_man_first():
    # 1m 2m 3m = 0 4 8; 4p 5p 6p = 48 53 56; 2s 3s 4s = 76 80 84; 7s 8s 9s = 96 100 104;
    # East East = 108 109.
    hai = ids(0, 4, 8, 48, 53, 56, 76, 80, 84, 96, 100, 104, 108, 109)
    xml = game(init(), agari(who=1, from_who=0, hai=hai, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40"))

    hand = only_hand(xml)

    assert hand["tiles"]["concealed"] == "123m456p234789s11z"


def test_red_fives_are_written_as_zero():
    # 3m 4m red-5m, red-5p 5p 5p, 3s 4s red-5s, 6s 7s 8s, Haku Haku.
    hai = ids(8, 12, 16, 52, 53, 54, 80, 84, 88, 92, 96, 100, 124, 125)
    xml = game(init(), agari(who=1, from_who=0, hai=hai, machi=88, ten="40,5200,0", yaku="18,1,54,3"))

    hand = only_hand(xml)

    assert hand["tiles"]["concealed"] == "340m055p340678s55z"


def test_winning_tile_is_read_from_machi_not_from_the_previous_move():
    # The last move before the win is a discard of 9p (68) by seat 0, but
    # Tenhou's machi says the winning tile was 4s (84).
    xml = game(init(), "<T120/><D68/>", agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40"))

    hand = only_hand(xml)

    assert hand["tiles"]["winningTile"] == "4s"


def test_dora_and_ura_dora_indicators_are_recorded_with_the_tiles():
    # Dora indicators Hatsu (130) and 2p (40, a kan dora); ura indicators 4z (120) and 2s (77).
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,1300,0",
                             yaku="1,1,53,0", dora="130,40", ura="120,77"))

    tiles = only_hand(xml)["tiles"]

    assert (tiles["doraIndicators"], tiles["uraDoraIndicators"]) == ("2p6z", "2s4z")


def test_a_hand_without_riichi_has_no_ura_dora_indicators():
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1"))

    assert only_hand(xml)["tiles"]["uraDoraIndicators"] == ""
