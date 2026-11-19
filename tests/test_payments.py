"""Payments in the answer key and check 5 (stage 1, one log at a time)."""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, agari, game, init

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


def test_in_a_double_ron_the_first_winner_collects_the_honba_and_the_riichi_sticks():
    # East 3 with 1 honba and 1 stick carried in. Seat 0 deals into seats 1 and 3. The second
    # winner's ba still shows the honba, but Tenhou gives the honba and sticks to the first winner.
    xml = game(
        init(round_number=2, honba=1, sticks=1),
        agari(who=1, from_who=0, ba="1,1", hai=CLOSED_HAND, machi=84, ten="30,2000,0", yaku="7,1,52,1",
              sc="250,-23,250,33,250,0,240,0"),
        agari(who=3, from_who=0, ba="1,0", hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1",
              sc="227,-10,283,0,250,0,240,10"),
    )

    first, second = parse_log(LOG_ID, xml).hands

    assert (first["id"], second["id"]) == (f"{LOG_ID}/0/0", f"{LOG_ID}/0/1")
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
