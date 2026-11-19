"""Stage 1: ingest parses every win in the log store into the hand store."""

import json

from logparser.hand_store import HandStore
from logparser.ingest import IngestSummary, ingest
from logparser.log_store import LogStore
from logparser.tags import TAGS
from tenhou_xml import SANMA_HANCHAN, agari, called_win, chi, closed_win, game, ids, init, m, short_win

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


# The ingest report: what one ingest found, and a diff against the previous run.


def open_honitsu(sc: str | None = None) -> str:
    """Seat 1 rons off the dealer, seat 0, with a chi of 123m and 567m 78m+9m 444z 33z concealed:
    honitsu, worth 2 han rather than 3 because the hand is open (kuisagari); 30 fu, 2000 points.
    A made-up `sc` that doesn't settle the points quarantines it for its payments."""
    return agari(who=1, from_who=0, m=m(chi((0, 4, 8), called=0)), hai=ids(17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
                 machi=32, ten="30,2000,0", yaku="34,2", sc=sc)


def report(summary: IngestSummary) -> dict:
    return json.loads((summary.report_folder / "report.json").read_text(encoding="utf-8"))


def test_the_report_gives_the_hands_parsed_and_the_quarantined_hands_grouped_by_reason(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), short_win(),
                               init(round_number=2, oya=0), open_honitsu(sc="250,-10,250,10,250,0,250,0")))
    logs.add(SANMA_LOG, game(init(), closed_win(), game_type=SANMA_HANCHAN))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        summary = ingest(logs, hands, tmp_path / "reports")

    assert report(summary)["logs"] == {"read": 2, "skipped": {"sanma": 1}}
    assert report(summary)["hands"] == {"parsed": 3, "verified": 1, "quarantined": 2}
    assert report(summary)["quarantined"] == {"payments": [f"{PHOENIX_LOG}/2/0"], "tile-total": [f"{PHOENIX_LOG}/1/0"]}


def test_the_report_counts_the_verified_hands_with_each_tag_listing_every_tag(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), open_honitsu(), init(round_number=1, oya=0), closed_win(),
                               init(round_number=2, oya=0), open_honitsu(sc="250,-10,250,10,250,0,250,0")))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        summary = ingest(logs, hands, tmp_path / "reports")

    tags = report(summary)["verified"]["tags"]
    assert (tags["kuisagari"], tags["wraparound-dora"]) == (1, 0)  # the quarantined kuisagari hand isn't counted
    assert set(tags) == set(TAGS)


def test_the_report_counts_the_verified_hands_at_each_limit_tier(tmp_path):
    # Seat 1 rons off seat 0 with a chi of 123m and 345m 67m+8m 999m 22m concealed: chinitsu, 5 han, mangan.
    open_chinitsu = agari(who=1, from_who=0, m=m(chi((0, 4, 8), called=0)), hai=ids(5, 6, 9, 12, 17, 20, 24, 28, 32, 33, 34),
                          machi=28, ten="30,8000,1", yaku="35,5")
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), open_chinitsu, init(round_number=1, oya=0), closed_win(),
                               init(round_number=2, oya=0), short_win()))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        summary = ingest(logs, hands, tmp_path / "reports")

    assert report(summary)["verified"]["limitTiers"] == {
        "none": 1, "mangan": 1, "haneman": 0, "baiman": 0, "sanbaiman": 0, "kazoe-yakuman": 0, "yakuman": 0}
