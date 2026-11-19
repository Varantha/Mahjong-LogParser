"""Stage 1: ingest parses every win in the log store into the hand store."""

import json
from datetime import datetime, timezone

from logparser.hand_store import HandStore
from logparser.ingest import IngestResult, ingest
from logparser.log_store import LogStore
from logparser.tags import TAGS
from tenhou_xml import SANMA_HANCHAN, agari, called_win, chi, closed_win, game, ids, init, m, ryuukyoku, short_win

PHOENIX_LOG = "2024010112gm-00a9-0000-0123abcd"
SANMA_LOG = "2024010113gm-00b9-0000-4567cdef"
OTHER_LOG = "2024010114gm-00a9-0000-89abcdef"


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


def test_ingest_counts_the_logs_skipped_the_hands_parsed_and_the_hands_quarantined(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))
    logs.add(SANMA_LOG, game(init(), closed_win(), game_type=SANMA_HANCHAN))
    logs.add("2024010114gm-00a9-0000-89abcdef", "<mjloggm><GO type=")  # cut off mid-download

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        result = ingest(logs, hands)

    assert result == IngestResult(logs=3, skipped={"sanma": 1, "malformed": 1}, hands=2, quarantined=1)


# The ingest report: what one ingest found, and a diff against the previous run.


def open_honitsu(sc: str | None = None) -> str:
    """Seat 1 rons off the dealer, seat 0, with a chi of 123m and 567m 78m+9m 444z 33z concealed:
    honitsu, worth 2 han rather than 3 because the hand is open (kuisagari); 30 fu, 2000 points.
    A made-up `sc` that doesn't settle the points quarantines it for its payments."""
    return agari(who=1, from_who=0, m=m(chi((0, 4, 8), called=0)), hai=ids(17, 20, 24, 25, 28, 32, 116, 117, 120, 121, 122),
                 machi=32, ten="30,2000,0", yaku="34,2", sc=sc)


def report(result: IngestResult) -> dict:
    return json.loads((result.report_folder / "report.json").read_text(encoding="utf-8"))


def test_the_report_gives_the_hands_parsed_and_the_quarantined_hands_grouped_by_reason(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), short_win(),
                               init(round_number=2, oya=0), open_honitsu(sc="250,-10,250,10,250,0,250,0")))
    logs.add(SANMA_LOG, game(init(), closed_win(), game_type=SANMA_HANCHAN))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        result = ingest(logs, hands, tmp_path / "reports")

    assert report(result)["logs"] == {"read": 2, "skipped": {"sanma": 1}}
    assert report(result)["hands"] == {"parsed": 3, "verified": 1, "quarantined": 2, "changed": 0, "removed": 0}
    assert report(result)["quarantined"] == {"payments": [f"{PHOENIX_LOG}/2/0"], "tile-total": [f"{PHOENIX_LOG}/1/0"]}


def test_the_report_counts_the_verified_hands_with_each_tag_listing_every_tag(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), open_honitsu(), init(round_number=1, oya=0), closed_win(),
                               init(round_number=2, oya=0), open_honitsu(sc="250,-10,250,10,250,0,250,0")))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        result = ingest(logs, hands, tmp_path / "reports")

    tags = report(result)["verified"]["tags"]
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
        result = ingest(logs, hands, tmp_path / "reports")

    assert report(result)["verified"]["limitTiers"] == {
        "none": 1, "mangan": 1, "haneman": 0, "baiman": 0, "sanbaiman": 0, "kazoe-yakuman": 0, "yakuman": 0}


def diff(result: IngestResult) -> list[dict]:
    lines = (result.report_folder / "diff.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_the_first_run_writes_a_report_and_an_empty_diff(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), short_win()))

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        result = ingest(logs, hands, tmp_path / "reports")

    assert report(result)["hands"]["parsed"] == 2
    assert diff(result) == []


def test_each_run_writes_its_report_into_a_folder_of_its_own_named_after_the_time_it_ran(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(), closed_win()))
    noon = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        first = ingest(logs, hands, tmp_path / "reports", ingested_at=noon)
        second = ingest(logs, hands, tmp_path / "reports", ingested_at=noon)

    assert (first.report_folder.parent, first.report_folder.name) == (tmp_path / "reports", "20240101T120000Z")
    assert second.report_folder.name.startswith("20240101T120000Z") and second.report_folder != first.report_folder
    assert report(first)["ingestedAt"] == report(second)["ingestedAt"] == "2024-01-01T12:00:00Z"


