"""How many hands have each tag and reach each limit tier, as the ingest report and the manifest count them."""

from collections import Counter
from collections.abc import Iterable

from logparser.plain_values import LIMIT_TIERS
from logparser.tags import TAGS


class HandCounts:
    """Hands counted by tag and by limit tier. Every tag and every tier is listed, with 0 when no hand
    counted has it."""

    def __init__(self, hands: Iterable[dict] = ()) -> None:
        self._tags = Counter()
        self._limit_tiers = Counter()
        for hand in hands:
            self.add(hand)

    def add(self, hand: dict) -> None:
        self._tags.update(hand["tags"])
        self._limit_tiers[hand["plainValues"]["limitTier"]] += 1

    def tags(self) -> dict[str, int]:
        """The hands with each tag, by tag key, in the order hands list their tags."""
        return {tag: self._tags[tag] for tag in TAGS}

    def limit_tiers(self) -> dict[str, int]:
        """The hands at each limit tier, lowest first."""
        return {tier: self._limit_tiers[tier] for tier in LIMIT_TIERS}
