"""Decoding Tenhou's call codes (the `m` attribute of N and AGARI) into calls.

Every code below is worked out by hand from Tenhou's bit layout, shown in the
comments. Bit 0 is the least significant; bits 0-1 always say where the called
tile came from, relative to the caller: 1 the next player (shimocha), 2 the
player across (toimen), 3 the previous player (kamicha), 0 nobody.
"""

import pytest

from logparser.calls import Call, decode_call, hand_is_open

CLOSED_KAN_OF_EAST = 108 << 8
CLOSED_KAN_OF_FIVE_MAN = 16 << 8


def test_a_chi_gives_its_three_tiles_the_called_tile_and_the_kamicha_it_came_from():
    # Chi of 4p 0p 6p, calling the 4p. Run start: suit 1 (pin) * 7 + rank 4 - 1 = 10;
    # 10 * 3 + called position 0 = 30, in bits 10+. Bit 2 marks a chi. Copies of
    # each tile in bits 3-4, 5-6, 7-8: 4p copy 1 (49), 5p copy 0 (52, red), 6p copy 2 (58).
    code = 30 << 10 | 1 << 3 | 0 << 5 | 2 << 7 | 0b100 | 3  # 30991

    assert decode_call(code) == Call(type="chi", tiles=(49, 52, 58), called_tile=49, called_from="kamicha")


def test_a_chi_in_sou_starts_its_run_after_the_nine_man_and_nine_pin_kinds():
    # Chi of 7s 8s 9s, calling the 9s. Run start: suit 2 (sou) * 7 + 7 - 1 = 20;
    # 20 * 3 + called position 2 = 62. Copies 0, 3, 1: 7s 96, 8s 103, 9s 105.
    code = 62 << 10 | 0 << 3 | 3 << 5 | 1 << 7 | 0b100 | 3  # 63751

    assert decode_call(code) == Call(type="chi", tiles=(96, 103, 105), called_tile=105, called_from="kamicha")


def test_a_pon_gives_its_three_tiles_the_called_tile_and_the_seat_it_came_from():
    # Pon of 5s (kind 22), calling the second of its tiles from toimen: 22 * 3 + 1 = 67,
    # in bits 9+. Bit 3 marks a pon. Bits 5-6 hold the copy left out of the pon: 2,
    # so the pon is 88 (red), 89 and 91.
    code = 67 << 9 | 2 << 5 | 0b1000 | 2  # 34378

    assert decode_call(code) == Call(type="pon", tiles=(88, 89, 91), called_tile=89, called_from="toimen")


def test_an_added_kan_keeps_its_pons_called_tile_and_seat_and_adds_the_fourth_tile():
    # A pon of 5m (kind 4) called from kamicha, its second tile called: 4 * 3 + 1 = 13,
    # in bits 9+. Bit 4 marks an added kan. Bits 5-6 hold the added copy: 0, the red 5m.
    code = 13 << 9 | 0 << 5 | 0b10000 | 3  # 6675

    assert decode_call(code) == Call(
        type="added-kan", tiles=(16, 17, 18, 19), called_tile=18, called_from="kamicha", added_tile=16,
    )


def test_an_open_kan_gives_all_four_copies_and_the_called_tile_is_the_one_in_bits_8_up():
    # Bits 2-5 clear mark a kan. Bits 8+ hold the called tile itself: the red 5p (52),
    # here called from shimocha.
    code = 52 << 8 | 1  # 13313

    assert decode_call(code) == Call(type="open-kan", tiles=(52, 53, 54, 55), called_tile=52, called_from="shimocha")


def test_a_closed_kan_of_fives_holds_all_four_copies_red_five_included_and_was_called_from_nobody():
    # Bits 0-1 clear: nobody discarded it. Bits 8+ hold the first copy of 5m, the red one.
    code = 16 << 8  # 4096

    assert decode_call(code) == Call(type="closed-kan", tiles=(16, 17, 18, 19), called_tile=None, called_from=None)


def test_a_pon_whose_left_out_copy_sets_bit_5_is_still_a_pon():
    # Pon of North (kind 30) from shimocha, first tile called, copy 3 left out (bits 5-6).
    code = 90 << 9 | 3 << 5 | 0b1000 | 1  # 46185

    assert decode_call(code) == Call(type="pon", tiles=(120, 121, 122), called_tile=120, called_from="shimocha")


@pytest.mark.parametrize(
    "code",
    [
        120 << 8 | 0b100000,                   # a North taken out in three-player games (nuki)
        136 << 8 | 2,                           # an open kan of tile 136, past the last tile
        34 * 3 << 9 | 0b1000 | 1,               # a pon of kind 34, past Chun
        21 * 3 << 10 | 0b100 | 3,               # a chi of honours
    ],
    ids=["nuki", "kan-past-last-tile", "pon-past-last-kind", "chi-of-honours"],
)
def test_a_code_that_is_no_four_player_call_is_refused(code):
    with pytest.raises(ValueError):
        decode_call(code)


def test_a_hand_without_calls_is_closed():
    assert hand_is_open([]) is False


def test_a_hand_whose_only_calls_are_closed_kans_counts_as_closed():
    calls = [decode_call(CLOSED_KAN_OF_FIVE_MAN), decode_call(CLOSED_KAN_OF_EAST)]

    assert hand_is_open(calls) is False


@pytest.mark.parametrize(
    "code",
    [
        2 * 3 << 10 | 0b100 | 3,      # chi of 3m 4m 5m from kamicha
        27 * 3 << 9 | 0b1000 | 2,     # pon of East from toimen
        52 << 8 | 1,                  # open kan of 5p from shimocha
        27 * 3 << 9 | 0b10000 | 2,    # added kan of East
    ],
    ids=["chi", "pon", "open-kan", "added-kan"],
)
def test_any_other_call_opens_the_hand_even_beside_a_closed_kan(code):
    assert hand_is_open([decode_call(CLOSED_KAN_OF_EAST), decode_call(code)]) is True
