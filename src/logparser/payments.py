"""A hand's payments: who pays the winner what, split the way the trainer asks for them.

The base payments add up to the hand's points:

    ron               {"fromDiscarder": points}
    dealer tsumo      {"fromEachPlayer": ...}
    non-dealer tsumo  {"fromDealer": ..., "fromEachNonDealer": ...}

The honba bonus and the riichi sticks collected are kept apart from the base
payments, in points.
"""

HONBA_POINTS = 300  # per honba: all from the discarder on a ron, 100 from each player on a tsumo
RIICHI_STICK_POINTS = 1000


def payments(points: int, *, tsumo: bool, dealer: bool, honba: int, riichi_sticks: int) -> dict:
    """The winner's payments. `base` is None when no hand's points split that way."""
    return {
        "base": _base(points, tsumo=tsumo, dealer=dealer),
        "honbaBonus": HONBA_POINTS * honba,
        "riichiSticksCollected": RIICHI_STICK_POINTS * riichi_sticks,
    }


def _base(points: int, *, tsumo: bool, dealer: bool) -> dict | None:
    if not tsumo:
        return {"fromDiscarder": points}
    if dealer:
        return {"fromEachPlayer": points // 3} if points % 300 == 0 else None
    # Each non-dealer pays a quarter of the points rounded up to 100; the dealer pays the rest.
    # Both shares are rounded up from the hand's base points, so the dealer's is twice a
    # non-dealer's or 100 less.
    each_non_dealer = -(-points // 400) * 100
    from_dealer = points - 2 * each_non_dealer
    if from_dealer not in (2 * each_non_dealer, 2 * each_non_dealer - 100):
        return None
    return {"fromDealer": from_dealer, "fromEachNonDealer": each_non_dealer}


def score_changes(payments: dict, *, winner: int, discarder: int, dealer: int) -> list[int] | None:
    """How much each seat's score changes, in points, when the winner is paid `payments`.

    None when the payments have no base split.
    """
    base = payments["base"]
    if base is None:
        return None
    others = [seat for seat in range(4) if seat != winner]
    if "fromDiscarder" in base:
        owed = {discarder: base["fromDiscarder"]}
    elif "fromEachPlayer" in base:
        owed = {seat: base["fromEachPlayer"] for seat in others}
    else:
        owed = {seat: base["fromDealer"] if seat == dealer else base["fromEachNonDealer"] for seat in others}
    honba_each = payments["honbaBonus"] // len(owed)
    changes = [0] * 4
    for seat, amount in owed.items():
        changes[seat] = -(amount + honba_each)
    changes[winner] = -sum(changes) + payments["riichiSticksCollected"]
    return changes
