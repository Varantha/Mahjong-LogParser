"""Stage 1: ingest parses every win in the log store into the hand store.

Given a reports folder, each ingest also writes its ingest report there, in a
folder of its own named after the time it ran:

    report.json   the logs read and skipped, the hands parsed, verified and
                  quarantined, and the quarantined hands' IDs by reason code

Ingest reads only local files: it never uses the network.
"""

import json
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import version
from itertools import count
from pathlib import Path

from logparser.hand_store import HandStore
from logparser.log_store import LogStore
from logparser.plain_values import LIMIT_TIERS
from logparser.tags import TAGS
from logparser.tenhou import parse_log


@dataclass
class IngestSummary:
    logs: int = 0
    skipped: dict[str, int] = field(default_factory=dict)  # logs not taken, by reason
    hands: int = 0
    quarantined: int = 0
    report_folder: Path | None = None  # where this run's ingest report is, if it wrote one


def ingest(logs: LogStore, hands: HandStore, reports: Path | None = None, *,
           ingested_at: datetime | None = None) -> IngestSummary:
    """Parses every log in the log store into the hand store, replacing the hands each log gave
    before. With `reports`, writes this run's ingest report into a new folder there."""
    ingested_at = (ingested_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    summary = IngestSummary()
    skipped = Counter()
    quarantined = defaultdict(list)  # hand IDs, by reason code
    tags = Counter()  # verified hands, by tag
    limit_tiers = Counter()  # verified hands, by limit tier
    if reports is not None:
        summary.report_folder = _new_folder(Path(reports), ingested_at.strftime("%Y%m%dT%H%M%SZ"))
    with (summary.report_folder / "diff.jsonl").open("w", encoding="utf-8") if reports is not None else nullcontext() as diff:
        for log_id in logs.log_ids():
            parsed = parse_log(log_id, logs.read(log_id))
            previous = {hand["id"]: hand for hand in hands.log_hands(log_id)}
            hands.replace_log(log_id, parsed.hands)
            summary.logs += 1
            if parsed.skipped:
                skipped[parsed.skipped] += 1
            summary.hands += len(parsed.hands)
            for hand in parsed.hands:
                summary.quarantined += bool(hand["quarantineReasons"])
                for reason in hand["quarantineReasons"]:
                    quarantined[reason].append(hand["id"])
                if not hand["quarantineReasons"]:
                    tags.update(hand["tags"])
                    limit_tiers[hand["plainValues"]["limitTier"]] += 1
                change = _change(previous.get(hand["id"]), hand)
                if change and diff:
                    diff.write(json.dumps(change) + "\n")
    summary.skipped = dict(skipped)
    if reports is not None:
        report = {
            "ingestedAt": ingested_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": f"mahjong-logparser {version('mahjong-logparser')}",
            "logs": {"read": summary.logs, "skipped": dict(sorted(skipped.items()))},
            "hands": {"parsed": summary.hands, "verified": summary.hands - summary.quarantined,
                      "quarantined": summary.quarantined},
            "quarantined": dict(sorted(quarantined.items())),
            "verified": {"tags": {tag: tags[tag] for tag in TAGS},
                         "limitTiers": {tier: limit_tiers[tier] for tier in LIMIT_TIERS}},
        }
        (summary.report_folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return summary


def _change(previous: dict | None, hand: dict) -> dict | None:
    """How a hand changed since the previous run, or None if it is unchanged or new."""
    if previous is None:
        return None
    change = {}
    added = [tag for tag in hand["tags"] if tag not in previous["tags"]]
    removed = [tag for tag in previous["tags"] if tag not in hand["tags"]]
    if added or removed:
        change["tags"] = {"added": added, "removed": removed}
    return {"id": hand["id"], **change} if change else None


def _new_folder(parent: Path, name: str) -> Path:
    """Makes a folder `name` in `parent`, or `name-2`, `name-3`... if a run in the same second took it."""
    parent.mkdir(parents=True, exist_ok=True)
    for number in count(1):
        folder = parent / (name if number == 1 else f"{name}-{number}")
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        return folder
