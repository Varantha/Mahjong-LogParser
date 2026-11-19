"""Check 6, the cross-check: the `mahjong` library recalculates each hand under Tenhou rules and
must match the answer key exactly. A hand whose cross-check matched gets its fu breakdown and
raw fu in its answer key (stage 1, one log at a time).

Seat 0 deals in East 1. Unless a test says otherwise, seat 1 (South) wins: by ron on seat 0's
discard, or by tsumo on its second draw.
"""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import (
    CLOSED_HAND,
    KAMICHA,
    SHIMOCHA,
    TOIMEN,
    Wall,
    agari,
    chi,
    closed_kan,
    game,
    ids,
    init,
    open_kan,
    pon,
    riichi,
    turns,
    win,
)

LOG_ID = "2024010112gm-00a9-0000-0123abcd"

# The moves before a tsumo on the winner's second draw, so it is not on the first draw.
BEFORE_A_TSUMO = turns(4)
# Seat 1 declares riichi on its second turn; its next discard closes the ippatsu window.
SEAT_1_IN_RIICHI = turns(2) + riichi(1) + turns(4, first_seat=2)


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


@pytest.mark.parametrize(
    ("ten", "yaku"),
    [
        pytest.param("30,1000,0", "8,1", id="yaku"),  # tanyao in place of pinfu
        pytest.param("30,2000,0", "7,1,52,1", id="han-and-points"),  # a dora the hand doesn't hold
        pytest.param("40,1300,0", "7,1", id="fu-and-points"),
        pytest.param("30,1500,0", "7,1", id="points"),
        pytest.param("30,1000,1", "7,1", id="limit-tier"),  # mangan
    ],
)
def test_a_hand_the_library_scores_differently_from_tenhou_is_quarantined_without_a_fu_breakdown(ten, yaku):
    # CLOSED_HAND ron on 4s is pinfu, 1 han 30 fu, 1000; Tenhou's recorded result says otherwise.
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten=ten, yaku=yaku))

    hand = only_hand(xml)

    assert hand["quarantineReasons"] == ["cross-check"]
    assert (hand["answerKey"]["rawFu"], hand["answerKey"]["fuBreakdown"]) == (None, None)


def test_a_hand_the_library_refuses_to_score_is_quarantined_without_a_fu_breakdown():
    # 123m 456p 234s 789s and a pair of East, won on 4s: the pair of the round wind rules out
    # pinfu, so the hand has no yaku, whatever Tenhou's result says.
    hai = ids(0, 4, 8, 48, 53, 56, 76, 80, 84, 96, 100, 104, 108, 109)
    xml = game(init(), agari(who=1, from_who=0, hai=hai, machi=84, ten="30,1000,0", yaku="7,1"))

    hand = only_hand(xml)

    assert hand["quarantineReasons"] == ["cross-check-refused"]
    assert (hand["answerKey"]["rawFu"], hand["answerKey"]["fuBreakdown"]) == (None, None)


def open_tanyao() -> str:
    # Chi 234m; 567p 45s 678s 22p, won on 3s: tanyao, 1 han 30 fu.
    wall = Wall()
    run = wall.take("234m")
    return game(init(), win(wall, calls=(chi(run, called=run[0]),), concealed="567p45s678s22p", winning="3s",
                            ten="30,1000,0", yaku="8,1"))


def red_five_in_a_call() -> str:
    # Pon of 0s 5s 5s; 234m 678m 11p 22z, won by tsumo on South: seat wind South and aka dora,
    # 2 han 40 fu.
    wall = Wall()
    fives = wall.take("055s")
    return game(init(), BEFORE_A_TSUMO, win(wall, calls=(pon(fives, called=fives[1], from_seat=TOIMEN),),
                                            concealed="234m678m11p22z", winning="2z", tsumo=True, dora="3z",
                                            ten="40,2700,0", yaku="11,1,54,1"))


