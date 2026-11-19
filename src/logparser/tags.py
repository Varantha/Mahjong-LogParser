"""Tags: named facts derived from a hand, often a trap a player could fall into.

A hand's tags are a list of stable string keys owned by the trainer bundle
contract. Players never see them before answering; the trainer may show them
afterwards, as the lesson. Plain values such as han, fu or yaku are never tags:
drills filter on those directly.

Each tag is worked out from the hand record alone, plain values included, and
the tag settings, which hold the thresholds the first milestone tunes. To add a
tag, write a function that takes a hand record and the tag settings and says
whether the hand has the tag, list it in TAGS under its key, and add the key to
the schema's `tagKey` enum.
"""

from dataclasses import dataclass

from logparser.recalculation import points
from logparser.tiles import kinds

# Yaku worth 1 han less when the hand is open (kuisagari).
YAKU_LOSING_A_HAN_WHEN_OPEN = frozenset({"sanshoku-doujun", "ittsu", "chanta", "junchan", "honitsu", "chinitsu"})

# A dora indicator names the next tile of its kind as dora. These indicators wrap round to the first.
WRAPAROUND_DORA = {"9m": "1m", "9p": "1p", "9s": "1s", "4z": "1z", "7z": "5z"}  # North names East, Chun names Haku


@dataclass(frozen=True)
class TagSettings:
    """The thresholds of the tags that can be tuned."""

    high_fu: int = 50  # the fewest fu after rounding a hand with high-fu has


def _kuisagari(hand: dict, settings: TagSettings) -> bool:
    """The hand is open and has a yaku worth 1 han less because it is open."""
    plain = hand["plainValues"]
    return plain["open"] and not YAKU_LOSING_A_HAN_WHEN_OPEN.isdisjoint(plain["yaku"])


def _wraparound_dora(hand: dict, settings: TagSettings) -> bool:
    """A dora indicator wraps round and the hand holds that dora. Kan dora indicators count; ura dora indicators don't."""
    tiles = hand["tiles"]
    held = set(kinds(tiles["concealed"] + "".join(call["tiles"] for call in tiles["calls"])))
    return any(WRAPAROUND_DORA.get(indicator) in held for indicator in kinds(tiles["doraIndicators"]))


def _ambiguous_wait(hand: dict, settings: TagSettings) -> bool:
    """The hand's tiles split into sets and a pair in more than one way, and the split chosen changes
    the fu. Tenhou scores the split worth the most points."""
    return len(set(hand["splitFu"] or [])) > 1


def _open_pinfu_shape(hand: dict, settings: TagSettings) -> bool:
    """The hand is open and its raw fu are 20, which Tenhou scores as 30 fu."""
    plain = hand["plainValues"]
    return plain["open"] and plain["rawFu"] == 20


def _fu_mangan(hand: dict, settings: TagSettings) -> bool:
    """The hand reaches mangan at 3 or 4 han because of its fu: 3 han with 70 fu or more, or 4 han with 40 or more."""
    plain = hand["plainValues"]
    return (plain["han"] == 3 and plain["fu"] >= 70) or (plain["han"] == 4 and plain["fu"] >= 40)


def _high_fu(hand: dict, settings: TagSettings) -> bool:
    """The hand's fu after rounding reach the high-fu threshold."""
    return hand["plainValues"]["fu"] >= settings.high_fu


def _knife_edge_fu(hand: dict, settings: TagSettings) -> bool:
    """Re-scoring the hand with raw fu 2 higher or 2 lower changes its points. Hands with fixed fu,
    chiitoitsu and pinfu tsumo, never have it, nor does a hand with no raw fu."""
    plain = hand["plainValues"]
    if plain["rawFu"] is None or "chiitoitsu" in plain["yaku"] or ("pinfu" in plain["yaku"] and plain["tsumo"]):
        return False

    def scored(fu: int) -> int:
        return points(han=plain["han"], fu=fu, dealer=plain["dealer"], tsumo=plain["tsumo"])

    return any(scored(_rounded_fu(plain["rawFu"] + step, open_hand=plain["open"])) != scored(plain["fu"])
               for step in (-2, 2))


def _rounded_fu(raw_fu: int, *, open_hand: bool) -> int:
    """Raw fu rounded up to the next 10. An open hand scores at least 30 fu: Tenhou scores the 20 raw fu
    of the open pinfu shape as 30."""
    fu = -(-raw_fu // 10) * 10
    return max(fu, 30) if open_hand else fu


# Every tag, by key, in the order a hand lists them.
TAGS = {
    "kuisagari": _kuisagari,
    "wraparound-dora": _wraparound_dora,
    "ambiguous-wait": _ambiguous_wait,
    "open-pinfu-shape": _open_pinfu_shape,
    "fu-mangan": _fu_mangan,
    "high-fu": _high_fu,
    "knife-edge-fu": _knife_edge_fu,
}


def hand_tags(hand: dict, settings: TagSettings = TagSettings()) -> list[str]:
    """The keys of the tags the hand record has."""
    return [key for key, has_tag in TAGS.items() if has_tag(hand, settings)]
