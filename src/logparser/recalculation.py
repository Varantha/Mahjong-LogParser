"""A hand's score recalculated by the `mahjong` library under Tenhou rules, in contract terms.

This is the separate recalculation the cross-check (check 6) compares with the answer key.
The library is set to Tenhou rules: open tanyao, red fives, kazoe yakuman at 13 han, no
kiriage, and the double forms of yakuman (suuankou tanki, junsei chuuren poutou, kokushi
musou with a 13-sided wait, daisuushii) worth a single yakuman.

The library's own vocabulary stays in this module. Its yaku come out under the contract's yaku
keys, by way of Tenhou's yaku IDs, and its fu reasons under the contract's fu keys (FU_KEYS).
Its fu reasons are turned into the fu a player counts:

    base 30 (closed ron)   base 20 and closed-ron 10
    base 25 (chiitoitsu)   chiitoitsu 25
    the 2 fu the library gives an open hand that has no other fu
                           tsumo 2 on a tsumo. On a ron it is left out: the raw fu of the
                           open pinfu shape is 20, which Tenhou scores as 30 fu.
"""

from dataclasses import dataclass

from mahjong.constants import EAST, NORTH, SOUTH, WEST
from mahjong.hand_calculating.fu import FuCalculator
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, HandConstants, OptionalRules
from mahjong.hand_calculating.yaku_config import YAKU_ID_TO_TENHOU_ID
from mahjong.meld import Meld

from logparser.calls import ADDED_KAN, CHI, CLOSED_KAN, OPEN_KAN, PON, Call
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


@dataclass(frozen=True)
class Recalculation:
    """The library's score for a hand, in the answer key's terms."""

    yaku: list[dict]  # [{key, han}], every yakuman 13 han
    han: int
    fu: int
    points: int  # before honba and riichi sticks
    raw_fu: int  # fu before rounding: the fu breakdown's sum
    fu_breakdown: list[dict]  # [{key, fu}] under the contract's fu keys, in FU_KEYS order


def recalculate(*, concealed: list[int], calls: list[Call], winning_tile: int, dora_indicators: list[int],
                ura_dora_indicators: list[int], situation: dict) -> Recalculation | None:
    """The library's score for a hand, or None when the library refuses to score it.

    Tiles are Tenhou tile IDs, which are the library's own. `concealed` holds the winning tile.
    `situation` is the hand record's situation, worked out from the game's moves.
    """
    config = _config(situation)  # a new one per hand: the library changes it while scoring
    result = HandCalculator.estimate_hand_value(
        tiles=[*concealed, *(tile for call in calls for tile in call.tiles)],
        win_tile=winning_tile,
        melds=[_meld(call) for call in calls],
        dora_indicators=dora_indicators,
        ura_dora_indicators=ura_dora_indicators,
        config=config,
    )
    if result.error:
        return None
    fu_breakdown = _fu_breakdown(result.fu_details or [], tsumo=situation["tsumo"])
    return Recalculation(
        yaku=[{"key": _yaku_key(y), "han": _han(y, open_hand=result.is_open_hand)} for y in result.yaku],
        han=result.han,
        fu=result.fu,
        points=result.cost["main"] + 2 * result.cost["additional"],
        raw_fu=sum(item["fu"] for item in fu_breakdown),
        fu_breakdown=fu_breakdown,
    )


def _config(situation: dict) -> HandConfig:
    return HandConfig(
        is_tsumo=situation["tsumo"],
        is_riichi=situation["riichi"],
        is_daburu_riichi=situation["doubleRiichi"],
        is_ippatsu=situation["ippatsu"],
        is_rinshan=situation["rinshan"],
        is_chankan=situation["chankan"],
        is_haitei=situation["lastTile"] and situation["tsumo"],
        is_houtei=situation["lastTile"] and not situation["tsumo"],
        is_tenhou=situation["firstDraw"] and situation["dealer"],
        is_chiihou=situation["firstDraw"] and not situation["dealer"],
        player_wind=WIND_TILES[situation["seatWind"]],
        round_wind=WIND_TILES[situation["roundWind"]],
        options=TENHOU_RULES,
    )


def _meld(call: Call) -> Meld:
    return Meld(MELD_TYPES[call.type], list(call.tiles), opened=call.type != CLOSED_KAN, called_tile=call.called_tile)


def _yaku_key(yaku) -> str | None:
    """The yaku's contract key, by way of its Tenhou ID; None for a yaku Tenhou's rules don't have."""
    return TENHOU_YAKU_KEYS.get(YAKU_ID_TO_TENHOU_ID.get(yaku.yaku_id))


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
