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

from logparser.plain_values import PLAIN_VALUE_NAMES
from logparser.tags import TAGS

CATALOGUE_PATH = Path(__file__).with_name("drills.toml")
# The share of a drill with a trap given to lookalikes, unless the catalogue says otherwise.
DEFAULT_LOOKALIKE_SHARE = 0.5
DRILL_FIELDS = frozenset({"key", "target", "pool", "trap", "lookalikes", "quotas"})
QUOTA_FIELDS = frozenset({"share", "where"})


class CatalogueError(ValueError):
    """The drill catalogue asks for something the drill engine cannot follow."""


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

    def __str__(self) -> str:
        return ", ".join(f"{name} = {'/'.join(map(str, _listed(wanted)))}" for name, wanted in self.conditions.items())


def _listed(wanted) -> list:
    return wanted if isinstance(wanted, list) else [wanted]


def _value(hand: dict, name: str):
    return hand["tags"] if name == "tags" else hand["plainValues"][name]


def _holds(value, wanted) -> bool:
    wanted = _listed(wanted)
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
class Quota:
    """A share of a drill kept for the pool hands that also meet `where`, so they appear more often
    than in real games."""

    share: float
    where: Filter


@dataclass(frozen=True)
class Drill:
    """A drill in the catalogue.

    With a trap, `lookalikes` is the share of the drill given to pool hands without the trap, so the
    drill doesn't give the answer away; the rest of the drill has the trap. Without one, each quota
    takes its share first and the rest of the drill is drawn from the whole pool.
    """

    key: str
    target: int
    pool: Filter = Filter()
    trap: Filter | None = None
    lookalikes: float = DEFAULT_LOOKALIKE_SHARE
    quotas: tuple[Quota, ...] = ()

    def parts(self) -> list[Part]:
        pool, trap = self.pool, self.trap
        if trap is None:
            quotas = [Part(str(quota.where), round(self.target * quota.share),
                           lambda hand, where=quota.where: pool.matches(hand) and where.matches(hand))
                      for quota in self.quotas]
            return [*quotas, Part("pool", self.target - sum(quota.wanted for quota in quotas), pool.matches)]
        lookalikes = round(self.target * self.lookalikes)
        return [
            Part("trap hands", self.target - lookalikes, lambda hand: pool.matches(hand) and trap.matches(hand)),
            Part("lookalikes", lookalikes, lambda hand: pool.matches(hand) and not trap.matches(hand)),
        ]


@dataclass(frozen=True)
class Shortfall:
    """A part of a drill that every year of logs together could not fill."""

    part: str
    wanted: int
    found: int


@dataclass(frozen=True)
class DrawnDrill:
    """A drill's hands. A drill is never shrunk to fit the hand store: when every year of logs together
    still holds too few hands for a part of it, it keeps its target, the other parts don't make up the
    difference, and it falls short by that much."""

    key: str
    target: int
    hand_ids: list[str]
    shortfalls: list[Shortfall] = field(default_factory=list)

    @property
    def short_by(self) -> int:
        return self.target - len(self.hand_ids)


def load_catalogue(path: Path = CATALOGUE_PATH) -> list[Drill]:
    """Reads the drill catalogue, refusing any drill the engine could not follow as written."""
    with open(path, "rb") as file:
        drills = [_drill(entry) for entry in tomllib.load(file)["drill"]]
    keys = [drill.key for drill in drills]
    for key in keys:
        if keys.count(key) > 1:
            raise CatalogueError(f"drill {key!r}: more than one drill has this key")
    return drills


def _drill(entry: dict) -> Drill:
    key = entry["key"]

    def refuse(problem: str) -> CatalogueError:
        return CatalogueError(f"drill {key!r}: {problem}")

    def conditions(where: dict) -> Filter:
        for name, wanted in where.items():
            if name not in PLAIN_VALUE_NAMES and name != "tags":
                raise refuse(f"{name} is neither a plain value nor tags")
            if name == "tags" and (unknown := [tag for tag in _listed(wanted) if tag not in TAGS]):
                raise refuse(f"no tag is called {', '.join(unknown)}")
        return Filter(where)

    if unknown := sorted(set(entry) - DRILL_FIELDS):
        raise refuse(f"unknown field {', '.join(unknown)}")
    if "lookalikes" in entry and "trap" not in entry:
        raise refuse("lookalikes are only mixed into a drill with a trap")
    if "trap" in entry and "quotas" in entry:
        raise refuse("a drill with a trap shares itself with lookalikes, so it cannot have quotas")
    lookalikes = entry.get("lookalikes", DEFAULT_LOOKALIKE_SHARE)
    if not 0 <= lookalikes <= 1:
        raise refuse("lookalikes must be a share of the drill, from 0 to 1")
    quotas = []
    for quota in entry.get("quotas", []):
        if unknown := sorted(set(quota) - QUOTA_FIELDS):
            raise refuse(f"unknown quota field {', '.join(unknown)}")
        quotas.append(Quota(quota["share"], conditions(quota["where"])))
    if not all(0 <= quota.share for quota in quotas) or sum(quota.share for quota in quotas) > 1:
        raise refuse("the shares of the quotas must add up to no more than the whole drill")
    return Drill(
        key=key,
        target=entry["target"],
        pool=conditions(entry.get("pool", {})),
        trap=conditions(entry["trap"]) if "trap" in entry else None,
        lookalikes=lookalikes,
        quotas=tuple(quotas),
    )


def draw_drills(catalogue: list[Drill], hands: Iterable[dict], *, seed: int = 0) -> list[DrawnDrill]:
    """Draws each part of each drill at random from the hands it may take. Each drill has its own random
    draw, seeded by `seed` and its key, so adding a drill to the catalogue never changes another's hands."""
    hands = list(hands)
    drawn = []
    for drill in catalogue:
        rng = random.Random(f"{seed}/{drill.key}")
        hand_ids, shortfalls = [], []
        for part in drill.parts():
            taken_already = set(hand_ids)
            candidates = [hand["id"] for hand in hands if hand["id"] not in taken_already and part.takes(hand)]
            taken = _newest_first(candidates, part.wanted, rng)
            hand_ids += taken
            if len(taken) < part.wanted:
                shortfalls.append(Shortfall(part.name, part.wanted, len(taken)))
        drawn.append(DrawnDrill(drill.key, drill.target, sorted(hand_ids), shortfalls))
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
