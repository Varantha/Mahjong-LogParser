"""Dump import: fills the log store from a database dump of Tenhou logs.

A dump is V1's SQLite format: a table `logs(log_id, log_content)` mapping each
log ID to its log XML, bz2-compressed. Other columns are ignored. The dump is
only read, never changed, and no network is used.

Logs already in the log store are left as they are, so importing a dump again
adds nothing.
"""

import bz2
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from logparser.log_store import LogStore


@dataclass
class ImportSummary:
    added: int = 0
    already_stored: int = 0


def import_dump(dump: Path, store: LogStore) -> ImportSummary:
    summary = ImportSummary()
    connection = sqlite3.connect(Path(dump).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for log_id, content in connection.execute("SELECT log_id, log_content FROM logs"):
            if log_id in store:
                summary.already_stored += 1
                continue
            store.add(log_id, bz2.decompress(content).decode("utf-8"))
            summary.added += 1
    finally:
        connection.close()
    return summary
