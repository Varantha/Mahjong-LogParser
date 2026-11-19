"""A hand's score recalculated by the `mahjong` library under Tenhou rules, in contract terms.

This is the separate recalculation the cross-check (check 6) compares with the answer key.
The library is set to Tenhou rules: open tanyao, red fives, kazoe yakuman at 13 han, no
kiriage, and the double forms of yakuman (suuankou tanki, junsei chuuren poutou, kokushi
musou with a 13-sided wait, daisuushii) worth a single yakuman.

The library's own vocabulary stays in this module. Its yaku come out under the contract's yaku
keys, by way of Tenhou's yaku IDs, its limits as limit tiers, and its fu reasons under the
contract's fu keys (FU_KEYS). Its fu reasons are turned into the fu a player counts:

    base 30 (closed ron)   base 20 and closed-ron 10
    base 25 (chiitoitsu)   chiitoitsu 25
    the 2 fu the library gives an open hand that has no other fu
                           tsumo 2 on a tsumo. On a ron it is left out: the raw fu of the
                           open pinfu shape is 20, which Tenhou scores as 30 fu.

It also works out the fu of every split of the hand that has a yaku. The library scores each such
split and keeps the one worth the most points, as Tenhou does, but it only reports that one; a
split without a yaku can't win, and the library never scores it.

`points` scores a given han and fu on their own, for re-scoring a hand as if its fu were different.
"""

from dataclasses import dataclass

from mahjong.constants import EAST, NORTH, SOUTH, WEST
from mahjong.hand_calculating.fu import FuCalculator
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, HandConstants, OptionalRules
from mahjong.hand_calculating.scores import ScoresCalculator
from mahjong.hand_calculating.yaku_config import YAKU_ID_TO_TENHOU_ID
from mahjong.meld import Meld

from logparser.calls import ADDED_KAN, CHI, CLOSED_KAN, OPEN_KAN, PON, Call
from logparser.situation import situational_yaku
from logparser.winning_hand import WinningHand
from logparser.yaku import TENHOU_YAKU_KEYS

TENHOU_RULES = OptionalRules(
    has_open_tanyao=True,
    has_aka_dora=True,
    has_double_yakuman=False,
    kazoe_limit=HandConstants.KAZOE_LIMITED,
    kiriage=False,
    fu_for_open_pinfu=True,
    fu_for_pinfu_tsumo=False,
    renhou_as_yakuman=False,
    has_daisharin=False,
    has_daisharin_other_suits=False,
    has_daichisei=False,
    has_sashikomi_yakuman=False,
    is_three_player=False,
)

WIND_TILES = {"east": EAST, "south": SOUTH, "west": WEST, "north": NORTH}

# The library's flag for each situational yaku (see logparser.situation).
SITUATIONAL_YAKU_FLAGS = {
    "double-riichi": "is_daburu_riichi",
    "ippatsu": "is_ippatsu",
    "haitei": "is_haitei",
    "houtei": "is_houtei",
    "rinshan": "is_rinshan",
    "chankan": "is_chankan",
    "tenhou": "is_tenhou",
    "chiihou": "is_chiihou",
}

MELD_TYPES = {CHI: Meld.CHI, PON: Meld.PON, OPEN_KAN: Meld.KAN, CLOSED_KAN: Meld.KAN, ADDED_KAN: Meld.SHOUMINKAN}

# The contract's fu keys, in the order a fu breakdown lists them. "Terminal" sets are of
# terminals or honours; "simple" sets are of 2-8.
FU_KEYS = (
    "base",
    "closed-ron",
    "chiitoitsu",
    "tsumo",
    "closed-terminal-kan",
    "open-terminal-kan",
    "closed-simple-kan",
    "open-simple-kan",
    "closed-terminal-triplet",
    "open-terminal-triplet",
    "closed-simple-triplet",
    "open-simple-triplet",
    "double-wind-pair",
    "yakuhai-pair",
    "tanki-wait",
    "kanchan-wait",
    "penchan-wait",
)