def kazoe_yakuman() -> str:
    # 123m 123m 45m 789m 99m in riichi, won by tsumo on 6m, with 8m indicating the three 9m as
    # dora: riichi, menzen tsumo, pinfu, iipeikou, ittsu, chinitsu and dora 3, 15 han.
    wall = Wall()
    return game(init(), SEAT_1_IN_RIICHI, win(wall, concealed="1122334578999m", winning="6m", tsumo=True, dora="8m",
                                              ura="3z", ten="20,32000,5", yaku="1,1,0,1,7,1,9,1,24,2,35,6,52,3,53,0"))


def no_kiriage() -> str:
    # 123m 4p 0p 6p 99p 234s 789s, won on 4s, with 8p indicating the pair of 9p as dora: pinfu,
    # dora 2 and aka dora, 4 han 30 fu. Without kiriage that is 7700, not mangan.
    wall = Wall()
    return game(init(), win(wall, concealed="123m406p99p23789s", winning="4s", dora="8p", ten="30,7700,0",
                            yaku="7,1,52,2,54,1"))


def suuankou_tanki() -> str:
    # Concealed triplets of 1m, 5p, 2s and 7s, won by ron on 9p, a single wait: suuankou tanki,
    # a double yakuman elsewhere but a single one under Tenhou rules.
    wall = Wall()
    return game(init(), win(wall, concealed="111m555p222s777s9p", winning="9p", ten="60,32000,5", yakuman="41"))


@pytest.mark.parametrize(
    "xml",
    [
        pytest.param(open_tanyao(), id="open-tanyao"),
        pytest.param(red_five_in_a_call(), id="red-fives"),
        pytest.param(kazoe_yakuman(), id="kazoe-yakuman-at-13-han"),
        pytest.param(no_kiriage(), id="no-kiriage"),
        pytest.param(suuankou_tanki(), id="double-yakuman-forms-count-once"),
    ],
)
def test_the_library_scores_hands_under_tenhou_rules(xml):
    assert only_hand(xml)["quarantineReasons"] == []


def test_a_red_five_in_a_call_counts_in_the_fu_breakdown_which_adds_up_to_the_raw_fu():
    hand = only_hand(red_five_in_a_call())

    assert hand["quarantineReasons"] == []
    assert hand["tiles"]["calls"][0]["tiles"] == "055s"
    assert hand["answerKey"]["fu"] == 40
    assert (hand["answerKey"]["rawFu"], hand["answerKey"]["fuBreakdown"]) == (32, [
        {"key": "base", "fu": 20},
        {"key": "tsumo", "fu": 2},
        {"key": "closed-terminal-triplet", "fu": 8},
        {"key": "open-simple-triplet", "fu": 2},
    ])


def open_tanyao_tsumo() -> str:
    # open_tanyao's hand won by tsumo: tanyao, 1 han 30 fu.
    wall = Wall()
    run = wall.take("234m")
    return game(init(), BEFORE_A_TSUMO, win(wall, calls=(chi(run, called=run[0]),), concealed="567p45s678s22p",
                                            winning="3s", tsumo=True, ten="30,1100,0", yaku="8,1"))


def pinfu_tsumo() -> str:
    # CLOSED_HAND won by tsumo: menzen tsumo and pinfu, 2 han 20 fu.
    return game(init(), BEFORE_A_TSUMO, agari(who=1, from_who=1, hai=CLOSED_HAND, machi=84, ten="20,1500,0",
                                              yaku="0,1,7,1"))


def chiitoitsu() -> str:
    # 11m 44m 77m 22p 88p 33s and 6s, won on 6s: chiitoitsu, 2 han 25 fu.
    wall = Wall()
    return game(init(), win(wall, concealed="114477m2288p336s", winning="6s", ten="25,1600,0", yaku="22,2"))


def kokushi_musou() -> str:
    # 1m 1m 9m 1p 9p 1s 9s and East to Hatsu, won on Chun: kokushi musou, which has no fu.
    wall = Wall()
    return game(init(), win(wall, concealed="119m19p19s123456z", winning="7z", dora="2m", ten="0,32000,5",
                            yakuman="47"))


def closed_sets_yakuhai_pair_and_closed_wait() -> str:
    # In riichi: 13m 222p 999s 456s 55z, won by ron on 2m, a closed wait: riichi, 1 han 50 fu.
    wall = Wall()
    return game(init(), SEAT_1_IN_RIICHI, win(wall, concealed="13m222p999s456s55z", winning="2m", dora="7p",
                                              ura="7m", ten="50,1600,0", yaku="1,1,53,0"))


