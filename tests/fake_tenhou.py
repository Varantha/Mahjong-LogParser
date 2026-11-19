"""A fake Tenhou for downloader tests, so no test ever touches the network.

It serves made-up file indexes, scc lists and logs at Tenhou's URLs and keeps
every URL it was asked for, with the time it was asked. Nothing here is copied
from Tenhou: every scc line, player name and log is invented.
"""

import gzip

from logparser.downloader import Response

TENHOU = "https://tenhou.net"
FILE_INDEXES = (f"{TENHOU}/sc/raw/list.cgi", f"{TENHOU}/sc/raw/list.cgi?old")  # recent, then old


class FakeClock:
    """A wall clock that only moves when the code under test sleeps, or when a test moves it on."""

    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


def scc_line(log_id: str, start: str = "04:05", label: str = "四鳳南喰赤－") -> str:
    """One finished game as an scc list shows it: start | minutes | room | replay link | players."""
    link = f'<a href="http://tenhou.net/0/?log={log_id}">牌譜</a>'
    return f"{start} | 33 | {label} | {link} | Aa(+50.0) Bb(+10.0) Cc(-20.0) Dd(-40.0)<br>"


class FakeTenhou:
    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.requests: list[tuple[float, str]] = []
        self._recent: dict[str, bytes] = {}  # file -> gzip body, listed by list.cgi
        self._old: dict[str, bytes] = {}  # "YYYY/file" -> gzip body, listed by list.cgi?old
        self._logs: dict[str, bytes] = {}
        self._replies: dict[str, Response] = {}

    def add_list(self, file: str, *log_ids: str, old: bool = False) -> None:
        """Publishes an scc list (or any other file) holding these games; adding it again replaces it."""
        # Tenhou's scc lists end lines with both <br>\r\n and <br>\n.
        text = "".join(scc_line(log_id) + ("\r\n" if n % 2 else "\n") for n, log_id in enumerate(log_ids))
        (self._old if old else self._recent)[file] = gzip.compress(text.encode("utf-8"))

    def add_log(self, log_id: str, xml: str) -> None:
        self._logs[log_id] = xml.encode("utf-8")

    def reply(self, url: str, status: int, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        """Answers this URL with a fixed reply instead of what Tenhou would serve."""
        self._replies[url] = Response(status, body, headers or {})

    def urls(self) -> list[str]:
        return [url for _, url in self.requests]

    def log_url(self, log_id: str) -> str:
        return f"{TENHOU}/0/log/?{log_id}"

    def list_url(self, file: str) -> str:
        return f"{TENHOU}/sc/raw/dat/{file}"

    def __call__(self, url: str) -> Response:
        self.requests.append((self.clock(), url))
        if url in self._replies:
            return self._replies[url]
        if url == FILE_INDEXES[0]:
            return Response(200, _index(self._recent))
        if url == FILE_INDEXES[1]:
            return Response(200, _index(self._old))
        files = self._recent | self._old
        for file, body in files.items():
            if url == self.list_url(file):
                return Response(200, body)
        for log_id, xml in self._logs.items():
            if url == self.log_url(log_id):
                return Response(200, xml)
        return Response(404, b"Not Found")


def _index(files: dict[str, bytes]) -> bytes:
    """Tenhou's FileIndex: a JavaScript call listing each file with its size, with CRLF line endings."""
    entries = ",\r\n".join(f"{{file:'{file}',size:{len(body)}}}" for file, body in files.items())
    return f"list([\r\n{entries}\r\n]);\r\n".encode("ascii")
