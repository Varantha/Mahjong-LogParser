"""The downloader fills the log store from Tenhou's scc lists of Phoenix-room games.

Every test talks to a fake Tenhou: none of them touches the network.
"""

import pytest

from fake_tenhou import FILE_INDEXES, FakeClock, FakeTenhou
from logparser.downloader import Downloader, DownloadStopped
from logparser.log_store import LogStore
from tenhou_xml import closed_win, game, init

GAME_A = "2026110604gm-00a9-0000-0000000a"
GAME_B = "2026110604gm-00a9-0000-0000000b"


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


def test_only_phoenix_room_lists_are_read_from_both_the_recent_and_the_old_file_index(tenhou, log_store, download):
    tenhou.add_list("sca20261106.log.gz", GAME_B)
    tenhou.add_list("scb2026110604.html.gz", GAME_B)
    tenhou.add_list("2026/scc20260101.html.gz", GAME_A, old=True)
    tenhou.add_log(GAME_A, log(1))
    tenhou.add_log(GAME_B, log(2))

    download()

    assert list(log_store.log_ids()) == [GAME_A]


def test_only_games_ingest_takes_are_fetched(tenhou, log_store, download):
    hanchan, east_only, fast = "2026110604gm-00a9-0000-00000001", "2026110604gm-00a1-0000-00000002", "2026110604gm-00e9-0000-00000003"
    sanma, no_aka, no_kuitan = "2026110604gm-00b9-0000-00000004", "2026110604gm-00ab-0000-00000005", "2026110604gm-00ad-0000-00000006"
    tenhou.add_list("scc2026110604.html.gz", hanchan, east_only, fast, sanma, no_aka, no_kuitan)
    for n, log_id in enumerate([hanchan, east_only, fast, sanma, no_aka, no_kuitan]):
        tenhou.add_log(log_id, log(n))

    download()

    assert set(log_store.log_ids()) == {hanchan, east_only, fast}
    assert not {tenhou.log_url(sanma), tenhou.log_url(no_aka), tenhou.log_url(no_kuitan)} & set(tenhou.urls())


def test_a_log_the_log_store_already_holds_is_never_fetched(tenhou, log_store, download):
    log_store.add(GAME_A, log(1))
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B)
    tenhou.add_log(GAME_B, log(2))

    download()

    assert tenhou.log_url(GAME_A) not in tenhou.urls()
    assert log_store.read(GAME_A) == log(1)


def request_gaps(tenhou) -> list[float]:
    times = [time for time, _ in tenhou.requests]
    return [later - earlier for earlier, later in zip(times, times[1:])]


def test_by_default_requests_start_at_least_two_seconds_apart(tenhou, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B)
    tenhou.add_log(GAME_A, log(1))
    tenhou.add_log(GAME_B, log(2))

    download()

    assert len(tenhou.requests) == 5 and min(request_gaps(tenhou)) >= 2.0


def test_the_gap_between_requests_can_be_set(tenhou, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B)
    tenhou.add_log(GAME_A, log(1))
    tenhou.add_log(GAME_B, log(2))

    download(interval=7.5)

    assert request_gaps(tenhou) == [7.5, 7.5, 7.5, 7.5]


MINUTE = 60.0
GAME_C = "2026110605gm-00a9-0000-0000000c"


def test_an_scc_list_is_read_again_only_when_its_size_in_the_file_index_changed(tenhou, clock, log_store, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A)
    tenhou.add_list("scc2026110605.html.gz", GAME_B)
    for n, log_id in enumerate([GAME_A, GAME_B, GAME_C]):
        tenhou.add_log(log_id, log(n))
    download()
    clock.advance(30 * MINUTE)
    tenhou.add_list("scc2026110605.html.gz", GAME_B, GAME_C)  # a game that finished late joins the list
    tenhou.requests.clear()

    download()

    assert tenhou.urls() == [*FILE_INDEXES, tenhou.list_url("scc2026110605.html.gz"), tenhou.log_url(GAME_C)]


def test_the_file_index_is_read_at_most_once_every_twenty_minutes(tenhou, clock, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A)
    tenhou.add_log(GAME_A, log(1))
    download()

    clock.advance(19 * MINUTE)
    download()
    clock.advance(2 * MINUTE)
    download()

    assert [url for url in tenhou.urls() if url in FILE_INDEXES] == [*FILE_INDEXES, *FILE_INDEXES]


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_tenhou_asking_the_downloader_to_wait_stops_the_run_at_once(tenhou, log_store, download, status):
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B)
    tenhou.reply(tenhou.log_url(GAME_A), status, b"busy")
    tenhou.add_log(GAME_B, log(2))

    with pytest.raises(DownloadStopped, match=str(status)):
        download()

    assert tenhou.urls()[-1] == tenhou.log_url(GAME_A) and list(log_store.log_ids()) == []


def test_when_tenhou_says_how_long_to_wait_the_stop_says_so(tenhou, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A)
    tenhou.reply(tenhou.log_url(GAME_A), 429, headers={"retry-after": "600"})

    with pytest.raises(DownloadStopped, match="retry after 600"):
        download()


def test_an_interrupted_run_resumes_where_it_stopped(tenhou, clock, log_store, download):
    tenhou.add_list("scc2026110604.html.gz", GAME_A, GAME_B, GAME_C)
    for n, log_id in enumerate([GAME_A, GAME_B, GAME_C]):
        tenhou.add_log(log_id, log(n))
    tenhou.reply(tenhou.log_url(GAME_B), 503)
    with pytest.raises(DownloadStopped):
        download()
    tenhou.reply(tenhou.log_url(GAME_B), 200, log(1).encode())
    clock.advance(5 * MINUTE)
    tenhou.requests.clear()

    download()

    assert tenhou.urls() == [tenhou.log_url(GAME_B), tenhou.log_url(GAME_C)]
    assert list(log_store.log_ids()) == [GAME_A, GAME_B, GAME_C]