# The library's fu reasons that map straight onto a contract key.
_FU_REASON_KEYS = {
    FuCalculator.TSUMO: "tsumo",
    FuCalculator.CLOSED_TERMINAL_KAN: "closed-terminal-kan",
    FuCalculator.OPEN_TERMINAL_KAN: "open-terminal-kan",
    FuCalculator.CLOSED_KAN: "closed-simple-kan",
    FuCalculator.OPEN_KAN: "open-simple-kan",
    FuCalculator.CLOSED_TERMINAL_PON: "closed-terminal-triplet",
    FuCalculator.OPEN_TERMINAL_PON: "open-terminal-triplet",
    FuCalculator.CLOSED_PON: "closed-simple-triplet",
    FuCalculator.OPEN_PON: "open-simple-triplet",
    FuCalculator.DOUBLE_VALUED_PAIR: "double-wind-pair",
    FuCalculator.VALUED_PAIR: "yakuhai-pair",
    FuCalculator.PAIR_WAIT: "tanki-wait",
    FuCalculator.KANCHAN: "kanchan-wait",
    FuCalculator.PENCHAN: "penchan-wait",
}


# The library's names for its limits, by limit tier. Two or more yakuman at once are still the
# yakuman tier. The library names a kazoe yakuman a yakuman too.
_LIMIT_TIERS = {
    "": "none",
    "mangan": "mangan",
    "haneman": "haneman",
    "baiman": "baiman",
    "sanbaiman": "sanbaiman",
    "yakuman": "yakuman",
    **{f"{count}x yakuman": "yakuman" for count in range(2, 7)},
}


@dataclass(frozen=True)
class Recalculation:
    """The library's score for a hand, in the answer key's terms."""

    yaku: list[dict]  # [{key, han}], every yakuman 13 han
    han: int
    fu: int
    limit_tier: str | None  # None for a limit no limit tier names
    points: int  # before honba and riichi sticks
    raw_fu: int  # fu before rounding: the fu breakdown's sum
    fu_breakdown: list[dict]  # [{key, fu}] under the contract's fu keys, in FU_KEYS order
    split_fu: list[int]  # the fu of each split of the hand that has a yaku, ascending (see _SplitFu)


def recalculate(hand: WinningHand) -> Recalculation | None:
    """The library's score for a hand whose calls could all be read, or None when the library refuses to
    score it. Tenhou tile IDs are the library's own."""
    split_fu = _SplitFu()
    result = HandCalculator.estimate_hand_value(
        tiles=[*hand.concealed, *(tile for call in hand.calls for tile in call.tiles)],
        win_tile=hand.winning_tile,
        melds=[_meld(call) for call in hand.calls],
        dora_indicators=hand.dora_indicators,
        ura_dora_indicators=hand.ura_dora_indicators,
        config=_config(hand.situation),  # a new one per hand: the library changes it while scoring
        scores_calculator_factory=lambda: split_fu,
    )
    if result.error:
        return None
    fu_breakdown = _fu_breakdown(result.fu_details or [], tsumo=hand.situation["tsumo"])
    return Recalculation(
        yaku=[{"key": _yaku_key(y), "han": _han(y, open_hand=result.is_open_hand)} for y in result.yaku],
        han=result.han,
        fu=result.fu,
        limit_tier=_limit_tier(result.cost["yaku_level"], yakuman=any(y.is_yakuman for y in result.yaku)),
        points=_points(result.cost),
        raw_fu=sum(item["fu"] for item in fu_breakdown),
        fu_breakdown=fu_breakdown,
        split_fu=split_fu.of_splits(),
    )


def points(*, han: int, fu: int, dealer: bool, tsumo: bool) -> int:
    """The points of a hand of `han` and `fu` under Tenhou rules, before honba and riichi sticks.

    The hand is taken to have no yakuman: 13 han or more make a kazoe yakuman.
    """
    config = HandConfig(is_tsumo=tsumo, player_wind=EAST if dealer else SOUTH, options=TENHOU_RULES)
    return _points(ScoresCalculator.calculate_scores(han, fu, config))


