"""The checks a hand must pass to be verified.

A hand that fails any check becomes a quarantined hand: it stays in the hand
store with one reason code per failed check and never reaches the trainer
bundle. Reason codes are stable strings, so reports can group by them.
"""

TILE_TOTAL = "tile-total"
PAYMENTS = "payments"
UNKNOWN_YAKU = "unknown-yaku"
# Placeholder until calls are decoded: a hand with calls can't be checked yet.
CALLS_NOT_SUPPORTED = "calls-not-supported"


def quarantine_reasons(*, concealed: list[int], call_codes: list[int], unknown_yaku: list[int],
                       recorded_score_changes: list[int], expected_score_changes: list[int]) -> list[str]:
    reasons = []
    if call_codes:
        reasons.append(CALLS_NOT_SUPPORTED)
    elif len(concealed) != 14:
        # Check 1: a closed hand is its 14 concealed tiles, winning tile included.
        reasons.append(TILE_TOTAL)
    if recorded_score_changes != expected_score_changes:
        # Check 5: Tenhou's recorded score changes are the answer key's payments, honba and riichi sticks.
        reasons.append(PAYMENTS)
    if unknown_yaku:
        reasons.append(UNKNOWN_YAKU)
    return reasons
