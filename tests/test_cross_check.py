"""Check 6, the cross-check: the `mahjong` library recalculates each hand under Tenhou rules and
must match the answer key exactly. A hand whose cross-check matched gets its fu breakdown and
raw fu in its answer key (stage 1, one log at a time)."""

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, agari, game, init

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def test_a_hand_the_library_scores_as_tenhou_did_is_verified_with_its_fu_breakdown_and_raw_fu():
    # CLOSED_HAND ron on 4s, a two-sided wait: pinfu, 1 han 30 fu.
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1"))

    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert (hand["answerKey"]["rawFu"], hand["answerKey"]["fuBreakdown"]) == (
        30, [{"key": "base", "fu": 20}, {"key": "closed-ron", "fu": 10}])
