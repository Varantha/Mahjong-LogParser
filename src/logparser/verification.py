"""The checks a hand must pass to be verified.

A hand that fails any check becomes a quarantined hand: it stays in the hand
store with one reason code per failed check and never reaches the trainer
bundle. Reason codes are stable strings, so reports can group by them.
"""

from logparser.calls import KANS, Call
from logparser.situation import FIRST_DRAW_YAKU, SITUATIONAL_YAKU, situational_yaku
from logparser.yaku import YAKUMAN_KEYS

TILE_TOTAL = "tile-total"
SITUATION = "situation"
PAYMENTS = "payments"
UNKNOWN_YAKU = "unknown-yaku"
UNREADABLE_CALL = "unreadable-call"


def quarantine_reasons(*, concealed: list[int], calls: list[Call] | None, situation: dict, yaku: list[str],
                       unknown_yaku: list[int], recorded_score_changes: list[int],
                       expected_score_changes: list[int] | None) -> list[str]:
    """`calls` is None when a call code in the win could not be read, so the tiles can't be checked.
    `yaku` holds the contract keys of the yaku Tenhou gave."""
    reasons = []
    if calls is None:
        reasons.append(UNREADABLE_CALL)
    elif not _tile_total_adds_up(concealed, calls):
        reasons.append(TILE_TOTAL)
    if not _situation_agrees(situation, yaku):
        reasons.append(SITUATION)
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


def _situation_agrees(situation: dict, yaku: list[str]) -> bool:
    """Check 4: the situation worked out from the moves gives the situational yaku Tenhou gave.

    On a yakuman win Tenhou lists only the yakuman, so only tenhou and chiihou can be compared.
    """
    won_with = situational_yaku(situation)
    if YAKUMAN_KEYS.intersection(yaku):
        won_with &= FIRST_DRAW_YAKU
    return won_with == SITUATIONAL_YAKU.intersection(yaku)
