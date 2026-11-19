"""The downloader fills the log store from Tenhou.

It reads Tenhou's FileIndex, then the `scc` lists of Phoenix-room games it
names, then fetches each listed log. Given an ID list of log IDs instead, it
fetches the logs that list names. It is the only part of the pipeline that
uses the network.

It keeps to Tenhou's rules for automatic downloads (https://tenhou.net/sc/raw/):
one download at a time, so it never makes two requests at once and a second
downloader on the same state cannot start; the FileIndex at most every 20
minutes; and an scc list again only when its size has changed. Its state (lists
read, log IDs listed, logs Tenhou could not give) lets a stopped run carry on.
"""

import gzip
import http.client
import re
import sqlite3
import time
import urllib.error
import urllib.request
import zlib
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from logparser.log_store import LOG_ID, LogStore
from logparser.tenhou import skip_reason

TENHOU = "https://tenhou.net"
FILE_INDEXES = (f"{TENHOU}/sc/raw/list.cgi", f"{TENHOU}/sc/raw/list.cgi?old")
LIST_URL = TENHOU + "/sc/raw/dat/{file}"
LOG_URL = TENHOU + "/0/log/?{log_id}"

# Tenhou allows one download at a time and no more. The downloader makes one
# request at a time and, by default, starts each one at least 2 s after the last.
DEFAULT_INTERVAL = 2.0
# Tenhou: refresh the FileIndex no more often than every 20 minutes.
INDEX_REFRESH = 20 * 60.0
TIMEOUT = 60.0  # seconds to wait for Tenhou to answer
# Tenhou answers Python's default client with an empty body, so name this one.
USER_AGENT = "Mahjong-LogParser/2"

# The FileIndex is a JavaScript call, list([...]);, holding entries such as {file:'scc2026110604.html.gz',size:735}.
FILE_INDEX = re.compile(r"\s*list\s*\(\s*(?:\[(.*)\])?\s*\)\s*;\s*", re.DOTALL)
INDEX_ENTRY = re.compile(r"\{\s*file\s*:\s*'([^']+)'\s*,\s*size\s*:\s*([0-9]+)\s*\}")
# One finished game per scc line: its start time, then a replay link holding the log ID.
LISTED_GAME = re.compile(r"^\d{2}:\d{2}.*?log=([^\"'&>]+)", re.MULTILINE)
# What a log Tenhou serves starts with, after an optional XML declaration.
MJLOG_START = re.compile(r"\A\s*(?:<\?xml\s[\s\S]*?\?>\s*)?<mjloggm(?=[\s/>])")

SCHEMA = """
-- The scc lists in the FileIndex last read, with their sizes.
CREATE TABLE IF NOT EXISTS file_index (file TEXT PRIMARY KEY, size INTEGER NOT NULL);
-- When the FileIndex was last read (index_read_at) and when the last request started (last_request_at).
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value);
-- Each scc list already read, at the size the FileIndex gave it then.
CREATE TABLE IF NOT EXISTS lists_read (file TEXT PRIMARY KEY, size INTEGER NOT NULL);
-- Every game those lists named. Only log IDs are kept, never the lines (they hold player names).
CREATE TABLE IF NOT EXISTS listed (log_id TEXT PRIMARY KEY);
-- Games listed in an scc list or an ID list that Tenhou could not give a log for. They are not asked for again.
CREATE TABLE IF NOT EXISTS failed (log_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
"""


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)  # names in lower case


HttpGet = Callable[[str], Response]


class DownloadStopped(Exception):
    """The download stopped before it was done: Tenhou asked it to wait, Tenhou could not be reached,
    or another download is running. Run it again later to carry on where it stopped."""


@dataclass
class DownloadSummary:
    lists_read: int = 0  # scc lists read this run
    fetched: int = 0  # logs added to the log store this run
    failed: int = 0  # logs Tenhou could not give this run
    remaining: int = 0  # listed logs still to fetch, for a later run
    already_stored: int = 0  # ID-list entries the log store already held
    skipped: dict[str, int] = field(default_factory=dict)  # ID-list entries not fetched, by reason
    not_log_ids: list[tuple[int, str]] = field(default_factory=list)  # (line number, line) of each ID-list line skipped