def test_the_diff_lists_by_hand_id_the_hands_that_changed_since_the_previous_run(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), closed_win()))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands, tmp_path / "reports")
        # The log's first win changes. Its second win doesn't, and a log added since then holds only new hands.
        logs.add(PHOENIX_LOG, game(init(round_number=0), open_honitsu(), init(round_number=1, oya=0), closed_win()))
        logs.add(OTHER_LOG, game(init(), closed_win()))

        result = ingest(logs, hands, tmp_path / "reports")

    assert [change["id"] for change in diff(result)] == [f"{PHOENIX_LOG}/0/0"]
    # The pinfu ron has no tags: its fu are fixed, so they never sit on a knife edge.
    assert diff(result)[0]["tags"] == {"added": ["kuisagari"], "removed": []}
    assert result.changed == report(result)["hands"]["changed"] == 1


def test_the_diff_lists_a_hand_a_log_no_longer_gives_as_removed(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), closed_win()))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands, tmp_path / "reports")
        # The log's second round no longer gives a hand, as after a parser change.
        logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), ryuukyoku()))

        result = ingest(logs, hands, tmp_path / "reports")
        stored = [hand["id"] for hand in hands.log_hands(PHOENIX_LOG)]

    assert diff(result) == [{"id": f"{PHOENIX_LOG}/1/0", "removed": True}]
    assert result.removed == report(result)["hands"]["removed"] == 1
    assert stored == [f"{PHOENIX_LOG}/0/0"]


def test_hands_whose_log_has_left_the_log_store_are_dropped_and_listed_as_removed(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(round_number=0), closed_win(), init(round_number=1, oya=0), short_win()))
    logs.add(OTHER_LOG, game(init(), closed_win()))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands, tmp_path / "reports")
        (tmp_path / "log-store" / f"{PHOENIX_LOG}.xml").unlink()

        result = ingest(logs, hands, tmp_path / "reports")
        left = ([hand["id"] for hand in hands.log_hands(PHOENIX_LOG)], [hand["id"] for hand in hands.verified_hands()])

    assert diff(result) == [{"id": f"{PHOENIX_LOG}/0/0", "removed": True}, {"id": f"{PHOENIX_LOG}/1/0", "removed": True}]
    assert result.removed == report(result)["hands"]["removed"] == 2
    assert left == ([], [f"{OTHER_LOG}/0/0"])


def test_the_diff_gives_each_changed_value_of_the_answer_key_and_plain_values_before_and_after(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(), closed_win()))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        # The hand as an older parser stored it: it read the fu as 40 and knew no dora count.
        older = hands.get(f"{PHOENIX_LOG}/0/0")
        older["answerKey"]["fu"] = older["plainValues"]["fu"] = 40
        del older["plainValues"]["doraCount"]
        hands.replace_log(PHOENIX_LOG, [older])

        result = ingest(logs, hands, tmp_path / "reports")

    assert diff(result) == [{
        "id": f"{PHOENIX_LOG}/0/0",
        "answerKey": {"fu": {"before": 40, "after": 30}},
        "plainValues": {"fu": {"before": 40, "after": 30}, "doraCount": {"before": None, "after": 0}},
    }]


def test_the_diff_takes_hands_stored_before_plain_values_and_tags_existed_as_having_none(tmp_path):
    logs = LogStore(tmp_path / "log-store")
    logs.add(PHOENIX_LOG, game(init(), open_honitsu()))
    with HandStore(tmp_path / "hand-store.sqlite") as hands:
        ingest(logs, hands)
        older = hands.get(f"{PHOENIX_LOG}/0/0")
        del older["plainValues"], older["tags"]
        hands.replace_log(PHOENIX_LOG, [older])

        result = ingest(logs, hands, tmp_path / "reports")

    [change] = diff(result)
    assert "answerKey" not in change
    assert (change["plainValues"]["han"], change["plainValues"]["open"]) == ({"before": None, "after": 2},
                                                                            {"before": None, "after": True})
    assert change["tags"] == {"added": ["kuisagari"], "removed": []}
