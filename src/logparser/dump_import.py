"""Dump import: fills the log store from a database dump of Tenhou logs.

A dump is V1's SQLite format: a table `logs(log_id, log_content)` mapping each
log ID to its log XML, bz2-compressed. Other columns are ignored. The dump is
only read, never changed, and no network is used.

Logs already in the log store are left as they are, so importing a dump again
adds nothing. A row that holds no usable log is skipped with a reason and the
import carries on.
"""

import bz2
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from logparser.log_store import LOG_ID, LogStore


@dataclass
class ImportSummary:
    added: int = 0
    already_stored: int = 0
    skipped: dict[str, int] = field(default_factory=dict)  # rows not imported, by reason


def import_dump(dump: Path, store: LogStore) -> ImportSummary:
    summary = ImportSummary()
    skipped = Counter()
    connection = sqlite3.connect(Path(dump).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for log_id, content in connection.execute("SELECT log_id, log_content FROM logs"):
            if not (isinstance(log_id, str) and LOG_ID.fullmatch(log_id)):
                skipped["not a log ID"] += 1
            elif log_id in store:
                summary.already_stored += 1
            elif content is None:
                skipped["no content"] += 1
            elif (xml_text := _decompress(content)) is None:
                skipped["unreadable content"] += 1
            else:
                store.add(log_id, xml_text)
                summary.added += 1
    finally:
        connection.close()
    summary.skipped = dict(skipped)
    return summary


def _decompress(content) -> str | None:
    """The log XML in a row's bz2-compressed content, or None when it can't be read."""
    try:
        return bz2.decompress(content).decode("utf-8")
    except (OSError, EOFError, TypeError, ValueError):
        return None
