"""Tags: named facts derived from a hand, often a trap a player could fall into.

A hand's tags are a list of stable string keys owned by the trainer bundle
contract. Players never see them before answering; the trainer may show them
afterwards, as the lesson. Plain values such as han, fu or yaku are never tags:
drills filter on those directly.

Each tag is worked out from the hand record alone, plain values included. To
add one, write a function that takes a hand record and says whether the hand
has the tag, list it in TAGS under its key, and add the key to the schema's
`tagKey` enum.
"""

from logparser.tiles import kinds

# Yaku worth 1 han less when the hand is open (kuisagari).
YAKU_LOSING_A_HAN_WHEN_OPEN = frozenset({"sanshoku-doujun", "ittsu", "chanta", "junchan", "honitsu", "chinitsu"})

# A dora indicator names the next tile of its kind as dora. These indicators wrap round to the first.
WRAPAROUND_DORA = {"9m": "1m", "9p": "1p", "9s": "1s", "4z": "1z", "7z": "5z"}  # North names East, Chun names Haku


def _kuisagari(hand: dict) -> bool:
    """The hand is open and has a yaku worth 1 han less because it is open."""
    plain = hand["plainValues"]
    return plain["open"] and not YAKU_LOSING_A_HAN_WHEN_OPEN.isdisjoint(plain["yaku"])


def _wraparound_dora(hand: dict) -> bool:
    """A dora indicator wraps round and the hand holds that dora. Kan dora indicators count; ura dora indicators don't."""
    tiles = hand["tiles"]
    held = set(kinds(tiles["concealed"] + "".join(call["tiles"] for call in tiles["calls"])))
    return any(WRAPAROUND_DORA.get(indicator) in held for indicator in kinds(tiles["doraIndicators"]))


# Every tag, by key, in the order a hand lists them.
TAGS = {
    "kuisagari": _kuisagari,
    "wraparound-dora": _wraparound_dora,
}


def hand_tags(hand: dict) -> list[str]:
    """The keys of the tags the hand record has."""
    return [key for key, has_tag in TAGS.items() if has_tag(hand)]
