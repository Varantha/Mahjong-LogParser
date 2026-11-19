"""Dump import: fills the log store from a database dump of Tenhou logs.

A dump is V1's SQLite format: a table `logs(log_id, log_content)` mapping each
log ID to its log XML, bz2-compressed. Other columns are ignored. The dump is
only read, never changed, and no network is used.
"""

import bz2
import sqlite3
from pathlib import Path

from logparser.log_store import LogStore


def import_dump(dump: Path, store: LogStore) -> None:
    connection = sqlite3.connect(Path(dump).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for log_id, content in connection.execute("SELECT log_id, log_content FROM logs"):
            store.add(log_id, bz2.decompress(content).decode("utf-8"))
    finally:
        connection.close()
