"""Checks 2 and 3: tile limits and the winning tile (stage 1, one log at a time)."""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import (
    CLOSED_HAND,
    KAMICHA,
    TOIMEN,
    added_kan,
    agari,
    call,
    chi,
    closed_kan,
    discard,
    draw,
    game,
    ids,
    init,
    m,
    pon,
    riichi,
    turns,
)

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


# Eleven concealed tiles to go with a closed kan of 5m (16 17 18 19): 123p 789p 123s 99s, ron on 9s.
BESIDE_A_KAN = ids(36, 40, 44, 60, 64, 68, 72, 76, 80, 104, 105)


@pytest.mark.parametrize(
    "win",
    [
        # 9p 9p (68 69) concealed, and 9p (70 71 69) as three dora indicators.
        pytest.param(agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1",
                           dora="70,71,69"), id="concealed-and-dora-indicators"),
        # A closed kan of 5m, and 5m (17) again as the ura dora indicator.
        pytest.param(agari(who=1, from_who=0, hai=BESIDE_A_KAN, m=m(closed_kan(16)), machi=104,
                           ten="40,2600,0", yaku="1,1,53,0", ura="17"), id="call-and-ura-dora-indicators"),
        # A pon of Chun (132 133 134), and Chun Chun (134 135) as the pair.
        pytest.param(agari(who=1, from_who=0, hai=ids(48, 53, 56, 76, 80, 84, 134, 135),
                           m=m(chi((8, 12, 16), called=16), pon((132, 133, 134), called=133, from_seat=TOIMEN)),
                           machi=84, ten="30,2000,0", yaku="20,1,54,1"), id="call-and-concealed"),
    ],
)
def test_a_hand_with_a_fifth_copy_of_a_tile_is_quarantined_for_its_tile_limits(win):
    assert only_hand(game(init(), win))["quarantineReasons"] == ["tile-limits"]


@pytest.mark.parametrize(
    "win",
    [
        # 4p red-5p 6p (48 52 56) concealed, and the red 5p again as the dora indicator.
        pytest.param(agari(who=1, from_who=0, hai=ids(0, 4, 8, 48, 52, 56, 68, 69, 76, 80, 84, 96, 100, 104),
                           machi=84, ten="30,2000,0", yaku="7,1,54,1", dora="52"), id="concealed-and-dora-indicator"),
        # A chi of 3m 4m red-5m (8 12 16), and the red 5m again as the ura dora indicator.
        pytest.param(agari(who=1, from_who=0, hai=ids(48, 53, 56, 68, 69, 76, 80, 84),
                           m=m(chi((8, 12, 16), called=16), pon((132, 133, 134), called=133, from_seat=TOIMEN)),
                           machi=84, ten="30,2000,0", yaku="20,1,54,1", ura="16"), id="call-and-ura-dora-indicator"),
    ],
)
def test_a_hand_with_two_red_fives_of_one_suit_is_quarantined_for_its_tile_limits(win):
    assert only_hand(game(init(), win))["quarantineReasons"] == ["tile-limits"]


def test_four_copies_of_a_tile_and_one_red_five_per_suit_are_within_the_tile_limits():
    # 9p: 68 69 concealed, 70 a dora indicator, 71 an ura dora indicator. One red five in each
    # suit: 16 (0m) and 52 (0p) concealed, 88 (0s) a dora indicator. Seat 1 is in riichi:
    # riichi, pinfu and aka dora 2, 4 han 30 fu.
    hai = ids(8, 12, 16, 48, 52, 56, 68, 69, 76, 80, 84, 96, 100, 104)
    win = agari(who=1, from_who=0, hai=hai, machi=84, ten="30,7700,0", yaku="1,1,7,1,54,2,53,0",
                dora="70,88", ura="71,120")

    assert only_hand(game(init(), turns(2), riichi(1), turns(4, first_seat=2), win))["quarantineReasons"] == []


@pytest.mark.parametrize(
    "machi",
    [
        pytest.param(85, id="another-copy-of-a-concealed-tile"),  # CLOSED_HAND holds 4s as 84
        pytest.param(120, id="a-tile-the-hand-lacks"),  # North
    ],
)
def test_a_hand_whose_winning_tile_is_not_among_its_concealed_tiles_is_quarantined(machi):
    win = agari(who=1, from_who=0, hai=CLOSED_HAND, machi=machi, ten="30,1000,0", yaku="7,1")

    assert only_hand(game(init(), win))["quarantineReasons"] == ["winning-tile"]


def ron(*moves: str, yaku: str = "7,1", ten: str = "30,1000,0") -> str:
    """CLOSED_HAND: seat 1 rons seat 0 on 4s (84), after the given moves and nothing else."""
    return game(init(), *moves, agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten=ten, yaku=yaku,
                                      winning_move=False))


def tsumo(*moves: str) -> str:
    """CLOSED_HAND: seat 1 wins by tsumo on 4s (84), after a turn each and then the given moves.

    The turns keep the win off the player's first draw, which would be chiihou."""
    return game(init(), turns(4), *moves, agari(who=1, from_who=1, hai=CLOSED_HAND, machi=84, ten="20,1500,0", yaku="0,1,7,1",
                                      winning_move=False))


