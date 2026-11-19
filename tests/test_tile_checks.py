"""Checks 2 and 3: tile limits and the winning tile (stage 1, one log at a time)."""

import pytest

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, agari, chi, closed_kan, game, ids, init, m, pon, TOIMEN

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
    # suit: 16 (0m) and 52 (0p) concealed, 88 (0s) a dora indicator.
    hai = ids(8, 12, 16, 48, 52, 56, 68, 69, 76, 80, 84, 96, 100, 104)
    win = agari(who=1, from_who=0, hai=hai, machi=84, ten="30,3900,0", yaku="1,1,7,1,54,2,53,0",
                dora="70,88", ura="71,120")

    assert only_hand(game(init(), win))["quarantineReasons"] == []
