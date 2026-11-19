"""A hand's situation worked out from the game's moves, and check 4 (stage 1, one log at a time).

Tenhou's live wall holds 70 tiles once the hands are dealt. Each kan moves one
more tile into the dead wall, so the last tile is the live wall's 70th draw,
less one per kan. Draws after a kan come from the dead wall and don't count.
"""

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, agari, call, closed_kan, discard, draw, game, ids, init, m, turns

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
