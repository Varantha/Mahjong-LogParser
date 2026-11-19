"""Reading hands out of a single Tenhou log (stage 1, one log at a time)."""

from logparser.tenhou import parse_log
from tenhou_xml import CLOSED_HAND, agari, game, ids, init

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def test_concealed_tiles_are_written_in_mpsz_with_man_first():
    xml = game(
        init(),
        agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40"),
    )

    hand = only_hand(xml)

    assert hand["tiles"]["concealed"] == "123m456p234789s11z"


def test_red_fives_are_written_as_zero():
    # 3m 4m red-5m, red-5p 5p 5p, 3s 4s red-5s, 6s 7s 8s, Haku Haku.
    hai = ids(8, 12, 16, 52, 53, 54, 80, 84, 88, 92, 96, 100, 124, 125)
    xml = game(init(), agari(who=1, from_who=0, hai=hai, machi=88, ten="40,5200,0", yaku="18,1,54,3"))

    hand = only_hand(xml)

    assert hand["tiles"]["concealed"] == "340m055p340678s55z"


def test_winning_tile_is_read_from_machi_not_from_the_previous_move():
    # The last move before the win is a discard of 9p (68) by seat 0, but
    # Tenhou's machi says the winning tile was 4s (84).
    xml = game(init(), "<T120/><D68/>", agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,1300,0", yaku="1,1,53,0", ura="40"))

    hand = only_hand(xml)

    assert hand["tiles"]["winningTile"] == "4s"


def test_dora_and_ura_dora_indicators_are_recorded_with_the_tiles():
    # Dora indicators Hatsu (130) and 2p (40, a kan dora); ura indicators 4z (120) and 2s (77).
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="40,1300,0",
                             yaku="1,1,53,0", dora="130,40", ura="120,77"))

    tiles = only_hand(xml)["tiles"]

    assert (tiles["doraIndicators"], tiles["uraDoraIndicators"]) == ("2p6z", "2s4z")


def test_a_hand_without_riichi_has_no_ura_dora_indicators():
    xml = game(init(), agari(who=1, from_who=0, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1"))

    assert only_hand(xml)["tiles"]["uraDoraIndicators"] == ""
