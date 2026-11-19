"""The downloader fills the log store from Tenhou.

It reads Tenhou's FileIndex, then the `scc` lists of Phoenix-room games it
names, then fetches each listed log. It is the only part of the pipeline that
uses the network.
"""

import gzip
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from logparser.log_store import LOG_ID, LogStore

TENHOU = "https://tenhou.net"
FILE_INDEXES = (f"{TENHOU}/sc/raw/list.cgi", f"{TENHOU}/sc/raw/list.cgi?old")
LIST_URL = TENHOU + "/sc/raw/dat/{file}"
LOG_URL = TENHOU + "/0/log/?{log_id}"

# FileIndex entries, e.g. {file:'scc2026110604.html.gz',size:735}
INDEX_ENTRY = re.compile(r"\{\s*file\s*:\s*'([^']+)'\s*,\s*size\s*:\s*([0-9]+)\s*\}")
# One finished game per scc line: its start time, then a replay link holding the log ID.
LISTED_GAME = re.compile(r"^(\d{2}:\d{2}).*?log=([^\"'&>]+)", re.MULTILINE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS listed (log_id TEXT PRIMARY KEY);
"""


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)  # names in lower case


HttpGet = Callable[[str], Response]


@dataclass
class DownloadSummary:
    fetched: int = 0


class Downloader:
    def __init__(self, log_store: LogStore, state: Path, *, http_get: HttpGet,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep):
        self._log_store = log_store
        self._http_get = http_get
        state = Path(state)
        state.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(state)
        self._db.executescript(SCHEMA)

    def __enter__(self) -> "Downloader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def run(self, max_logs: int | None = None) -> DownloadSummary:
        summary = DownloadSummary()
        for index_url in FILE_INDEXES:
            for file, _size in INDEX_ENTRY.findall(self._http_get(index_url).body.decode("ascii")):
                self._read_list(file)
        for (log_id,) in self._db.execute("SELECT log_id FROM listed ORDER BY log_id").fetchall():
            reply = self._http_get(LOG_URL.format(log_id=log_id))
            self._log_store.add(log_id, reply.body.decode("utf-8"))
            summary.fetched += 1
        return summary

    def _read_list(self, file: str) -> None:
        body = self._http_get(LIST_URL.format(file=file)).body
        text = gzip.decompress(body).decode("utf-8")
        log_ids = [log_id for _start, log_id in LISTED_GAME.findall(text) if LOG_ID.fullmatch(log_id)]
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO listed (log_id) VALUES (?)", [(i,) for i in log_ids])
