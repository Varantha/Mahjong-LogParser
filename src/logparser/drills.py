"""The drill engine: draws each drill in the drill catalogue from the whole hand store.

The drill catalogue (drills.toml) is configuration, so drills can be added or retuned
without code changes (see docs/adr/0001). A drill names its pool: the hands it may take,
described by their plain values and tags.
"""

import random
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

CATALOGUE_PATH = Path(__file__).with_name("drills.toml")


@dataclass(frozen=True)
class Filter:
    """Hands whose plain values and tags meet every condition.

    A condition names a plain value, or `tags`, and gives one value or a list of them. A hand
    meets it when its value is one of them; for yaku, call types and tags, which hold several
    values, when it holds any of them.
    """

    conditions: dict = field(default_factory=dict)

    def matches(self, hand: dict) -> bool:
        return all(_holds(_value(hand, name), wanted) for name, wanted in self.conditions.items())


def _value(hand: dict, name: str):
    return hand["tags"] if name == "tags" else hand["plainValues"][name]


def _holds(value, wanted) -> bool:
    wanted = wanted if isinstance(wanted, list) else [wanted]
    if isinstance(value, list):
        return any(held in wanted for held in value)
    return value in wanted


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


def draw_drills(catalogue: list[Drill], hands: Iterable[dict], *, seed: int = 0) -> list[DrawnDrill]:
    """Draws each drill's hands at random from its pool. Each drill has its own random draw, seeded
    by `seed` and its key, so adding a drill to the catalogue never changes the hands of another."""
    hands = list(hands)
    drawn = []
    for drill in catalogue:
        pool = sorted(hand["id"] for hand in hands if drill.pool.matches(hand))
        rng = random.Random(f"{seed}/{drill.key}")
        drawn.append(DrawnDrill(drill.key, sorted(rng.sample(pool, min(drill.target, len(pool))))))
    return drawn
