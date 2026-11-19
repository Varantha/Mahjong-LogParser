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

It also works out the fu of every split of the hand. The library scores each split and keeps the
one worth the most points, as Tenhou does, but it only reports that one.

`points` scores a given han and fu on their own, for re-scoring a hand as if its fu were different.
"""

from dataclasses import dataclass

from mahjong.constants import CHUN, EAST, HAKU, HATSU, NORTH, SOUTH, WEST
from mahjong.hand_calculating.divider import HandDivider
from mahjong.hand_calculating.fu import FuCalculator
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, HandConstants, OptionalRules
from mahjong.hand_calculating.scores import ScoresCalculator
from mahjong.hand_calculating.yaku_config import YAKU_ID_TO_TENHOU_ID
from mahjong.meld import Meld
from mahjong.tile import TilesConverter

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
    split_fu: list[int]  # the fu of each split of the hand, ascending (see _split_fu)


def recalculate(*, concealed: list[int], calls: list[Call], winning_tile: int, dora_indicators: list[int],
                ura_dora_indicators: list[int], situation: dict) -> Recalculation | None:
    """The library's score for a hand, or None when the library refuses to score it.

    Tiles are Tenhou tile IDs, which are the library's own. `concealed` holds the winning tile.
    `situation` is the hand record's situation, worked out from the game's moves.
    """
    config = _config(situation)  # a new one per hand: the library changes it while scoring
    tiles = [*concealed, *(tile for call in calls for tile in call.tiles)]
    melds = [_meld(call) for call in calls]
    result = HandCalculator.estimate_hand_value(
        tiles=tiles,
        win_tile=winning_tile,
        melds=melds,
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
        limit_tier=_limit_tier(result.cost["yaku_level"], yakuman=any(y.is_yakuman for y in result.yaku)),
        points=result.cost["main"] + 2 * result.cost["additional"],
        raw_fu=sum(item["fu"] for item in fu_breakdown),
        fu_breakdown=fu_breakdown,
        split_fu=_split_fu(tiles, winning_tile, melds, config),
    )


def points(*, han: int, fu: int, dealer: bool, tsumo: bool) -> int:
    """The points of a hand of `han` and `fu` under Tenhou rules, before honba and riichi sticks.

    The hand is taken to have no yakuman: 13 han or more make a kazoe yakuman.
    """
    config = HandConfig(is_tsumo=tsumo, player_wind=EAST if dealer else SOUTH, options=TENHOU_RULES)
    cost = ScoresCalculator.calculate_scores(han, fu, config)
    return cost["main"] + 2 * cost["additional"]


def _split_fu(tiles: list[int], winning_tile: int, melds: list[Meld], config: HandConfig) -> list[int]:
    """The fu of each split of the hand, ascending.

    A split arranges the tiles into four sets and a pair, the calls being sets as they were made,
    and says which concealed set or pair the winning tile completed. One arrangement can make
    several splits: in 234m 44m won on a 4m, the 4m completed either the 23m or the 4m. Seven pairs
    is no split into sets and a pair, so a chiitoitsu hand that can't be read as sets has none.
    """
    valued_tiles = [HAKU, HATSU, CHUN, config.player_wind, config.round_wind]
    fu = []
    for sets_and_pair in HandDivider.divide_hand(TilesConverter.to_34_array(tiles), melds):
        if len(sets_and_pair) != 5:
            continue  # seven pairs
        concealed = list(sets_and_pair)
        for meld in melds:
            concealed.remove(sorted(tile // 4 for tile in meld.tiles))
        completed_by_the_winning_tile = {tuple(group): group for group in concealed if winning_tile // 4 in group}
        for completed in completed_by_the_winning_tile.values():
            fu.append(FuCalculator.calculate_fu(sets_and_pair, winning_tile, completed, config, valued_tiles, melds)[1])
    return sorted(fu)


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
