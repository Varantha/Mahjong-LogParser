"""The downloader fills the log store from Tenhou's scc lists of Phoenix-room games.

Every test talks to a fake Tenhou: none of them touches the network.
"""

import pytest

from fake_tenhou import FakeClock, FakeTenhou
from logparser.downloader import Downloader
from logparser.log_store import LogStore
from tenhou_xml import closed_win, game, init

GAME_A = "2026110604gm-00a9-0000-0000000a"
GAME_B = "2026110604gm-00a1-0000-0000000b"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def tenhou(clock):
    return FakeTenhou(clock)


@pytest.fixture
def log_store(tmp_path):
    return LogStore(tmp_path / "log-store")


@pytest.fixture
def state(tmp_path):
    return tmp_path / "downloader.sqlite"


@pytest.fixture
def download(state, log_store, tenhou, clock, no_network):
    """Runs the downloader once against the fake Tenhou and returns its summary."""

    def run(max_logs=None, **options):
        with Downloader(log_store, state, http_get=tenhou, clock=clock, sleep=clock.sleep, **options) as downloader:
            return downloader.run(max_logs=max_logs)

    return run


def log(n: int) -> str:
    return game(init(round_number=n % 8), closed_win())


def test_games_in_an_scc_list_are_fetched_into_the_log_store(tenhou, log_store, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B)
    tenhou.add_log(GAME_A, log(1))
    tenhou.add_log(GAME_B, log(2))

    download()

    assert {log_id: log_store.read(log_id) for log_id in log_store.log_ids()} == {GAME_A: log(1), GAME_B: log(2)}
