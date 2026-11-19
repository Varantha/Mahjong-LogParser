"""The checks a hand must pass to be verified.

A hand that fails any check becomes a quarantined hand: it stays in the hand
store with one reason code per failed check and never reaches the trainer
bundle. Reason codes are stable strings, so reports can group by them.

Check 6, the cross-check, needs a hand whose tiles and moves could be read and
whose tiles pass checks 1-3: it runs on no other hand.
"""

from collections import Counter
from dataclasses import dataclass

from logparser.calls import KANS, Call
from logparser.recalculation import Recalculation, recalculate
from logparser.situation import FIRST_DRAW_YAKU, SITUATIONAL_YAKU, situational_yaku
from logparser.tiles import RED_FIVES
from logparser.yaku import YAKUMAN_KEYS

TILE_TOTAL = "tile-total"
TILE_LIMITS = "tile-limits"
WINNING_TILE = "winning-tile"
SITUATION = "situation"
PAYMENTS = "payments"
CROSS_CHECK = "cross-check"
CROSS_CHECK_REFUSED = "cross-check-refused"
UNKNOWN_YAKU = "unknown-yaku"
UNREADABLE_CALL = "unreadable-call"
# Check 6 runs only without these: the library can only recalculate a hand whose tiles and moves
# could be read and whose tiles pass checks 1-3.
UNSOUND_TILES = frozenset({UNREADABLE_CALL, TILE_TOTAL, TILE_LIMITS, WINNING_TILE})


@dataclass(frozen=True)
class Verification:
    reasons: list[str]  # one reason code per failed check; empty when the hand is verified
    recalculation: Recalculation | None  # the cross-check's recalculation, only when it matched the answer key


def verify(*, concealed: list[int], calls: list[Call] | None, unreadable_call_in_moves: bool,
           winning_tile: int, tile_from_moves: int | None, dora_indicators: list[int],
           ura_dora_indicators: list[int], situation: dict, answer_key: dict, unknown_yaku: list[int],
           recorded_score_changes: list[int], expected_score_changes: list[int] | None) -> Verification:
    """Tiles are Tenhou tile IDs.

    `calls` is None when a call code in the win could not be read, so the tile total can't be
    checked. The tile limits are still checked on the other tiles: leaving tiles out can hide a
    fifth copy but never make one up. `unreadable_call_in_moves` says a call code in the round's
    moves could not be read, so the situation can't be worked out.

    `winning_tile` is Tenhou's `machi`. `tile_from_moves` is the tile the game's moves handed the
    winner: drawn on a tsumo; discarded, or added to a kan, on a ron. It is None if the last move
    handed over none.

    `answer_key` is Tenhou's recorded result, with the yaku Tenhou gave under their contract keys.
    """
    yaku = [recorded["key"] for recorded in answer_key["yaku"]]
    reasons = []
    if calls is None or unreadable_call_in_moves:
        reasons.append(UNREADABLE_CALL)
    elif not _tile_total_adds_up(concealed, calls):
        reasons.append(TILE_TOTAL)
    if not _within_tile_limits([*concealed, *(tile for call in calls or [] for tile in call.tiles),
                                *dora_indicators, *ura_dora_indicators]):
        reasons.append(TILE_LIMITS)
    if winning_tile not in concealed or winning_tile != tile_from_moves:
        # Check 3: the winning tile is among the concealed tiles, and it is the tile the moves handed over.
        reasons.append(WINNING_TILE)
    if not unreadable_call_in_moves and not _situation_agrees(situation, yaku):
        reasons.append(SITUATION)
    if recorded_score_changes != expected_score_changes:
        # Check 5: Tenhou's recorded score changes are the answer key's payments, honba and riichi sticks.
        reasons.append(PAYMENTS)
    recalculation = None
    if not UNSOUND_TILES.intersection(reasons):
        recalculation = recalculate(concealed=concealed, calls=calls, winning_tile=winning_tile,
                                    dora_indicators=dora_indicators, ura_dora_indicators=ura_dora_indicators,
                                    situation=situation)
        if recalculation is None:
            reasons.append(CROSS_CHECK_REFUSED)
        elif not _recalculation_matches(recalculation, answer_key):
            reasons.append(CROSS_CHECK)
            recalculation = None
    if unknown_yaku:
        reasons.append(UNKNOWN_YAKU)
    return Verification(reasons, recalculation)


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


def _situation_agrees(situation: dict, yaku: list[str]) -> bool:
    """Check 4: the situation worked out from the moves gives the situational yaku Tenhou gave.

    On a yakuman win Tenhou lists only the yakuman, so only tenhou and chiihou can be compared.
    """
    won_with = situational_yaku(situation)
    if YAKUMAN_KEYS.intersection(yaku):
        won_with &= FIRST_DRAW_YAKU
    return won_with == SITUATIONAL_YAKU.intersection(yaku)


def _recalculation_matches(recalculation: Recalculation, answer_key: dict) -> bool:
    """Check 6: the library's yaku, each with its han, and its han, fu and points are the answer key's."""
    return (
        Counter((y["key"], y["han"]) for y in recalculation.yaku) == Counter((y["key"], y["han"]) for y in answer_key["yaku"])
        and (recalculation.han, recalculation.fu, recalculation.points) == (answer_key["han"], answer_key["fu"], answer_key["points"])
    )
