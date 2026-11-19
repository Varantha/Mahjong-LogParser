"""Payments in the answer key and check 5 (stage 1, one log at a time)."""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, SHIMOCHA, TOIMEN, agari, game, ids, init, m, pon, turns

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def test_a_ron_is_paid_by_the_discarder_alone():
    # Seat 1 rons seat 3 for 8000 (riichi pinfu dora 2 aka 1, 30 fu).
    xml = game(init(), agari(who=1, from_who=3, hai=CLOSED_HAND, machi=84, ten="30,8000,1",
                             yaku="1,1,7,1,52,2,54,1,53,0", ura="40", sc="250,0,250,80,250,0,250,-80"))

    assert only_hand(xml)["answerKey"]["payments"] == {
        "base": {"fromDiscarder": 8000},
        "honbaBonus": 0,
        "riichiSticksCollected": 0,
    }


def test_a_dealer_tsumo_is_one_amount_from_each_player():
    # Seat 0 deals and wins by tsumo: menzen tsumo and dora 2, 3 han 30 fu, 2000 all.
    xml = game(init(), agari(who=0, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,6000,0",
                             yaku="0,1,52,2", sc="250,60,250,-20,250,-20,250,-20"))

    assert only_hand(xml)["answerKey"]["payments"]["base"] == {"fromEachPlayer": 2000}


@pytest.mark.parametrize(
    ("ten", "sc", "base"),
    [
        # 3 han 40 fu: 1300 / 2600.
        ("40,5200,0", "250,-26,250,52,250,-13,250,-13", {"fromDealer": 2600, "fromEachNonDealer": 1300}),
        # 3 han 20 fu: 700 / 1300, the dealer pays 100 less than twice a non-dealer.
        ("20,2700,0", "250,-13,250,27,250,-7,250,-7", {"fromDealer": 1300, "fromEachNonDealer": 700}),
        # 1 han 30 fu: 300 / 500.
        ("30,1100,0", "250,-5,250,11,250,-3,250,-3", {"fromDealer": 500, "fromEachNonDealer": 300}),
    ],
    ids=["5200", "2700", "1100"],
)
def test_a_non_dealer_tsumo_is_one_amount_from_the_dealer_and_one_from_each_non_dealer(ten, sc, base):
    # Seat 0 deals; seat 1 wins by tsumo.
    xml = game(init(), agari(who=1, from_who=1, hai=CLOSED_HAND, machi=84, ten=ten, yaku="0,1,7,1,52,1", sc=sc))

    assert only_hand(xml)["answerKey"]["payments"]["base"] == base


def test_the_honba_bonus_and_the_riichi_sticks_collected_are_kept_apart_from_the_base_payments():
    # East 1 with 2 honba and 1 stick carried in; seat 2 declares riichi (a second stick) and rons seat 3.
    xml = game(
        init(honba=2, sticks=1),
        '<REACH who="2" step="1"/><F30/><REACH who="2" step="2" ten="250,250,240,250"/>',
        agari(who=2, from_who=3, ba="2,2", hai=CLOSED_HAND, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40",
              sc="250,0,250,0,240,39,250,-19"),
    )

    assert only_hand(xml)["answerKey"]["payments"] == {
        "base": {"fromDiscarder": 1300},
        "honbaBonus": 600,
        "riichiSticksCollected": 2000,
    }


# CLOSED_HAND with the red 5p (52) in place of its 5p.
CLOSED_HAND_WITH_RED_5P = ids(0, 4, 8, 48, 52, 56, 68, 69, 76, 80, 84, 96, 100, 104)


def double_ron(second_sc: str) -> str:
    """East 3 with 1 honba and 1 stick carried in: seat 0 deals into seat 1 (pinfu and aka dora,
    2000) and seat 3 (pinfu, 1000).

    The second winner's ba still shows the honba, but Tenhou gives the honba and the stick to the
    first winner. Both win on the same discard, so no move comes between the two wins.
    """
    return game(
        init(round_number=2, honba=1, sticks=1),
        agari(who=1, from_who=0, ba="1,1", hai=CLOSED_HAND_WITH_RED_5P, machi=84, ten="30,2000,0", yaku="7,1,54,1",
              sc="250,-23,250,33,250,0,240,0"),
        agari(who=3, from_who=0, ba="1,0", hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1",
              sc=second_sc, winning_move=False),
    )


def test_in_a_double_ron_the_first_winner_collects_the_honba_and_the_riichi_sticks():
    first, second = parse_log(LOG_ID, double_ron(second_sc="227,-10,283,0,250,0,240,10")).hands

    assert (first["id"], second["id"]) == (f"{LOG_ID}/0/0", f"{LOG_ID}/0/1")
    assert first["quarantineReasons"] == second["quarantineReasons"] == []
    assert first["answerKey"]["payments"] == {
        "base": {"fromDiscarder": 2000},
        "honbaBonus": 300,
        "riichiSticksCollected": 1000,
    }
    assert second["answerKey"]["payments"] == {
        "base": {"fromDiscarder": 1000},
        "honbaBonus": 0,
        "riichiSticksCollected": 0,
    }


def test_the_second_winner_of_a_double_ron_is_marked_so_the_trainer_can_say_why_it_collects_nothing_on_the_table():
    first, second = parse_log(LOG_ID, double_ron(second_sc="227,-10,283,0,250,0,240,10")).hands

    assert (first["situation"]["secondWinner"], second["situation"]["secondWinner"]) == (False, True)
    # Both see the honba on the table, but only the first winner collects them.
    assert [hand["situation"]["honba"] for hand in (first, second)] == [1, 1]
    assert second["answerKey"]["payments"]["honbaBonus"] == 0


