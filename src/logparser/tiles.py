"""Tenhou tile IDs to `mpsz` notation.

Tenhou numbers the 136 tiles 0-135, four copies per kind: 0-35 are man,
36-71 pin, 72-107 sou and 108-135 the honours (East, South, West, North,
Haku, Hatsu, Chun = 1z-7z). The first copy of each five (16, 52, 88) is the
red five, written `0`.
"""

import re

SUITS = "mpsz"
RED_FIVES = frozenset({16, 52, 88})


def tile(tile_id: int) -> str:
    """One tile in mpsz, e.g. `5m`, `0p`, `7z`."""
    return f"{rank(tile_id)}{SUITS[tile_id // 36]}"


def rank(tile_id: int) -> int:
    """The rank written in mpsz: 1-9, 1-7 for honours, 0 for a red five."""
    if tile_id in RED_FIVES:
        return 0
    return tile_id // 4 % 9 + 1


def kinds(tiles: str) -> list[str]:
    """Each tile in an mpsz string as its kind, e.g. `340m` gives `3m`, `4m`, `5m` (a red five is a five)."""
    return [f"{int(r) or 5}{suit}" for ranks, suit in re.findall(r"([0-9]+)([mpsz])", tiles) for r in ranks]


def mpsz(tile_ids) -> str:
    """Tiles in compact mpsz, sorted, e.g. `340m11z` (a red five sorts as a five)."""
    groups: dict[str, str] = {}  # sorted IDs fill this in m, p, s, z order
    for tile_id in sorted(tile_ids):
        suit = SUITS[tile_id // 36]
        groups[suit] = groups.get(suit, "") + str(rank(tile_id))
    return "".join(ranks + suit for suit, ranks in groups.items())
