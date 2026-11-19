"""Stage 1: ingest parses every win in the log store into the hand store."""

from logparser.hand_store import HandStore
from logparser.ingest import IngestSummary, ingest
from logparser.log_store import LogStore
from tenhou_xml import SANMA_HANCHAN, called_win, closed_win, game, init, short_win

PHOENIX_LOG = "2024010112gm-00a9-0000-0123abcd"
SANMA_LOG = "2024010113gm-00b9-0000-4567cdef"


def test_ingest_turns_every_win_of_a_taken_game_into_a_hand(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(who=1), init(round_number=1), called_win(who=2)))
    logs.add(SANMA_LOG, game(init(), closed_win(), game_type=SANMA_HANCHAN))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)

        assert sorted(hands.hand_ids()) == [f"{PHOENIX_LOG}/0/0", f"{PHOENIX_LOG}/1/0"]


def test_the_hand_store_keeps_each_hand_as_parsed_including_quarantined_hands(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        verified = hands.get(f"{PHOENIX_LOG}/0/0")
        quarantined = hands.get(f"{PHOENIX_LOG}/1/0")

    assert (verified["tiles"]["concealed"], verified["quarantineReasons"]) == ("123m45699p234789s", [])
    assert quarantined["quarantineReasons"] == ["tile-total"]


def test_ingesting_again_gives_the_same_hands_without_duplicates(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(who=1), init(round_number=1), closed_win(who=2)))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        first = {hand_id: hands.get(hand_id) for hand_id in hands.hand_ids()}
        ingest(logs, hands)
        second = {hand_id: hands.get(hand_id) for hand_id in hands.hand_ids()}

    assert second == first


def test_ingest_summarises_logs_skipped_hands_parsed_and_hands_quarantined(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))
    logs.add(SANMA_LOG, game(init(), closed_win(), game_type=SANMA_HANCHAN))
    logs.add("2024010114gm-00a9-0000-89abcdef", "<mjloggm><GO type=")  # cut off mid-download

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        summary = ingest(logs, hands)

    assert summary == IngestSummary(logs=3, skipped={"sanma": 1, "malformed": 1}, hands=2, quarantined=1)