def test_the_second_winner_of_a_double_ron_paid_the_honba_fails_check_5():
    second = parse_log(LOG_ID, double_ron(second_sc="227,-13,283,0,250,0,240,13")).hands[1]

    assert second["quarantineReasons"] == ["payments"]


def ron_8000(sc: str, ba: str = "0,0") -> str:
    """Seat 1 rons seat 3 for 8000 in East 1 (seat 0 deals), with the given recorded score changes.

    Two 8p dora indicators make the pair of 9p dora twice over: pinfu and dora 4, 5 han, mangan.
    """
    return game(init(), agari(who=1, from_who=3, ba=ba, hai=CLOSED_HAND, machi=84, ten="30,8000,1",
                              yaku="7,1,52,4", dora=ids(64, 65), sc=sc))


def tsumo(*, who: int, ten: str, sc: str, ba: str = "0,0") -> str:
    """Seat `who` wins by tsumo on its second draw in East 1 (seat 0 deals), with the given recorded
    score changes.

    The 8p dora indicator makes the pair of 9p dora: menzen tsumo, pinfu and dora 2, 4 han 20 fu,
    2600 all from the dealer or 1300 / 2600 from a non-dealer.
    """
    return game(init(), turns(4), agari(who=who, from_who=who, ba=ba, hai=CLOSED_HAND, machi=84, ten=ten,
                              yaku="0,1,7,1,52,2", dora=ids(64), sc=sc))


def daisangen_tsumo(sc: str) -> str:
    """Seat 1 wins by tsumo on its second draw in East 1: pons of Haku, Hatsu and Chun, 234m and a
    pair of 9p, won on 4m. Daisangen, 40 fu, 32000."""
    calls = m(pon((124, 125, 126), called=124, from_seat=TOIMEN), pon((128, 129, 130), called=128, from_seat=TOIMEN),
              pon((132, 133, 134), called=132, from_seat=SHIMOCHA))
    return game(init(), turns(4), agari(who=1, from_who=1, hai=ids(4, 8, 12, 68, 69), m=calls, machi=12,
                                        ten="40,32000,5", yakuman="39", dora=ids(0), sc=sc))


@pytest.mark.parametrize(
    "xml",
    [
        # 8000 + 2 honba (600) from the discarder; the winner also collects 1 stick.
        pytest.param(ron_8000(ba="2,1", sc="250,0,250,96,250,0,250,-86"), id="ron"),
        # 2600 all + 1 honba (100 from each player).
        pytest.param(tsumo(who=0, ten="20,7800,0", ba="1,0", sc="250,81,250,-27,250,-27,250,-27"),
                     id="dealer-tsumo"),
        # 1300 / 2600 + 2 honba (200 from each player); the winner also collects 1 stick.
        pytest.param(tsumo(who=1, ten="20,5200,0", ba="2,1", sc="250,-28,250,68,250,-15,250,-15"),
                     id="non-dealer-tsumo"),
    ],
)
def test_a_hand_is_verified_when_its_recorded_score_changes_are_its_points_plus_honba_plus_riichi_sticks(xml):
    assert only_hand(xml)["quarantineReasons"] == []


@pytest.mark.parametrize(
    ("xml", "reasons"),
    [
        # The discarder lost 7700 and the winner gained 7700, but the hand is worth 8000.
        pytest.param(ron_8000(sc="250,0,250,77,250,0,250,-77"), ["payments"], id="points-short"),
        # 1 honba on the table, but the discarder paid only the points.
        pytest.param(ron_8000(ba="1,0", sc="250,0,250,80,250,0,250,-80"), ["payments"], id="honba-unpaid"),
        # 1 riichi stick on the table, but the winner gained only the points.
        pytest.param(ron_8000(ba="0,1", sc="250,0,250,80,250,0,250,-80"), ["payments"], id="stick-not-collected"),
        # Seat 2 paid for seat 3's discard.
        pytest.param(ron_8000(sc="250,0,250,80,250,-80,250,0"), ["payments"], id="wrong-payer"),
        # 5200 from a non-dealer tsumo is 2600 from the dealer and 1300 from each non-dealer,
        # but seat 2 paid the dealer's share.
        pytest.param(tsumo(who=1, ten="20,5200,0", sc="250,-13,250,52,250,-26,250,-13"), ["payments"],
                     id="tsumo-split-wrong"),
        # 1000 from a non-dealer tsumo would be 400 / 300 / 300, but the dealer always pays twice
        # a non-dealer's share or 100 less (both are rounded up to 100), so no hand is worth 1000:
        # the cross-check can't match it either.
        pytest.param(tsumo(who=1, ten="20,1000,0", sc="250,-4,250,10,250,-3,250,-3"), ["payments", "cross-check"],
                     id="points-cannot-be-split"),
        # Pao: seat 2 is liable for a daisangen and pays the whole tsumo alone.
        pytest.param(daisangen_tsumo(sc="250,0,250,320,250,-320,250,0"), ["payments"], id="pao"),
    ],
)
def test_a_hand_whose_recorded_score_changes_disagree_with_its_payments_is_quarantined(xml, reasons):
    assert only_hand(xml)["quarantineReasons"] == reasons
