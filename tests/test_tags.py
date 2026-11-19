"""Tags: named facts derived from a hand, worked out as each hand is read from its log."""

import pytest

from logparser.tags import TAGS
from logparser.tenhou import parse_log
from logparser.yaku import TENHOU_YAKU_KEYS
from tenhou_xml import KAMICHA, TOIMEN, agari, called_win, chi, closed_kan, game, ids, init, m, pon

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def only_hand(xml: str) -> dict:
    hands = parse_log(LOG_ID, xml).hands
    assert len(hands) == 1
    return hands[0]


def ron(*, hai: str, machi: int, ten: str, yaku: str, calls: str | None = None, dora: str = "130",
        ura: str | None = None) -> str:
    """A ron by seat 1 (South, not dealing) off seat 0 in East 1, with the Hatsu as dora indicator by default."""
    return game(init(), agari(who=1, from_who=0, hai=hai, m=calls, machi=machi, ten=ten, yaku=yaku, dora=dora,
                              ura=ura))


# Open hands, each with one yaku worth 1 han less because the hand is open. Every hand opens with a
# chi from kamicha; the rest of its tiles are concealed and it wins by ron.
OPEN_HANDS_LOSING_A_HAN = {
    # chi 123m; 123p 456p 12s+3s 99s: 1 han 30 fu.
    "sanshoku-doujun": ron(calls=m(chi((0, 4, 8), called=0)), hai=ids(36, 40, 44, 48, 53, 56, 72, 76, 80, 104, 105),
                           machi=80, ten="30,1000,0", yaku="25,1"),
    # chi 123m; 456m 789m 23p+4p 99s: 1 han 30 fu.
    "ittsu": ron(calls=m(chi((0, 4, 8), called=0)), hai=ids(12, 17, 20, 24, 28, 32, 40, 44, 48, 104, 105),
                 machi=48, ten="30,1000,0", yaku="24,1"),
    # chi 789m; 123p 123s 78s+9s 44z: 1 han 30 fu.
    "chanta": ron(calls=m(chi((24, 28, 32), called=32)), hai=ids(36, 40, 44, 72, 76, 80, 96, 100, 104, 120, 121),
                  machi=104, ten="30,1000,0", yaku="23,1"),
    # chi 789m; 123p 123s 78s+9s 99p: 2 han 30 fu.
    "junchan": ron(calls=m(chi((24, 28, 32), called=32)), hai=ids(36, 40, 44, 68, 69, 72, 76, 80, 96, 100, 104),
                   machi=104, ten="30,2000,0", yaku="33,2"),
    # chi 123m; 567m 78m+9m 444z 33z: 2 han 30 fu.
    "honitsu": ron(calls=m(chi((0, 4, 8), called=0)), hai=ids(17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
                   machi=32, ten="30,2000,0", yaku="34,2"),
    # chi 123m; 345m 67m+8m 999m 22m: 5 han, mangan.
    "chinitsu": ron(calls=m(chi((0, 4, 8), called=0)), hai=ids(5, 6, 9, 12, 17, 20, 24, 28, 32, 33, 34),
                    machi=28, ten="30,8000,1", yaku="35,5"),
}


@pytest.mark.parametrize("xml", OPEN_HANDS_LOSING_A_HAN.values(), ids=OPEN_HANDS_LOSING_A_HAN.keys())
def test_an_open_hand_with_a_yaku_worth_a_han_less_when_open_has_kuisagari(xml):
    assert "kuisagari" in only_hand(xml)["tags"]


HANDS_WITHOUT_KUISAGARI = {
    # 123m 567m 78m+9m 444z 33z, all concealed: honitsu at its full 3 han, 40 fu.
    "closed": ron(hai=ids(0, 4, 8, 17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
                  machi=32, ten="40,5200,0", yaku="34,3"),
    # The same honitsu with the North as a closed kan, which leaves the hand closed: 3 han 70 fu, mangan.
    "closed-kan": ron(calls=m(closed_kan(120)), hai=ids(0, 4, 8, 17, 20, 24, 25, 28, 32, 116, 117),
                      machi=32, ten="70,8000,1", yaku="34,3"),
    # Chi 340m and a pon of Chun: chun and aka dora, neither worth less when open.
    "open-without-such-yaku": game(init(), called_win()),
    # Pons of 2m and 2p; 222s 45p+6p 99s: sanshoku doukou is 2 han open or closed.
    "open-sanshoku-doukou": ron(calls=m(pon((4, 5, 6), called=5, from_seat=TOIMEN),
                                        pon((40, 41, 42), called=41, from_seat=KAMICHA)),
                                hai=ids(48, 53, 56, 76, 77, 78, 104, 105), machi=56, ten="30,2000,0", yaku="26,2"),
}


@pytest.mark.parametrize("xml", HANDS_WITHOUT_KUISAGARI.values(), ids=HANDS_WITHOUT_KUISAGARI.keys())
def test_a_hand_that_is_closed_or_loses_no_han_by_being_open_has_no_kuisagari(xml):
    assert "kuisagari" not in only_hand(xml)["tags"]


# Chiitoitsu, ron on the Haku: 11m 99m 11p 22p 11s 11z 5z+5z. Under each indicator below that
# names a pair as dora it is 4 han 25 fu.
SEVEN_PAIRS = ids(0, 1, 32, 33, 36, 37, 40, 41, 72, 73, 108, 109, 124, 125)


def seven_pairs(dora: str, ura: str | None = None, yaku: str = "22,2,52,2", ten: str = "25,6400,0") -> str:
    return ron(hai=SEVEN_PAIRS, machi=125, ten=ten, yaku=yaku, dora=dora, ura=ura)


HANDS_WITH_WRAPAROUND_DORA = {
    "9m-makes-1m-dora": seven_pairs(dora=ids(34)),
    "9p-makes-1p-dora": seven_pairs(dora=ids(70)),
    "9s-makes-1s-dora": seven_pairs(dora=ids(106)),
    "north-makes-east-dora": seven_pairs(dora=ids(120)),
    "chun-makes-haku-dora": seven_pairs(dora=ids(132)),
    # The Hatsu is the first indicator; the 9m is turned over after a kan.
    "kan-dora-indicator": seven_pairs(dora=ids(128, 34)),
    # A pon of East with the North as indicator; 123m 456p 99p 23s+4s: round wind and dora 3, 4 han 30 fu.
    "dora-in-a-call": ron(calls=m(pon((108, 109, 110), called=109, from_seat=TOIMEN)),
                          hai=ids(0, 4, 8, 48, 53, 56, 68, 69, 76, 80, 84), machi=84, ten="30,7700,0",
                          yaku="14,1,52,3", dora=ids(120)),
}


@pytest.mark.parametrize("xml", HANDS_WITH_WRAPAROUND_DORA.values(), ids=HANDS_WITH_WRAPAROUND_DORA.keys())
def test_a_hand_holding_the_dora_of_an_indicator_that_wraps_round_has_wraparound_dora(xml):
    assert "wraparound-dora" in only_hand(xml)["tags"]


HANDS_WITHOUT_WRAPAROUND_DORA = {
    # The 8m names the 9m pair as dora without wrapping round.
    "indicator-does-not-wrap": seven_pairs(dora=ids(28)),
    # The 9p wraps round to the 1p, which the hand does not hold: 123m 456p 99p 23s+4s 789s, pinfu only.
    "dora-not-held": ron(hai=ids(0, 4, 8, 48, 53, 56, 68, 69, 76, 80, 84, 96, 100, 104), machi=84,
                         ten="30,1000,0", yaku="7,1", dora=ids(70)),
    # Only the ura dora indicator wraps round: riichi, chiitoitsu and ura dora 2 make a mangan.
    "only-ura-dora-wraps": seven_pairs(dora=ids(128), ura=ids(34), yaku="1,1,22,2,53,2", ten="25,8000,1"),
}


@pytest.mark.parametrize("xml", HANDS_WITHOUT_WRAPAROUND_DORA.values(), ids=HANDS_WITHOUT_WRAPAROUND_DORA.keys())
def test_a_hand_without_the_dora_of_a_dora_indicator_that_wraps_round_has_no_wraparound_dora(xml):
    assert "wraparound-dora" not in only_hand(xml)["tags"]


def test_a_hand_lists_its_tags_once_each_in_a_fixed_order():
    # Chi 123m with the 9m as indicator; 567m 78m+9m 444z 33z: honitsu 2 and dora 1, 3 han 30 fu.
    xml = ron(calls=m(chi((0, 4, 8), called=0)), hai=ids(17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
              machi=32, ten="30,3900,0", yaku="34,2,52,1", dora=ids(35))

    assert only_hand(xml)["tags"] == ["kuisagari", "wraparound-dora"]


def test_no_plain_value_is_a_tag():
    # The spec's plain values, which drills filter on directly: han, fu, raw fu, limit tier, dealer,
    # tsumo/ron, open/closed, yaku, dora count, honba, riichi sticks and call types.
    plain_values = {
        "han", "fu", "raw-fu", "limit-tier", "mangan", "haneman", "baiman", "sanbaiman", "kazoe-yakuman", "yakuman",
        "dealer", "tsumo", "ron", "open", "closed", "dora-count", "honba", "riichi-sticks",
        "chi", "pon", "open-kan", "closed-kan", "added-kan", *TENHOU_YAKU_KEYS.values(),
    }

    assert set(TAGS).isdisjoint(plain_values)
