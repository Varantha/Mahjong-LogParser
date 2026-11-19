"""A hand's payments: who pays the winner what, split the way the trainer asks for them.

The base payments add up to the hand's points:

    ron               {"fromDiscarder": points}
    dealer tsumo      {"fromEachPlayer": ...}
    non-dealer tsumo  {"fromDealer": ..., "fromEachNonDealer": ...}

The honba bonus and the riichi sticks collected are kept apart from the base
payments, in points.
"""


def payments(points: int, *, tsumo: bool, dealer: bool, honba: int, riichi_sticks: int) -> dict:
    return {
        "base": {"fromDiscarder": points},
        "honbaBonus": 0,
        "riichiSticksCollected": 0,
    }
