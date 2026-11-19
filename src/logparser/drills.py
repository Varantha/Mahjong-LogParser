"""The drill engine: draws each drill in the drill catalogue from the whole hand store.

The drill catalogue (drills.toml) is configuration, so drills can be added or retuned
without code changes (see docs/adr/0001). A drill names its pool: the hands it may take,
described by their plain values and tags.
"""

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

CATALOGUE_PATH = Path(__file__).with_name("drills.toml")


@dataclass(frozen=True)
class Filter:
    """Hands whose plain values and tags meet every condition."""

    conditions: dict = field(default_factory=dict)

    def matches(self, hand: dict) -> bool:
        return all(hand["plainValues"][name] == wanted for name, wanted in self.conditions.items())


@dataclass(frozen=True)
class Drill:
    key: str
    target: int
    pool: Filter = Filter()


@dataclass(frozen=True)
class DrawnDrill:
    key: str
    hand_ids: list[str]


def load_catalogue(path: Path = CATALOGUE_PATH) -> list[Drill]:
    with open(path, "rb") as file:
        entries = tomllib.load(file)["drill"]
    return [Drill(key=entry["key"], target=entry["target"], pool=Filter(entry.get("pool", {}))) for entry in entries]


def draw_drills(catalogue: list[Drill], hands: Iterable[dict]) -> list[DrawnDrill]:
    hands = list(hands)
    return [DrawnDrill(drill.key, sorted(hand["id"] for hand in hands if drill.pool.matches(hand))) for drill in catalogue]
