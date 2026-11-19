"""A winning hand as read from its log: what the checks and the recalculation read."""

from dataclasses import dataclass

from logparser.calls import Call


@dataclass(frozen=True)
class WinningHand:
    """A hand's tiles, as Tenhou tile IDs, and the situation it won in.

    `concealed` holds the winning tile, Tenhou's `machi`. `calls` are in the order they were made, or
    None when a call code in the win could not be read. `situation` is the hand record's situation,
    worked out from the game's moves.
    """

    concealed: list[int]
    calls: list[Call] | None
    winning_tile: int
    dora_indicators: list[int]
    ura_dora_indicators: list[int]
    situation: dict
