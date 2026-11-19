"""Plain values: the facts about a hand that drills filter on directly, worked out as each hand is
read from its log. The limit tier is a plain value and also part of the answer key.

Seat 0 deals in East 1. Unless a test says otherwise, seat 1 (South) wins by ron on seat 0's discard.
"""

import pytest

from logparser.plain_values import PLAIN_VALUE_NAMES
from logparser.tenhou import parse_log
from tenhou_xml import (CALLED_HAND, CALLED_HAND_CALLS, KAMICHA, Wall, added_kan, agari, called_win, closed_kan,
                        closed_win, game, ids, init, m, riichi, turns, win)

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


def daisangen(dora: str = "1p") -> str:
    # Triplets of Haku, Hatsu and Chun with 123m, won on 9p, a single wait: daisangen.
    wall = Wall()
    return game(init(), win(wall, concealed="555z666z777z123m9p", winning="9p", dora=dora, ten="60,32000,5",
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


def test_a_hand_carries_its_plain_values():
    # East 1 with 2 honba and 1 riichi stick on the table. Seat 1 calls a chi of 3m 4m red 5m and a
    # pon of Chun, then rons seat 0 on 4s with 456p 99p 23s: chun and aka dora, 2 han, raw fu 24.
    xml = game(init(honba=2, sticks=1), agari(who=1, from_who=0, ba="2,1", hai=CALLED_HAND, m=CALLED_HAND_CALLS,
                                              machi=84, ten="30,2000,0", yaku="20,1,54,1", dora="116"))

    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert hand["plainValues"] == {
        "han": 2,
        "fu": 30,
        "rawFu": 24,
        "limitTier": "none",
        "dealer": False,
        "tsumo": False,
        "open": True,
        "yaku": ["chun", "aka-dora"],
        "doraCount": 1,
        "honba": 2,
        "riichiSticks": 1,
        "callTypes": ["chi", "pon"],
    }


def test_the_plain_value_names_drills_can_filter_on_are_the_ones_each_hand_carries():
    hand = only_hand(game(init(), closed_win(who=1)))

    assert tuple(hand["plainValues"]) == PLAIN_VALUE_NAMES


def test_the_dora_count_adds_up_the_dora_aka_dora_and_ura_dora_tenhou_recorded():
    # The dealer, in riichi, wins by tsumo with 123m 4p 0p 6p 99p 23s 789s on 4s. The 8p names the
    # pair of 9p as dora and the ura dora indicator 3s names the 4s: riichi, menzen tsumo, pinfu,
    # dora 2, aka dora 1 and ura dora 1, 7 han.
    wall = Wall()
    xml = game(init(), turns(1), riichi(0), turns(7, first_seat=1),
               win(wall, who=0, tsumo=True, concealed="123m406p99p23789s", winning="4s", dora="8p", ura="3s",
                   ten="20,18000,2", yaku="1,1,0,1,7,1,52,2,54,1,53,1"))

    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert hand["plainValues"]["doraCount"] == 4


def test_a_yakuman_has_a_dora_count_of_0_as_tenhou_records_no_dora_with_it():
    # The 2m names the 3m the daisangen holds as dora.
    hand = only_hand(daisangen(dora="2m"))

    assert hand["quarantineReasons"] == []
    assert hand["plainValues"]["doraCount"] == 0


def closed_kan_honitsu() -> str:
    # A closed kan of North; 123m 567m 78m 33z, won on 9m: honitsu, 3 han 70 fu.
    return game(init(), agari(who=1, from_who=0, hai=ids(0, 4, 8, 17, 20, 24, 25, 28, 32, 116, 117),
                              m=m(closed_kan(120)), machi=32, ten="70,8000,1", yaku="34,3"))


def closed_kan_then_added_kan() -> str:
    # A closed kan of 5m, then an added kan of 5p onto a pon from kamicha; 234s 678s 33m, won on
    # 3m: tanyao and aka dora 2, 3 han 50 fu.
    return game(init(), agari(who=1, from_who=0, hai=ids(8, 9, 76, 80, 84, 92, 96, 100), machi=9,
                              m=m(closed_kan(16), added_kan((53, 54, 55), called=54, from_seat=KAMICHA)),
                              ten="50,6400,0", yaku="8,1,54,2"))


@pytest.mark.parametrize(
    ("xml", "is_open", "call_types"),
    [
        pytest.param(game(init(), closed_win()), False, [], id="no-calls"),
        pytest.param(closed_kan_honitsu(), False, ["closed-kan"], id="closed-kan-only"),
        pytest.param(game(init(), called_win()), True, ["chi", "pon"], id="chi-and-pon"),
        pytest.param(closed_kan_then_added_kan(), True, ["closed-kan", "added-kan"], id="closed-kan-and-added-kan"),
    ],
)
def test_a_hand_is_open_once_it_has_a_call_other_than_a_closed_kan_and_lists_its_call_types_in_order(
        xml, is_open, call_types):
    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert (hand["plainValues"]["open"], hand["plainValues"]["callTypes"]) == (is_open, call_types)