class _SplitFu(ScoresCalculator):
    """The library's scorer, noting the fu of each reading of the hand it scores.

    A split arranges the tiles into four sets and a pair, the calls being sets as they were made,
    and says which concealed set or pair the winning tile completed. One arrangement can make
    several splits: in 234m 44m won on a 4m, the 4m completed either the 23m or the 4m.

    The library scores every split that has a yaku, once each, and no split without one. It also
    scores the hand read as seven pairs, always at 25 fu, and kokushi musou, at 0 fu. Neither is a
    split, and a split's fu are rounded up to a multiple of 10, so their fu tell them apart.
    """

    NOT_SPLITS_FU = frozenset({25, 0})  # seven pairs, kokushi musou

    def __init__(self) -> None:
        self._fu: list[int] = []

    def calculate_scores(self, han: int, fu: int, config: HandConfig, is_yakuman: bool = False):
        self._fu.append(fu)
        return super().calculate_scores(han, fu, config, is_yakuman)

    def of_splits(self) -> list[int]:
        """The fu of each split that has a yaku, ascending."""
        return sorted(fu for fu in self._fu if fu not in self.NOT_SPLITS_FU)


def _config(situation: dict) -> HandConfig:
    won_with = situational_yaku(situation)
    return HandConfig(
        is_tsumo=situation["tsumo"],
        is_riichi=situation["riichi"],
        **{flag: yaku in won_with for yaku, flag in SITUATIONAL_YAKU_FLAGS.items()},
        player_wind=WIND_TILES[situation["seatWind"]],
        round_wind=WIND_TILES[situation["roundWind"]],
        options=TENHOU_RULES,
    )


def _points(cost: dict) -> int:
    """The points in the library's cost of a hand, before honba and riichi sticks. On a ron the main
    payment is the discarder's and there is no additional one; on a tsumo the main payment is the
    dealer's (or a first non-dealer's, when the dealer won) and the additional one each other player's."""
    return cost["main"] + 2 * cost["additional"]


def _meld(call: Call) -> Meld:
    return Meld(MELD_TYPES[call.type], list(call.tiles), opened=call.type != CLOSED_KAN, called_tile=call.called_tile)


def _yaku_key(yaku) -> str | None:
    """The yaku's contract key, by way of its Tenhou ID; None for a yaku Tenhou's rules don't have."""
    return TENHOU_YAKU_KEYS.get(YAKU_ID_TO_TENHOU_ID.get(yaku.yaku_id))


def _limit_tier(yaku_level: str, *, yakuman: bool) -> str | None:
    """The limit tier of the library's limit; a yakuman's limit reached without a yakuman is a kazoe yakuman."""
    tier = _LIMIT_TIERS.get(yaku_level)
    if tier == "yakuman" and not yakuman:
        return "kazoe-yakuman"
    return tier


def _han(yaku, *, open_hand: bool) -> int:
    return yaku.han_open if open_hand and yaku.han_open else yaku.han_closed


def _fu_breakdown(fu_details: list[dict], *, tsumo: bool) -> list[dict]:
    breakdown = []
    for detail in fu_details:
        reason, fu = detail["reason"], detail["fu"]
        if reason == FuCalculator.BASE and fu == 30:
            breakdown += [{"key": "base", "fu": 20}, {"key": "closed-ron", "fu": 10}]
        elif reason == FuCalculator.BASE and fu == 25:
            breakdown.append({"key": "chiitoitsu", "fu": 25})
        elif reason == FuCalculator.BASE:
            breakdown.append({"key": "base", "fu": fu})
        elif reason == FuCalculator.HAND_WITHOUT_FU:
            if tsumo:
                breakdown.append({"key": "tsumo", "fu": fu})
        else:
            breakdown.append({"key": _FU_REASON_KEYS[reason], "fu": fu})
    return sorted(breakdown, key=lambda item: FU_KEYS.index(item["key"]))