@pytest.mark.parametrize(
    "xml",
    [
        pytest.param(ron(draw(0, 120), discard(0, 84)), id="ron-on-the-discard"),
        pytest.param(tsumo(discard(0, 120), draw(1, 84)), id="tsumo-on-the-draw"),
    ],
)
def test_a_hand_won_on_the_tile_its_last_move_handed_over_passes_the_winning_tile_check(xml):
    assert only_hand(xml)["quarantineReasons"] == []


@pytest.mark.parametrize(
    "xml",
    [
        pytest.param(ron(draw(0, 85), discard(0, 68)), id="ron-on-another-tile-than-the-discard"),
        pytest.param(ron(discard(3, 84)), id="ron-on-a-discard-by-another-seat"),
        pytest.param(ron(discard(0, 84), draw(1, 120)), id="ron-on-an-earlier-discard"),
        pytest.param(ron(draw(0, 84)), id="ron-on-a-draw"),
        pytest.param(ron(), id="ron-without-a-move"),
        pytest.param(tsumo(draw(1, 68)), id="tsumo-on-another-tile-than-the-draw"),
        pytest.param(tsumo(draw(0, 84)), id="tsumo-on-a-draw-by-another-seat"),
        pytest.param(tsumo(draw(1, 84), discard(1, 120)), id="tsumo-on-an-earlier-draw"),
        pytest.param(tsumo(discard(0, 84)), id="tsumo-on-a-discard"),
    ],
)
def test_a_hand_whose_winning_tile_is_not_the_tile_its_last_move_handed_over_is_quarantined(xml):
    assert only_hand(xml)["quarantineReasons"] == ["winning-tile"]


@pytest.mark.parametrize(
    "xml",
    [
        pytest.param(ron(draw(0, 120), '<REACH who="0" step="1"/>', discard(0, 84)), id="ron-on-a-riichi-declaration"),
        pytest.param(ron(draw(0, 120), discard(0, 84), '<BYE who="0"/>'), id="ron-after-the-discarder-disconnects"),
        pytest.param(tsumo(draw(1, 84), '<UN n0="Alice"/>'), id="tsumo-after-a-player-reconnects"),
        # Seat 0 adds 4s (84) to its pon of 4s (85 86 87) and seat 1 robs it: chankan, pinfu.
        pytest.param(ron(draw(0, 84), call(0, added_kan((85, 86, 87), called=86, from_seat=KAMICHA)),
                         yaku="3,1,7,1", ten="30,2000,0"),
                     id="ron-on-the-tile-added-to-a-kan"),
    ],
)
def test_tags_that_are_no_moves_do_not_hide_the_move_that_handed_over_the_winning_tile(xml):
    assert only_hand(xml)["quarantineReasons"] == []


@pytest.mark.parametrize(
    "xml",
    [
        # Seat 0 adds 4s (85) to its pon of 4s (84 86 87): the pon's tiles were never on offer.
        pytest.param(ron(draw(0, 85), call(0, added_kan((84, 86, 87), called=86, from_seat=KAMICHA)),
                         yaku="3,1,7,1", ten="30,2000,0"),
                     id="ron-on-a-tile-of-the-pon-a-kan-was-added-to"),
        pytest.param(ron(draw(2, 84), call(2, added_kan((85, 86, 87), called=86, from_seat=KAMICHA))),
                     id="ron-on-a-kan-added-by-another-seat"),
        pytest.param(ron(discard(3, 84), call(0, pon((84, 85, 86), called=84, from_seat=KAMICHA))),
                     id="ron-on-a-tile-called-for-a-pon"),
    ],
)
def test_a_ron_on_a_call_other_than_the_tile_added_to_a_kan_is_quarantined(xml):
    assert only_hand(xml)["quarantineReasons"] == ["winning-tile"]


def test_both_winners_of_a_double_ron_win_on_the_one_discard():
    xml = game(
        init(), draw(0, 120), discard(0, 84),
        agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1", winning_move=False),
        agari(who=3, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1", winning_move=False),
    )

    assert [hand["quarantineReasons"] for hand in parse_log(LOG_ID, xml).hands] == [[], []]


def test_a_hand_that_fails_several_checks_records_a_reason_code_for_each():
    # CLOSED_HAND without its 1m (13 tiles), a fifth 9p among the dora indicators, a winning tile
    # the hand lacks, and a discarder who paid 7700 for a 1000-point hand.
    thirteen_tiles = ids(4, 8, 48, 53, 56, 68, 69, 76, 80, 84, 96, 100, 104)
    win = agari(who=1, from_who=0, hai=thirteen_tiles, machi=85, ten="30,1000,0", yaku="7,1", dora="70,71,69",
                sc="250,-77,250,77,250,0,250,0")

    assert only_hand(game(init(), win))["quarantineReasons"] == ["tile-total", "tile-limits", "winning-tile",
                                                                 "payments"]
