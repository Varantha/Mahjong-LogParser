"""The checks a hand must pass to be verified.

A hand that fails any check becomes a quarantined hand: it stays in the hand
store with one reason code per failed check and never reaches the trainer
bundle. Reason codes are stable strings, so reports can group by them.
"""

from collections import Counter

from logparser.calls import KANS, Call
from logparser.tiles import RED_FIVES

TILE_TOTAL = "tile-total"
TILE_LIMITS = "tile-limits"
WINNING_TILE = "winning-tile"
PAYMENTS = "payments"
UNKNOWN_YAKU = "unknown-yaku"
UNREADABLE_CALL = "unreadable-call"


def quarantine_reasons(*, concealed: list[int], calls: list[Call] | None, winning_tile: int,
                       tile_from_moves: int | None, dora_indicators: list[int], ura_dora_indicators: list[int],
                       unknown_yaku: list[int], recorded_score_changes: list[int],
                       expected_score_changes: list[int] | None) -> list[str]:
    """Tiles are Tenhou tile IDs.

    `calls` is None when a call code in the win could not be read, so the tile total can't be
    checked. The tile limits are still checked on the other tiles: leaving tiles out can hide a
    fifth copy but never make one up.

    `winning_tile` is Tenhou's `machi`. `tile_from_moves` is the tile the game's moves handed the
    winner (drawn on a tsumo, discarded on a ron), or None if the last move handed over none.
    """
    reasons = []
    if calls is None:
        reasons.append(UNREADABLE_CALL)
    elif not _tile_total_adds_up(concealed, calls):
        reasons.append(TILE_TOTAL)
    if not _within_tile_limits([*concealed, *(tile for call in calls or [] for tile in call.tiles),
                                *dora_indicators, *ura_dora_indicators]):
        reasons.append(TILE_LIMITS)
    if winning_tile not in concealed or winning_tile != tile_from_moves:
        # Check 3: the winning tile is among the concealed tiles, and it is the tile the moves handed over.
        reasons.append(WINNING_TILE)
    if recorded_score_changes != expected_score_changes:
        # Check 5: Tenhou's recorded score changes are the answer key's payments, honba and riichi sticks.
        reasons.append(PAYMENTS)
    if unknown_yaku:
        reasons.append(UNKNOWN_YAKU)
    return reasons


def _tile_total_adds_up(concealed: list[int], calls: list[Call]) -> bool:
    """Check 1: concealed tiles (winning tile included) plus called tiles come to 14, plus one per kan."""
    kans = sum(1 for call in calls if call.type in KANS)
    return len(concealed) + sum(len(call.tiles) for call in calls) == 14 + kans


def _within_tile_limits(tiles: list[int]) -> bool:
    """Check 2: among the hand's tiles and indicators, no tile appears more than 4 times and
    there is at most one red five per suit."""
    copies = Counter(tile // 4 for tile in tiles)
    red_fives = Counter(tile // 36 for tile in tiles if tile in RED_FIVES)
    return max(copies.values(), default=0) <= 4 and max(red_fives.values(), default=0) <= 1
