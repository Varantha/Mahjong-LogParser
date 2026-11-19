"""Payments in the answer key and check 5 (stage 1, one log at a time)."""

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
