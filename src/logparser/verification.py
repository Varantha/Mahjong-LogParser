"""The checks a hand must pass to be verified.

A hand that fails any check becomes a quarantined hand: it stays in the hand
store with one reason code per failed check and never reaches the trainer
bundle. Reason codes are stable strings, so reports can group by them.
"""

from logparser.calls import KANS, Call

TILE_TOTAL = "tile-total"
UNKNOWN_YAKU = "unknown-yaku"


def quarantine_reasons(*, concealed: list[int], calls: list[Call], unknown_yaku: list[int]) -> list[str]:
    reasons = []
    if not _tile_total_adds_up(concealed, calls):
        reasons.append(TILE_TOTAL)
    if unknown_yaku:
        reasons.append(UNKNOWN_YAKU)
    return reasons


def _tile_total_adds_up(concealed: list[int], calls: list[Call]) -> bool:
    """Check 1: concealed tiles (winning tile included) plus called tiles come to 14, plus one per kan."""
    kans = sum(1 for call in calls if call.type in KANS)
    return len(concealed) + sum(len(call.tiles) for call in calls) == 14 + kans
