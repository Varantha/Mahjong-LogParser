"""Dump import: database dumps that map a log ID to compressed log XML fill the log store.

A dump is V1's SQLite format: a table `logs(log_id, log_content)` holding
bz2-compressed log XML. Every dump here is built inside the test from
hand-written logs.
"""

import bz2
import sqlite3

import pytest

from logparser.dump_import import import_dump
from logparser.log_store import LogStore
from tenhou_xml import closed_win, game, init

LOG_A = "2024010112gm-00a9-0000-0123abcd"
LOG_B = "2024010113gm-00a1-0000-89abcdef"


def make_dump(path, rows):
    """Writes a dump holding `rows` of (log_id, log_content) as given."""
    with sqlite3.connect(path) as dump:
        dump.execute("CREATE TABLE logs(log_id TEXT PRIMARY KEY, log_content BLOB)")
        dump.executemany("INSERT INTO logs VALUES (?, ?)", rows)
    dump.close()
    return path


def compressed(xml_text):
    return bz2.compress(xml_text.encode("utf-8"))


def test_every_log_in_a_dump_is_kept_in_the_log_store_under_its_log_id(tmp_path):
    log_a, log_b = game(init(), closed_win(who=1)), game(init(round_number=1))
    dump = make_dump(tmp_path / "dump.db", [(LOG_A, compressed(log_a)), (LOG_B, compressed(log_b))])
    store = LogStore(tmp_path / "log-store")

    import_dump(dump, store)

    assert {log_id: store.read(log_id) for log_id in store.log_ids()} == {LOG_A: log_a, LOG_B: log_b}


def test_importing_the_same_dump_again_adds_nothing_and_keeps_one_copy_of_each_log(tmp_path):
    dump = make_dump(tmp_path / "dump.db", [(LOG_A, compressed(game(init()))), (LOG_B, compressed(game(init())))])
    store = LogStore(tmp_path / "log-store")
    first = import_dump(dump, store)

    again = import_dump(dump, store)

    assert ((first.added, first.already_stored), (again.added, again.already_stored), list(store.log_ids())) == (
        (2, 0), (0, 2), [LOG_A, LOG_B])


@pytest.mark.parametrize("bad_row, reason", [
    pytest.param((LOG_B, None), "no content", id="not-downloaded-yet"),
    pytest.param(("my-game", compressed(game(init()))), "not a log ID", id="not-a-log-id"),
    pytest.param((LOG_B, game(init()).encode("utf-8")), "unreadable content", id="not-bz2"),
])
def test_a_row_that_holds_no_usable_log_is_skipped_with_a_reason(tmp_path, bad_row, reason):
    dump = make_dump(tmp_path / "dump.db", [bad_row, (LOG_A, compressed(game(init())))])
    store = LogStore(tmp_path / "log-store")

    summary = import_dump(dump, store)

    assert (summary.added, summary.skipped, list(store.log_ids())) == (1, {reason: 1}, [LOG_A])


def test_a_dump_that_does_not_exist_is_refused_and_not_created(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing.db"):
        import_dump(tmp_path / "missing.db", LogStore(tmp_path / "log-store"))

    assert not (tmp_path / "missing.db").exists()
