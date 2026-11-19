"""The log store: unparsed Tenhou logs on local disk, keyed by log ID."""

import pytest

from logparser.log_store import LogStore
from tenhou_xml import game, init

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def test_a_log_added_from_an_xml_file_is_kept_under_its_log_id(tmp_path):
    source = tmp_path / f"{LOG_ID}.xml"
    source.write_text(game(init()))
    store = LogStore(tmp_path / "log-store")

    store.add_file(source)

    assert (list(store.log_ids()), store.read(LOG_ID)) == ([LOG_ID], game(init()))


def test_adding_the_same_log_twice_keeps_one_copy(tmp_path):
    source = tmp_path / f"{LOG_ID}.xml"
    source.write_text(game(init()))
    store = LogStore(tmp_path / "log-store")

    store.add_file(source)
    store.add_file(source)

    assert list(store.log_ids()) == [LOG_ID]


def test_a_file_not_named_after_a_log_id_is_refused(tmp_path):
    source = tmp_path / "my-game.xml"
    source.write_text(game(init()))

    with pytest.raises(ValueError, match="log ID"):
        LogStore(tmp_path / "log-store").add_file(source)
