"""A hand's situation worked out from the game's moves, and check 4 (stage 1, one log at a time).

Tenhou's live wall holds 70 tiles once the hands are dealt. Each kan moves one
more tile into the dead wall, so the last tile is the live wall's 70th draw,
less one per kan. Draws after a kan come from the dead wall and don't count.
"""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import (
    CLOSED_HAND,
    KAMICHA,
    added_kan,
    agari,
    call,
    closed_kan,
    discard,
    draw,
    game,
    ids,
    init,
    m,
    open_kan,
    pon,
    turns,
)

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def tsumo(who: int, yaku: str, ten: str = "20,2700,0", dealer: int = 0) -> str:
    """CLOSED_HAND won by `who` on a draw of 4s (84)."""
    return agari(who=who, from_who=who, hai=CLOSED_HAND, machi=84, ten=ten, yaku=yaku, dealer=dealer)


def ron(who: int, from_who: int, yaku: str, ten: str = "30,2000,0") -> str:
    """CLOSED_HAND won by `who` on a discard of 4s (84) by `from_who`."""
    return agari(who=who, from_who=from_who, hai=CLOSED_HAND, machi=84, ten=ten, yaku=yaku)


# A closed kan of East beside 123p 789p 123s and a 9s, won on the other 9s (105).
EAST_KAN = closed_kan(108)
BESIDE_EAST_KAN = ids(36, 40, 44, 60, 64, 68, 72, 76, 80, 104, 105)


def tsumo_after_east_kan(who: int, yaku: str, ten: str = "60,12000,1", dealer: int = 0) -> str:
    """A hand with EAST_KAN won by `who` on a draw of 9s (105)."""
    return agari(who=who, from_who=who, hai=BESIDE_EAST_KAN, m=m(EAST_KAN), machi=105, ten=ten, yaku=yaku,
                 dealer=dealer)


def test_a_tsumo_on_the_live_walls_last_tile_is_on_the_last_tile():
    # 69 turns leave one tile in the live wall; seat 1 draws it and wins: menzen tsumo, haitei, pinfu.
    xml = game(init(), turns(69), draw(1, 84), tsumo(who=1, yaku="0,1,5,1,7,1"))

    assert only_hand(xml)["situation"]["lastTile"] is True


def test_a_tsumo_before_the_live_walls_last_tile_is_not_on_the_last_tile():
    xml = game(init(), turns(68), draw(0, 84), tsumo(who=0, yaku="0,1,7,1", ten="20,2100,0"))

    assert only_hand(xml)["situation"]["lastTile"] is False


def test_a_ron_on_the_discard_after_the_live_walls_last_tile_is_on_the_last_tile():
    # Seat 1 draws the last tile and discards 4s; seat 2 wins on it: houtei, pinfu.
    xml = game(init(), turns(69), draw(1, 84), discard(1, 84), ron(who=2, from_who=1, yaku="6,1,7,1"))

    assert only_hand(xml)["situation"]["lastTile"] is True


def test_a_ron_before_the_live_walls_last_tile_is_not_on_the_last_tile():
    xml = game(init(), turns(68), draw(0, 84), discard(0, 84), ron(who=2, from_who=0, yaku="7,1", ten="30,1000,0"))

    assert only_hand(xml)["situation"]["lastTile"] is False


def test_each_kan_takes_a_tile_from_the_live_wall_and_the_draw_after_it_does_not_count():
    # Seat 2 draws, makes a closed kan of East and draws again from the dead wall. The live
    # wall is down to 69 draws, so seat 0's draw after 68 others is its last tile.
    kan_turn = draw(2, 108) + call(2, closed_kan(108)) + draw(2, 130) + discard(2, 130)
    xml = game(init(), turns(2), kan_turn, turns(65, first_seat=3), draw(0, 84),
               tsumo(who=0, yaku="0,1,5,1,7,1", ten="20,3900,0"))

    assert only_hand(xml)["situation"]["lastTile"] is True


def test_a_tsumo_on_the_draw_after_a_kan_is_not_on_the_last_tile_even_when_the_kan_empties_the_live_wall():
    # Seat 0 draws the second-last tile and makes a closed kan, which leaves the live wall empty.
    # Its draw from the dead wall wins: menzen tsumo, rinshan, seat and round wind East.
    xml = game(init(), turns(68), draw(0, 108), call(0, EAST_KAN), draw(0, 105),
               tsumo_after_east_kan(who=0, yaku="0,1,4,1,10,1,14,1"))

    assert only_hand(xml)["situation"]["lastTile"] is False