class Downloader:
    def __init__(self, log_store: LogStore, state: Path, *, http_get: HttpGet | None = None,
                 interval: float = DEFAULT_INTERVAL, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep):
        self._log_store = log_store
        self._http_get = http_get or urllib_get
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        state = Path(state)
        state.parent.mkdir(parents=True, exist_ok=True)
        # The state file stays locked while this downloader is open, so a second one on it cannot start.
        self._db = sqlite3.connect(state, timeout=0)
        try:
            self._db.execute("PRAGMA locking_mode = EXCLUSIVE")
            self._db.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as error:
            self._db.close()
            raise DownloadStopped(f"another download is using {state}: Tenhou allows one download at a time") from error
        self._db.executescript(SCHEMA)
        self._last_request = self._state("last_request_at")  # the gap holds from one run to the next

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
                summary.lists_read += self._read_list(file, size)
        listed = self._db.execute(
            "SELECT log_id FROM listed WHERE log_id NOT IN (SELECT log_id FROM failed) ORDER BY log_id").fetchall()
        to_fetch = [log_id for (log_id,) in listed if not _skip_reason(log_id) and log_id not in self._log_store]
        self._fetch_logs(to_fetch, max_logs, summary)
        return summary

    def run_id_list(self, lines: Iterable[str], max_logs: int | None = None) -> DownloadSummary:
        """Fetches the logs an ID list names, given its lines, one log ID per line, instead of reading Tenhou's
        scc lists. Blank lines are ignored, and lines that are not log IDs are skipped and kept in the summary."""
        summary = DownloadSummary()
        skipped = Counter()
        listed = set()
        for number, line in enumerate(lines, start=1):
            if not (log_id := line.strip()):
                continue
            if LOG_ID.fullmatch(log_id):
                listed.add(log_id)
            else:
                summary.not_log_ids.append((number, log_id))
                skipped["not a log ID"] += 1
        failed = {log_id for (log_id,) in self._db.execute("SELECT log_id FROM failed")}
        to_fetch = []
        for log_id in sorted(listed):
            if log_id in self._log_store:
                summary.already_stored += 1
            elif reason := _skip_reason(log_id):
                skipped[reason] += 1
            elif log_id in failed:
                skipped["failed before"] += 1
            else:
                to_fetch.append(log_id)
        summary.skipped = dict(skipped)
        self._fetch_logs(to_fetch, max_logs, summary)
        return summary

    def _fetch_logs(self, to_fetch: list[str], max_logs: int | None, summary: DownloadSummary) -> None:
        """Fetches each log in turn, up to max_logs of them, recording those Tenhou cannot give as failed."""
        summary.remaining = len(to_fetch)
        for log_id in to_fetch[:max_logs]:
            summary.remaining -= 1
            xml, failure = self._fetch_log(log_id)
            if failure:
                with self._db:
                    self._db.execute("INSERT OR REPLACE INTO failed (log_id, reason) VALUES (?, ?)", (log_id, failure))
                summary.failed += 1
            else:
                self._log_store.add(log_id, xml)
                summary.fetched += 1

    def _get(self, url: str) -> Response:
        """One request to Tenhou, started no sooner than the interval after the previous one."""
        if self._last_request is not None:
            wait = self._last_request + self._interval - self._clock()
            if wait > 0:
                self._sleep(min(wait, self._interval))  # never longer, even if the clock jumps back
        self._last_request = self._clock()
        with self._db:
            self._set_state("last_request_at", self._last_request)
        reply = self._http_get(url)
        if reply.status in (408, 429) or reply.status >= 500:
            retry_after = reply.headers.get("retry-after")
            raise DownloadStopped(f"Tenhou answered {reply.status} for {url}"
                                  + (f"; it asks to retry after {retry_after}" if retry_after else ""))
        return reply

    def _fetch_log(self, log_id: str) -> tuple[str | None, str | None]:
        """A log's XML, or why Tenhou could not give it."""
        reply = self._get(LOG_URL.format(log_id=log_id))
        if reply.status != 200:
            return None, f"HTTP {reply.status}"
        if not reply.body:  # says nothing about the log: Tenhou is not serving this client
            raise DownloadStopped(f"Tenhou sent an empty reply for {log_id}; it may be refusing this client")
        try:
            xml = reply.body.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None, "not UTF-8"
        if not MJLOG_START.match(xml):
            return None, "no log content"
        return xml, None

    def _file_index(self) -> list[tuple[str, int]]:
        """The scc lists Tenhou offers, with their sizes, from the recent and the old FileIndex.

        A FileIndex read less than 20 minutes ago is used again rather than read anew.
        """
        read_at = self._state("index_read_at")
        if read_at is None or not 0 <= self._clock() - read_at < INDEX_REFRESH:
            read_at = self._clock()
            index = []
            for url in FILE_INDEXES:
                reply = self._get(url)
                entries = FILE_INDEX.fullmatch(reply.body.decode("utf-8", "replace")) if reply.status == 200 else None
                if entries is None:
                    raise DownloadStopped(f"Tenhou's FileIndex at {url} could not be read (HTTP {reply.status})")
                for file, size in INDEX_ENTRY.findall(entries[1] or ""):
                    if _is_phoenix_list(file):
                        index.append((file, int(size)))
            with self._db:
                self._db.execute("DELETE FROM file_index")
                self._db.executemany("INSERT OR REPLACE INTO file_index (file, size) VALUES (?, ?)", index)
                self._set_state("index_read_at", read_at)
        return self._db.execute("SELECT file, size FROM file_index ORDER BY rowid").fetchall()

    def _state(self, key: str) -> float | None:
        row = self._db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return None if row is None else row[0]

    def _set_state(self, key: str, value: float) -> None:
        self._db.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))

    def _read_list(self, file: str, size: int) -> bool:
        """Keeps the log IDs an scc list names. A list that cannot be read is left for the next run."""
        reply = self._get(LIST_URL.format(file=file))
        if reply.status != 200:
            return False
        try:
            text = gzip.decompress(reply.body).decode("utf-8", "replace")
        except (OSError, EOFError, zlib.error):
            return False
        log_ids = [log_id for log_id in LISTED_GAME.findall(text) if LOG_ID.fullmatch(log_id)]
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO listed (log_id) VALUES (?)", [(i,) for i in log_ids])
            self._db.execute("INSERT OR REPLACE INTO lists_read (file, size) VALUES (?, ?)", (file, size))
        return True


def _is_phoenix_list(file: str) -> bool:
    """`scc` files list Phoenix-room games; the old index names them `YYYY/scc...`."""
    return file.rsplit("/", 1)[-1].startswith("scc")


def _skip_reason(log_id: str) -> str | None:
    """Why ingest would skip this game, or None if it takes it. Only 4-player games with open tanyao and red
    fives are worth fetching.

    The game type is the hex field after "gm-" in the log ID, the same value as the log's GO tag.
    """
    return skip_reason(int(log_id[13:17], 16))


def urllib_get(url: str) -> Response:
    """Fetches a URL, following redirects and decoding a gzip-encoded reply. Error replies are returned, not raised."""
    request = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
    try:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as reply:
                status, headers, body = reply.status, reply.headers, reply.read()
        except urllib.error.HTTPError as error:
            status, headers, body = error.code, error.headers, error.read()
        if headers.get("Content-Encoding", "").lower() == "gzip":
            body = gzip.decompress(body)
    except (OSError, EOFError, http.client.HTTPException) as error:
        raise DownloadStopped(f"could not reach {url}: {error}") from error
    return Response(status, body, {name.lower(): value for name, value in headers.items()})
