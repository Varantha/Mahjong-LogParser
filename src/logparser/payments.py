"""A hand's payments: who pays the winner what, split the way the trainer asks for them.

The base payments add up to the hand's points:

    ron               {"fromDiscarder": points}
    dealer tsumo      {"fromEachPlayer": ...}
    non-dealer tsumo  {"fromDealer": ..., "fromEachNonDealer": ...}

The honba bonus and the riichi sticks collected are kept apart from the base
payments, in points.
"""


def payments(points: int, *, tsumo: bool, dealer: bool, honba: int, riichi_sticks: int) -> dict:
    if not tsumo:
        base = {"fromDiscarder": points}
    elif dealer:
        base = {"fromEachPlayer": points // 3}
    else:
        # Each non-dealer pays a quarter of the points rounded up to 100; the dealer pays the rest.
        each_non_dealer = -(-points // 400) * 100
        base = {"fromDealer": points - 2 * each_non_dealer, "fromEachNonDealer": each_non_dealer}
    return {
        "base": base,
        "honbaBonus": 0,
        "riichiSticksCollected": 0,
    }