EAST_PON = pon((109, 110, 111), called=109, from_seat=KAMICHA)
EAST_ADDED_KAN = added_kan((109, 110, 111), called=109, from_seat=KAMICHA)
EAST_OPEN_KAN = open_kan(108, from_seat=KAMICHA)


@pytest.mark.parametrize(
    ("moves", "code", "yaku"),
    [
        # Seat 0 draws the fourth East and makes a closed kan: menzen tsumo, rinshan, seat and round wind.
        (turns(1, first_seat=3) + draw(0, 108) + call(0, EAST_KAN), EAST_KAN, "0,1,4,1,10,1,14,1"),
        # Seat 3 discards an East and seat 0 makes an open kan of it: rinshan, seat and round wind.
        (draw(3, 108) + discard(3, 108) + call(0, EAST_OPEN_KAN), EAST_OPEN_KAN, "4,1,10,1,14,1"),
        # Seat 0 called a pon of East from seat 3 and adds the fourth East it draws: as above.
        (draw(3, 109) + discard(3, 109) + call(0, EAST_PON) + discard(0, 135) + turns(3, first_seat=1)
         + draw(0, 108) + call(0, EAST_ADDED_KAN), EAST_ADDED_KAN, "4,1,10,1,14,1"),
    ],
    ids=["closed-kan", "open-kan", "added-kan"],
)
def test_a_tsumo_on_the_draw_after_the_winners_own_kan_is_drawn_after_a_kan(moves, code, yaku):
    win = agari(who=0, from_who=0, hai=BESIDE_EAST_KAN, m=m(code), machi=105, ten="60,12000,1", yaku=yaku)
    xml = game(init(), turns(3), moves, draw(0, 105), win)

    assert only_hand(xml)["situation"]["rinshan"] is True


def test_a_tsumo_on_the_kan_makers_next_draw_from_the_live_wall_is_not_drawn_after_a_kan():
    xml = game(init(), draw(0, 108), call(0, EAST_KAN), draw(0, 130), discard(0, 130), turns(3, first_seat=1),
               draw(0, 105), tsumo_after_east_kan(who=0, yaku="0,1,10,1,14,1", ten="50,9600,0"))

    assert only_hand(xml)["situation"]["rinshan"] is False


def test_a_tsumo_after_another_players_kan_is_not_drawn_after_a_kan():
    kan_turn = draw(2, 108) + call(2, EAST_KAN) + draw(2, 130) + discard(2, 130)
    xml = game(init(), turns(2), kan_turn, draw(3, 84), tsumo(who=3, yaku="0,1,7,1"))

    assert only_hand(xml)["situation"]["rinshan"] is False


def four_sou_added_kan(seat: int) -> str:
    """`seat` calls a pon of 4s from the player before, then draws the fourth 4s (84) and adds it to the
    pon. Five draws from the live wall."""
    pon_tiles = (85, 86, 87)
    before = (seat - 1) % 4
    return (draw(before, 85) + discard(before, 85) + call(seat, pon(pon_tiles, called=85, from_seat=KAMICHA))
            + discard(seat, 135) + turns(3, first_seat=(seat + 1) % 4) + draw(seat, 84)
            + call(seat, added_kan(pon_tiles, called=85, from_seat=KAMICHA)))


def test_a_ron_on_the_tile_added_to_a_kan_robs_a_kan():
    # Seat 2 wins on the 4s seat 0 adds to its kan: chankan, pinfu.
    xml = game(init(), turns(3), four_sou_added_kan(seat=0), ron(who=2, from_who=0, yaku="3,1,7,1"))

    assert only_hand(xml)["situation"]["chankan"] is True


def test_a_ron_on_the_discard_after_an_added_kan_does_not_rob_a_kan():
    # Seat 0 draws from the dead wall after its kan and discards a 4s, which seat 2 wins on: pinfu.
    xml = game(init(), turns(3), four_sou_added_kan(seat=0), draw(0, 130), discard(0, 84),
               ron(who=2, from_who=0, yaku="7,1", ten="30,1000,0"))

    assert only_hand(xml)["situation"]["chankan"] is False


def test_a_ron_robbing_a_kan_is_not_on_the_last_tile_even_when_the_kan_empties_the_live_wall():
    # After 69 draws seat 1's added kan moves the live wall's last tile to the dead wall.
    # Seat 3 robs the kan: chankan, pinfu.
    xml = game(init(), turns(64), four_sou_added_kan(seat=1), ron(who=3, from_who=1, yaku="3,1,7,1"))

    assert only_hand(xml)["situation"]["lastTile"] is False
