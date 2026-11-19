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
from logparser.tenhou import NO_OPEN_TANYAO, NO_RED_FIVES, SANMA

TENHOU = "https://tenhou.net"
FILE_INDEXES = (f"{TENHOU}/sc/raw/list.cgi", f"{TENHOU}/sc/raw/list.cgi?old")
LIST_URL = TENHOU + "/sc/raw/dat/{file}"
LOG_URL = TENHOU + "/0/log/?{log_id}"

# Tenhou allows one download at a time and no more. The downloader makes one
# request at a time and, by default, starts each one at least 2 s after the last.
DEFAULT_INTERVAL = 2.0
# Tenhou: refresh the FileIndex no more often than every 20 minutes.
INDEX_REFRESH = 20 * 60.0

# FileIndex entries, e.g. {file:'scc2026110604.html.gz',size:735}
INDEX_ENTRY = re.compile(r"\{\s*file\s*:\s*'([^']+)'\s*,\s*size\s*:\s*([0-9]+)\s*\}")
# One finished game per scc line: its start time, then a replay link holding the log ID.
LISTED_GAME = re.compile(r"^(\d{2}:\d{2}).*?log=([^\"'&>]+)", re.MULTILINE)

SCHEMA = """
-- The scc lists in the FileIndex last read, with their sizes, and when it was read.
CREATE TABLE IF NOT EXISTS file_index (file TEXT PRIMARY KEY, size INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value);
-- Each scc list already read, at the size the FileIndex gave it then.
CREATE TABLE IF NOT EXISTS lists_read (file TEXT PRIMARY KEY, size INTEGER NOT NULL);
-- Every game those lists named. Only log IDs are kept, never the lines (they hold player names).
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
    def __init__(self, log_store: LogStore, state: Path, *, http_get: HttpGet, interval: float = DEFAULT_INTERVAL,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep):
        self._log_store = log_store
        self._http_get = http_get
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last_request: float | None = None
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
        lists_read = dict(self._db.execute("SELECT file, size FROM lists_read"))
        for file, size in self._file_index():
            if lists_read.get(file) != size:  # Tenhou adds late-finishing games to a list after it first appears
                self._read_list(file, size)
        for (log_id,) in self._db.execute("SELECT log_id FROM listed ORDER BY log_id").fetchall():
            if not _ingest_takes(log_id) or log_id in self._log_store:
                continue
            reply = self._get(LOG_URL.format(log_id=log_id))
            self._log_store.add(log_id, reply.body.decode("utf-8"))
            summary.fetched += 1
        return summary

    def _get(self, url: str) -> Response:
        """One request to Tenhou, started no sooner than the interval after the previous one."""
        if self._last_request is not None:
            wait = self._last_request + self._interval - self._clock()
            if wait > 0:
                self._sleep(min(wait, self._interval))  # never longer, even if the clock jumps back
        self._last_request = self._clock()
        return self._http_get(url)

    def _file_index(self) -> list[tuple[str, int]]:
        """The scc lists Tenhou offers, with their sizes, from the recent and the old FileIndex.

        A FileIndex read less than 20 minutes ago is used again rather than read anew.
        """
        read_at = self._db.execute("SELECT value FROM state WHERE key = 'index_read_at'").fetchone()
        if read_at is None or not 0 <= self._clock() - read_at[0] < INDEX_REFRESH:
            read_at = self._clock()
            index = []
            for url in FILE_INDEXES:
                for file, size in INDEX_ENTRY.findall(self._get(url).body.decode("ascii")):
                    if _is_phoenix_list(file):
                        index.append((file, int(size)))
            with self._db:
                self._db.execute("DELETE FROM file_index")
                self._db.executemany("INSERT OR REPLACE INTO file_index (file, size) VALUES (?, ?)", index)
                self._db.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('index_read_at', ?)", (read_at,))
        return self._db.execute("SELECT file, size FROM file_index ORDER BY rowid").fetchall()

    def _read_list(self, file: str, size: int) -> None:
        body = self._get(LIST_URL.format(file=file)).body
        text = gzip.decompress(body).decode("utf-8")
        log_ids = [log_id for _start, log_id in LISTED_GAME.findall(text) if LOG_ID.fullmatch(log_id)]
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO listed (log_id) VALUES (?)", [(i,) for i in log_ids])
            self._db.execute("INSERT OR REPLACE INTO lists_read (file, size) VALUES (?, ?)", (file, size))


def _is_phoenix_list(file: str) -> bool:
    """`scc` files list Phoenix-room games; the old index names them `YYYY/scc...`."""
    return file.rsplit("/", 1)[-1].startswith("scc")


def _ingest_takes(log_id: str) -> bool:
    """Only 4-player games with open tanyao and red fives are worth fetching: ingest skips the rest.

    The game type is the hex field after "gm-" in the log ID, the same value as the log's GO tag.
    """
    game_type = int(log_id[13:17], 16)
    return not game_type & (SANMA | NO_RED_FIVES | NO_OPEN_TANYAO)
