"""Plain values: the facts about a hand that drills filter on directly.

They are worked out from the hand record alone, and gathered in one flat dict so a drill can
filter on any of them by name:

    han, fu, rawFu, limitTier   from the answer key; rawFu is None unless the cross-check matched
    dealer, tsumo, honba, riichiSticks
                                from the situation
    open                        True once the hand has a call other than a closed kan
    yaku                        the answer key's yaku keys, in its order
    doraCount                   the han of the dora, aka dora and ura dora Tenhou recorded. On a
                                yakuman Tenhou records no dora, so the count is 0.
    callTypes                   the type of each call, in the order made

Plain values are never tags. The limit tier is also part of the answer key.
"""

from logparser.calls import CLOSED_KAN

# The named payment caps a hand can reach, lowest first. A kazoe yakuman reaches the yakuman's cap
# with 13 han or more and no yakuman; it is told apart from a yakuman.
LIMIT_TIERS = ("none", "mangan", "haneman", "baiman", "sanbaiman", "kazoe-yakuman", "yakuman")

DORA_YAKU = frozenset({"dora", "aka-dora", "ura-dora"})

# The name of each plain value, in the order a hand lists them. Drills filter on these names.
PLAIN_VALUE_NAMES = ("han", "fu", "rawFu", "limitTier", "dealer", "tsumo", "open", "yaku", "doraCount", "honba",
                     "riichiSticks", "callTypes")


def plain_values(hand: dict) -> dict:
    """The plain values of a hand record."""
    answer_key, situation, calls = hand["answerKey"], hand["situation"], hand["tiles"]["calls"]
    return {
        "han": answer_key["han"],
        "fu": answer_key["fu"],
        "rawFu": answer_key["rawFu"],
        "limitTier": answer_key["limitTier"],
        "dealer": situation["dealer"],
        "tsumo": situation["tsumo"],
        "open": any(call["type"] != CLOSED_KAN for call in calls),
        "yaku": [yaku["key"] for yaku in answer_key["yaku"]],
        "doraCount": sum(yaku["han"] for yaku in answer_key["yaku"] if yaku["key"] in DORA_YAKU),
        "honba": situation["honba"],
        "riichiSticks": situation["riichiSticks"],
        "callTypes": [call["type"] for call in calls],
    }
