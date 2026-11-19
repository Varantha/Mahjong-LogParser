"""Stage 2: export builds the trainer bundle from the hand store.

Only verified hands are exported. The drill engine builds each drill in the
drill catalogue by searching the whole hand store (see docs/adr/0001); the
bundle then stores every hand once, split into chunk files, with a manifest
saying which hands belong to which drill. Export reads only local files: it
never uses the network.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

from logparser.drills import DrawnDrill, Drill, draw_drills
from logparser.hand_store import HandStore
from logparser.plain_values import LIMIT_TIERS
from logparser.tags import TAGS

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = Path(__file__).parent / "schema" / "trainer-bundle.schema.json"
DEFAULT_CHUNK_SIZE = 200
# The parts of a hand-store record the trainer sees. Replay links, quarantine
# reasons and anything else stay in the hand store.
BUNDLE_FIELDS = ("id", "situation", "tiles", "answerKey", "plainValues", "tags")


@dataclass(frozen=True)
class ExportSummary:
    manifest: dict
    drills: list[DrawnDrill]

    @property
    def short_drills(self) -> list[DrawnDrill]:
        """The drills that every year of logs in the hand store together could not fill."""
        return [drill for drill in self.drills if drill.short_by]


def export_bundle(hands: HandStore, folder: Path, catalogue: list[Drill], *,
                  chunk_size: int = DEFAULT_CHUNK_SIZE, seed: int = 0,
                  built_at: datetime | None = None) -> ExportSummary:
    """Writes the trainer bundle to `folder`, replacing any earlier bundle there. Returns its manifest and
    each drill as drawn, so the caller can say which drills fall short."""
    drawn = draw_drills(catalogue, hands.verified_hands(), seed=seed)
    drills = [{"key": drill.key, "handIds": drill.hand_ids} for drill in drawn]

    hand_ids = sorted({hand_id for drill in drills for hand_id in drill["handIds"]})
    bundle_hands = [_bundle_hand(hands.get(hand_id)) for hand_id in hand_ids]
    chunks = {
        f"hands-{number:03d}.json": {"schemaVersion": SCHEMA_VERSION, "hands": bundle_hands[start:start + chunk_size]}
        for number, start in enumerate(range(0, len(bundle_hands), chunk_size))
    }
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "build": {
            "builtAt": (built_at or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": f"mahjong-logparser {version('mahjong-logparser')}",
            "seed": seed,
        },
        "counts": {
            "hands": len(bundle_hands),
            "drills": {drill["key"]: len(drill["handIds"]) for drill in drills},
            "tags": {tag: sum(tag in hand["tags"] for hand in bundle_hands) for tag in TAGS},
            "limitTiers": {tier: sum(hand["plainValues"]["limitTier"] == tier for hand in bundle_hands)
                           for tier in LIMIT_TIERS},
        },
        "chunks": list(chunks),
        "drills": drills,
    }

    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    for document in [manifest, *chunks.values()]:
        validator.validate(document)
    _write(Path(folder), manifest, chunks)
    return ExportSummary(manifest, drawn)


def _bundle_hand(record: dict) -> dict:
    return {field: record[field] for field in BUNDLE_FIELDS}


def _write(folder: Path, manifest: dict, chunks: dict[str, dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for stale in [*folder.glob("hands-*.json"), folder / "manifest.json"]:
        stale.unlink(missing_ok=True)
    for name, chunk in chunks.items():
        (folder / name).write_text(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
