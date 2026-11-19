"""Plain values: the facts about a hand that drills filter on directly, worked out as each hand is
read from its log. The limit tier is a plain value and also part of the answer key.

Seat 0 deals in East 1. Unless a test says otherwise, seat 1 (South) wins by ron on seat 0's discard.
"""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import Wall, closed_win, game, ids, init, riichi, turns, win

LOG_ID = "2024010112gm-00a9-0000-0123abcd"

# Seat 1 declares riichi on its second turn; its next discard closes the ippatsu window.
SEAT_1_IN_RIICHI = turns(2) + riichi(1) + turns(4, first_seat=2)


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def pinfu_and_dora(dora: str, *, ten: str, yaku: str) -> str:
    # 123m 4p 0p 6p 99p 23s 789s, won on 4s: pinfu and aka dora, plus the dora the indicators name.
    wall = Wall()
    return game(init(), win(wall, concealed="123m406p99p23789s", winning="4s", dora=dora, ten=ten, yaku=yaku))


def chinitsu(*, ten: str, yaku: str, in_riichi: bool = False) -> str:
    # 123m 234m 456m 789m 99m, won on 4m, with the 8m naming the three 9m as dora: pinfu, ittsu,
    # chinitsu and dora 3, 12 han.
    wall = Wall()
    moves = SEAT_1_IN_RIICHI if in_riichi else ""
    return game(init(), moves, win(wall, concealed="123456789m99m23m", winning="4m", dora="8m",
                                   ura="3z" if in_riichi else None, ten=ten, yaku=yaku))


def closed_triplets_in_riichi() -> str:
    # In riichi: 13m 222p 999s 456s 55z, won on 2m, with the 1p naming the three 2p as dora: riichi
    # and dora 3, 4 han 50 fu.
    wall = Wall()
    return game(init(), SEAT_1_IN_RIICHI, win(wall, concealed="13m222p999s456s55z", winning="2m", dora="1p",
                                              ura="7m", ten="50,8000,1", yaku="1,1,52,3,53,0"))


def daisangen() -> str:
    # Triplets of Haku, Hatsu and Chun with 123m, won on 9p, a single wait: daisangen.
    wall = Wall()
    return game(init(), win(wall, concealed="555z666z777z123m9p", winning="9p", dora="1p", ten="60,32000,5",
                            yakuman="39"))


def daisangen_and_tsuuiisou() -> str:
    # Triplets of Haku, Hatsu and Chun with East East South South, won on East: tsuuiisou and
    # daisangen, two yakuman.
    wall = Wall()
    return game(init(), win(wall, concealed="555z666z777z11z22z", winning="1z", dora="1p", ten="60,64000,5",
                            yakuman="42,39"))


@pytest.mark.parametrize(
    ("xml", "limit_tier"),
    [
        pytest.param(game(init(), closed_win()), "none", id="none"),  # pinfu, 1 han 30 fu
        pytest.param(pinfu_and_dora("8p1m", ten="30,8000,1", yaku="7,1,52,3,54,1"), "mangan", id="mangan"),
        pytest.param(closed_triplets_in_riichi(), "mangan", id="mangan-at-4-han-from-fu"),
        pytest.param(pinfu_and_dora("8p8p", ten="30,12000,2", yaku="7,1,52,4,54,1"), "haneman", id="haneman"),
        pytest.param(pinfu_and_dora("8p8p1m3s", ten="30,16000,3", yaku="7,1,52,6,54,1"), "baiman", id="baiman"),
        pytest.param(chinitsu(ten="30,24000,4", yaku="7,1,24,2,35,6,52,3"), "sanbaiman", id="sanbaiman"),
        # The same hand in riichi has 13 han without a yakuman.
        pytest.param(chinitsu(ten="30,32000,5", yaku="1,1,7,1,24,2,35,6,52,3,53,0", in_riichi=True),
                     "kazoe-yakuman", id="kazoe-yakuman"),
        pytest.param(daisangen(), "yakuman", id="yakuman"),
        pytest.param(daisangen_and_tsuuiisou(), "yakuman", id="two-yakuman"),
    ],
)
def test_the_answer_key_holds_the_limit_tier_tenhou_recorded(xml, limit_tier):
    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert hand["answerKey"]["limitTier"] == limit_tier
