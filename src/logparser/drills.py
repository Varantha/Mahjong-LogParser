"""The drill engine: draws each drill in the drill catalogue from the whole hand store.

The drill catalogue (drills.toml) is configuration, so drills can be added or retuned
without code changes (see docs/adr/0001). A drill names its pool: the hands it may take,
described by their plain values and tags.
"""

import random
import tomllib
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

CATALOGUE_PATH = Path(__file__).with_name("drills.toml")
# The share of a drill with a trap given to lookalikes, unless the catalogue says otherwise.
DEFAULT_LOOKALIKE_SHARE = 0.5


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
class Part:
    """A share of a drill: how many hands it wants, and which hands it may take."""

    name: str
    wanted: int
    takes: Callable[[dict], bool]


@dataclass(frozen=True)
class Drill:
    """A drill in the catalogue. With a trap, `lookalikes` is the share of the drill given to pool hands
    without the trap, so the drill doesn't give the answer away; the rest of the drill has the trap."""

    key: str
    target: int
    pool: Filter = Filter()
    trap: Filter | None = None
    lookalikes: float = DEFAULT_LOOKALIKE_SHARE

    def parts(self) -> list[Part]:
        pool, trap = self.pool, self.trap
        if trap is None:
            return [Part("pool", self.target, pool.matches)]
        lookalikes = round(self.target * self.lookalikes)
        return [
            Part("trap hands", self.target - lookalikes, lambda hand: pool.matches(hand) and trap.matches(hand)),
            Part("lookalikes", lookalikes, lambda hand: pool.matches(hand) and not trap.matches(hand)),
        ]


@dataclass(frozen=True)
class DrawnDrill:
    """A drill's hands. A drill is never shrunk to fit the hand store: when every year of logs together
    still holds too few hands, it keeps its target and falls short by the difference."""

    key: str
    target: int
    hand_ids: list[str]

    @property
    def short_by(self) -> int:
        return self.target - len(self.hand_ids)


def load_catalogue(path: Path = CATALOGUE_PATH) -> list[Drill]:
    with open(path, "rb") as file:
        entries = tomllib.load(file)["drill"]
    return [_drill(entry) for entry in entries]


def _drill(entry: dict) -> Drill:
    return Drill(
        key=entry["key"],
        target=entry["target"],
        pool=Filter(entry.get("pool", {})),
        trap=Filter(entry["trap"]) if "trap" in entry else None,
        lookalikes=entry.get("lookalikes", DEFAULT_LOOKALIKE_SHARE),
    )


def draw_drills(catalogue: list[Drill], hands: Iterable[dict], *, seed: int = 0) -> list[DrawnDrill]:
    """Draws each part of each drill at random from the hands it may take. Each drill has its own random
    draw, seeded by `seed` and its key, so adding a drill to the catalogue never changes another's hands."""
    hands = list(hands)
    drawn = []
    for drill in catalogue:
        rng = random.Random(f"{seed}/{drill.key}")
        hand_ids = []
        for part in drill.parts():
            hand_ids += _newest_first([hand["id"] for hand in hands if part.takes(hand)], part.wanted, rng)
        drawn.append(DrawnDrill(drill.key, drill.target, sorted(hand_ids)))
    return drawn


def _newest_first(hand_ids: list[str], wanted: int, rng: random.Random) -> list[str]:
    """Draws `wanted` hands on the newest year of logs. While that is not enough, it takes every hand of
    that year and draws the rest on the year before, so a drill reaches back only as far as it needs."""
    by_year = defaultdict(list)
    for hand_id in sorted(hand_ids):
        by_year[_year(hand_id)].append(hand_id)
    drawn = []
    for year in sorted(by_year, reverse=True):
        needed = wanted - len(drawn)
        if needed <= 0:
            break
        drawn += by_year[year] if len(by_year[year]) <= needed else rng.sample(by_year[year], needed)
    return sorted(drawn)


def _year(hand_id: str) -> str:
    """The year the hand's game was played: a hand ID starts with its log ID, which starts YYYYMMDDHH."""
    return hand_id[:4]
