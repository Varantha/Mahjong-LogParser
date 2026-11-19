"""Stage 1: ingest parses every win in the log store into the hand store.

Ingest reads only local files: it never uses the network.
"""

from collections import Counter
from dataclasses import dataclass, field

from logparser.hand_store import HandStore
from logparser.log_store import LogStore
from logparser.tenhou import parse_log


@dataclass
class IngestSummary:
    logs: int = 0
    skipped: dict[str, int] = field(default_factory=dict)  # logs not taken, by reason
    hands: int = 0
    quarantined: int = 0


def ingest(logs: LogStore, hands: HandStore) -> IngestSummary:
    summary = IngestSummary()
    skipped = Counter()
    for log_id in logs.log_ids():
        parsed = parse_log(log_id, logs.read(log_id))
        hands.replace_log(log_id, parsed.hands)
        summary.logs += 1
        if parsed.skipped:
            skipped[parsed.skipped] += 1
        summary.hands += len(parsed.hands)
        summary.quarantined += sum(1 for hand in parsed.hands if hand["quarantineReasons"])
    summary.skipped = dict(skipped)
    return summary
