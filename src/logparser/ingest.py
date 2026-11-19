"""Stage 1: ingest parses every win in the log store into the hand store.

Given a reports folder, each ingest also writes its ingest report there, in a
folder of its own named after the time it ran:

    report.json   the logs read and skipped, the hands parsed, verified and
                  quarantined, and the quarantined hands' IDs by reason code

Ingest reads only local files: it never uses the network.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from logparser.hand_store import HandStore
from logparser.log_store import LogStore
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
    for log_id in logs.log_ids():
        parsed = parse_log(log_id, logs.read(log_id))
        hands.replace_log(log_id, parsed.hands)
        summary.logs += 1
        if parsed.skipped:
            skipped[parsed.skipped] += 1
        summary.hands += len(parsed.hands)
        for hand in parsed.hands:
            summary.quarantined += bool(hand["quarantineReasons"])
            for reason in hand["quarantineReasons"]:
                quarantined[reason].append(hand["id"])
    summary.skipped = dict(skipped)
    if reports is not None:
        summary.report_folder = Path(reports) / ingested_at.strftime("%Y%m%dT%H%M%SZ")
        summary.report_folder.mkdir(parents=True)
        report = {
            "ingestedAt": ingested_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": f"mahjong-logparser {version('mahjong-logparser')}",
            "logs": {"read": summary.logs, "skipped": dict(sorted(skipped.items()))},
            "hands": {"parsed": summary.hands, "verified": summary.hands - summary.quarantined,
                      "quarantined": summary.quarantined},
            "quarantined": dict(sorted(quarantined.items())),
        }
        (summary.report_folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return summary
