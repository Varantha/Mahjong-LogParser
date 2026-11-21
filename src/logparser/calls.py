"""Tenhou's call codes decoded into calls.

A call code is the integer in the `m` attribute of N and AGARI tags. Its
layout is Tenhou's own (the viewer's `tehai.js`). Bit 0 is the least
significant:

    bits 0-1   whose discard the called tile was, relative to the caller:
               1 shimocha (next), 2 toimen (across), 3 kamicha (previous), 0 nobody
    bit 2      chi. Bits 10+ hold run * 3 + the called tile's position in the run,
               where run is suit * 7 + lowest rank - 1. Bits 3-4, 5-6 and 7-8 hold
               which copy of each tile in the run it is.
    bit 3      pon. Bits 9+ hold kind * 3 + the called tile's position in the pon.
               Bits 5-6 hold the copy of the kind that is not in the pon.
    bit 4      added kan: a pon laid out as above, plus the copy in bits 5-6.
    bit 5      a North taken out in three-player games (nuki). Not a call in
               four-player games, so it is refused.
    none       a kan. Bits 8+ hold a tile of its kind: the called tile of an open
               kan, or any copy for a closed kan (bits 0-1 clear).

Tiles are Tenhou tile IDs (see `logparser.tiles`). A kan holds all four copies
of its kind, so a kan of fives always holds the red five.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from logparser.tiles import SUITS, rank

CHI = "chi"
PON = "pon"
OPEN_KAN = "open-kan"
CLOSED_KAN = "closed-kan"
ADDED_KAN = "added-kan"
KANS = frozenset({OPEN_KAN, CLOSED_KAN, ADDED_KAN})

CALLED_FROM = {1: "shimocha", 2: "toimen", 3: "kamicha"}
SUITED_RUNS = 3 * 7  # runs start at rank 1-7 of man, pin or sou
KINDS = 34
TILES = KINDS * 4


@dataclass(frozen=True)
class Call:
    type: str
    tiles: tuple[int, ...]  # Tenhou tile IDs, ascending, including the called and added tiles
    called_tile: int | None = None  # None for a closed kan
    called_from: str | None = None  # whose discard it was, relative to the caller; None for a closed kan
    added_tile: int | None = None  # the tile an added kan adds to its pon


def decode_call(code: int) -> Call:
    """The call in a Tenhou call code. Raises ValueError for a code that is no four-player call."""
    called_from = CALLED_FROM.get(code & 3)
    if code & 0x4:
        run, position = divmod(code >> 10, 3)
        _check(run < SUITED_RUNS, code)
        first = (run // 7 * 9 + run % 7) * 4
        tiles = tuple(first + 4 * k + (code >> (3 + 2 * k) & 3) for k in range(3))
        return Call(type=CHI, tiles=tiles, called_tile=tiles[position], called_from=called_from)
    if code & 0x18:
        kind, position = divmod(code >> 9, 3)
        _check(kind < KINDS, code)
        left_out = kind * 4 + (code >> 5 & 3)  # the copy not in the pon; an added kan adds it
        pon = tuple(kind * 4 + copy for copy in range(4) if kind * 4 + copy != left_out)
        if code & 0x8:
            return Call(type=PON, tiles=pon, called_tile=pon[position], called_from=called_from)
        return Call(type=ADDED_KAN, tiles=tuple(sorted((*pon, left_out))), called_tile=pon[position],
                    called_from=called_from, added_tile=left_out)
    _check(not code & 0x20 and code >> 8 < TILES, code)
    tile = code >> 8
    tiles = tuple(tile // 4 * 4 + copy for copy in range(4))
    if called_from is None:
        return Call(type=CLOSED_KAN, tiles=tiles)
    return Call(type=OPEN_KAN, tiles=tiles, called_tile=tile, called_from=called_from)


def call_string(call: Call) -> str:
    """A call as its call string: its tiles as they lie on the table, left to right, then the suit.

    `c` goes before a turned tile: the called tile, and for an added kan the added tile, which follows it.
    The turned tile lies first when called from kamicha, second from toimen and last from shimocha; the
    call's other tiles keep their order around it. `f` goes before a face-down tile: the two outer tiles
    of a closed kan, whose red five lies second so that it shows.

        c423p    chi of 234p, calling the 4p        55c5p    pon of 5p from shimocha
        1c111z   open kan of East from toimen       c5c055p  added kan: the 5p called, the red 5p added
        f505f5m  closed kan of 5m
    """
    suit = SUITS[call.tiles[0] // 36]
    if call.type == CLOSED_KAN:
        first, second, third, fourth = (rank(tile) for tile in call.tiles)
        return f"f{second}{first}{third}f{fourth}{suit}"  # a red five is the first copy
    turned = f"c{rank(call.called_tile)}" + ("" if call.added_tile is None else f"c{rank(call.added_tile)}")
    others = [str(rank(tile)) for tile in call.tiles if tile not in (call.called_tile, call.added_tile)]
    position = {"kamicha": 0, "toimen": 1, "shimocha": len(others)}[call.called_from]
    return "".join(others[:position] + [turned] + others[position:]) + suit


def _check(readable: bool, code: int) -> None:
    if not readable:
        raise ValueError(f"call code {code} is no four-player call")


def hand_is_open(call_types: Iterable[str]) -> bool:
    """A hand is open once it has a call other than a closed kan. `call_types` are the type of each of its calls."""
    return any(call_type != CLOSED_KAN for call_type in call_types)
