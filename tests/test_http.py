"""The downloader's HTTP client, checked against a small server on this machine (never Tenhou)."""

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from logparser.downloader import DownloadStopped, urllib_get


class LocalServer:
    """Answers each path with a fixed (status, headers, body) and keeps the headers of each request."""

    def __init__(self):
        self.routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.request_headers: list[dict[str, str]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.request_headers.append({k.lower(): v for k, v in self.headers.items()})
                status, headers, body = server.routes.get(self.path, (404, {}, b"Not Found"))
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        self._open = True

    def close(self):
        if self._open:
            self._open = False
            self._httpd.shutdown()
            self._httpd.server_close()


@pytest.fixture
def server():
    local = LocalServer()
    yield local
    local.close()


def test_a_gzip_encoded_reply_is_asked_for_and_decoded(server):
    server.routes["/0/log/?x"] = (200, {"Content-Encoding": "gzip"}, gzip.compress(b"<mjloggm ver=\"2.3\"></mjloggm>"))

    reply = urllib_get(server.url + "/0/log/?x")

    assert (reply.status, reply.body) == (200, b"<mjloggm ver=\"2.3\"></mjloggm>")
    assert "gzip" in server.request_headers[0]["accept-encoding"]


def test_requests_name_the_downloader_because_tenhou_sends_python_s_default_client_an_empty_reply(server):
    server.routes["/0/log/?x"] = (200, {}, b"<mjloggm/>")

    urllib_get(server.url + "/0/log/?x")

    user_agent = server.request_headers[0].get("user-agent", "")
    assert user_agent.startswith("Mahjong-LogParser/") and "Python-urllib" not in user_agent


def test_a_redirect_is_followed(server):
    server.routes["/sc/raw/dat/scc2026110604.html.gz"] = (302, {"Location": "/moved/scc2026110604.html.gz"}, b"")
    server.routes["/moved/scc2026110604.html.gz"] = (200, {"Content-Type": "application/x-gzip"}, gzip.compress(b"list"))

    reply = urllib_get(server.url + "/sc/raw/dat/scc2026110604.html.gz")

    assert (reply.status, gzip.decompress(reply.body)) == (200, b"list")


def test_an_error_reply_comes_back_with_its_status_and_headers(server):
    server.routes["/0/log/?x"] = (503, {"Retry-After": "120"}, b"busy")

    reply = urllib_get(server.url + "/0/log/?x")

    assert (reply.status, reply.headers["retry-after"], reply.body) == (503, "120", b"busy")


def test_a_server_that_cannot_be_reached_stops_the_download(server):
    url = server.url
    server.close()

    with pytest.raises(DownloadStopped, match="could not reach"):
        urllib_get(url + "/sc/raw/list.cgi")