def open_sets_double_wind_pair_and_edge_wait() -> str:
    # The dealer (seat 0, East in East round): pon of Chun and open kan of 6p; 12s 789m 11z, won by
    # tsumo on 3s, an edge wait: chun, 1 han 40 fu, 700 all.
    wall = Wall()
    chun, six_pin = wall.take("777z"), wall.take("6666p")
    calls = (pon(chun, called=chun[0], from_seat=TOIMEN), open_kan(six_pin[0], from_seat=SHIMOCHA))
    return game(init(), BEFORE_A_TSUMO, win(wall, who=0, calls=calls, concealed="12s789m11z", winning="3s",
                                            tsumo=True, dora="9p", ten="40,2100,0", yaku="20,1"))


def kans_open_triplet_and_single_wait() -> str:
    # Pon of 3s, open kan of West, closed kans of 1p and of 5m (with the red 5m); 8s, won by ron on
    # the other 8s, a single wait: toitoi, sankantsu and aka dora, 5 han 90 fu, mangan.
    wall = Wall()
    three_sou, west, one_pin, five_man = wall.take("333s"), wall.take("3333z"), wall.take("1111p"), wall.take("0555m")
    calls = (pon(three_sou, called=three_sou[0], from_seat=KAMICHA), open_kan(west[0], from_seat=TOIMEN),
             closed_kan(one_pin[0]), closed_kan(five_man[0]))
    return game(init(), win(wall, calls=calls, concealed="8s", winning="8s", dora="1m", ten="90,8000,1",
                            yaku="28,2,27,2,54,1"))


@pytest.mark.parametrize(
    ("xml", "fu", "raw_fu", "fu_breakdown"),
    [
        # An open hand with no fu at all: raw fu 20, which Tenhou scores as 30.
        pytest.param(open_tanyao(), 30, 20, [("base", 20)], id="open-pinfu-shape-by-ron"),
        # The same shape by tsumo has the tsumo's 2 fu.
        pytest.param(open_tanyao_tsumo(), 30, 22, [("base", 20), ("tsumo", 2)], id="open-hand-without-fu-by-tsumo"),
        pytest.param(pinfu_tsumo(), 20, 20, [("base", 20)], id="pinfu-tsumo"),
        pytest.param(chiitoitsu(), 25, 25, [("chiitoitsu", 25)], id="chiitoitsu"),
        pytest.param(kokushi_musou(), 0, 0, [], id="kokushi-musou"),
        pytest.param(closed_sets_yakuhai_pair_and_closed_wait(), 50, 46,
                     [("base", 20), ("closed-ron", 10), ("closed-terminal-triplet", 8), ("closed-simple-triplet", 4),
                      ("yakuhai-pair", 2), ("kanchan-wait", 2)],
                     id="closed-triplets-yakuhai-pair-kanchan"),
        pytest.param(open_sets_double_wind_pair_and_edge_wait(), 40, 40,
                     [("base", 20), ("tsumo", 2), ("open-simple-kan", 8), ("open-terminal-triplet", 4),
                      ("double-wind-pair", 4), ("penchan-wait", 2)],
                     id="open-kan-open-triplet-double-wind-pair-penchan"),
        pytest.param(kans_open_triplet_and_single_wait(), 90, 88,
                     [("base", 20), ("closed-terminal-kan", 32), ("open-terminal-kan", 16), ("closed-simple-kan", 16),
                      ("open-simple-triplet", 2), ("tanki-wait", 2)],
                     id="kans-open-simple-triplet-tanki"),
    ],
)
def test_the_fu_breakdown_names_each_source_of_fu_under_a_contract_key(xml, fu, raw_fu, fu_breakdown):
    hand = only_hand(xml)

    assert hand["quarantineReasons"] == []
    assert (hand["answerKey"]["fu"], hand["answerKey"]["rawFu"], hand["answerKey"]["fuBreakdown"]) == (
        fu, raw_fu, [{"key": key, "fu": value} for key, value in fu_breakdown])
