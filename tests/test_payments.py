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
