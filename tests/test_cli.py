"""The `logparser` command: add logs, ingest them, export the trainer bundle."""

import json

import pytest

from dumps import compressed, make_dump
from fake_tenhou import FILE_INDEXES, FakeClock, FakeTenhou
from logparser.cli import main
from logparser.hand_store import HandStore
from logparser.log_store import LogStore
from tenhou_xml import closed_win, game, init, short_win

LOG_ID = "2024010112gm-00a9-0000-0123abcd"


def test_logs_go_from_xml_files_to_a_trainer_bundle_under_local_without_the_network(tmp_path, monkeypatch, no_network):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / f"{LOG_ID}.xml").write_text(game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))
    monkeypatch.chdir(tmp_path)

    main(["add-logs", str(downloads / f"{LOG_ID}.xml")])
    main(["ingest"])
    main(["export"])

    manifest = json.loads((tmp_path / "local" / "bundle" / "manifest.json").read_text())
    assert {drill["key"]: drill["handIds"] for drill in manifest["drills"]}["everything"] == [f"{LOG_ID}/0/0"]


def test_every_location_can_be_given_on_the_command_line(tmp_path, no_network):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))
    logs, hands, reports, bundle = tmp_path / "logs", tmp_path / "hands.sqlite", tmp_path / "reports", tmp_path / "out"

    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])
    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands), "--reports", str(reports)])
    main(["export", "--hand-store", str(hands), "--bundle", str(bundle), "--chunk-size", "1", "--seed", "3"])

    manifest = json.loads((bundle / "manifest.json").read_text())
    assert (manifest["chunks"], manifest["build"]["seed"]) == (["hands-000.json"], 3)
    [report_folder] = reports.iterdir()
    assert (report_folder / "report.json").is_file()


def test_export_says_which_drills_fall_short_by_how_much_and_which_part_of_a_drill_ran_out(tmp_path, capsys):
    # One verified hand: a closed pinfu ron, so a lookalike in the drills below but not a trap hand.
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))
    logs, hands, catalogue = tmp_path / "logs", tmp_path / "hands.sqlite", tmp_path / "drills.toml"
    catalogue.write_text("""
        [[drill]]
        key = "everything"
        target = 1

        [[drill]]
        key = "payments"
        target = 3
        pool = { tsumo = true }

        [[drill]]
        key = "open-pinfu"
        target = 4
        pool = { yaku = "pinfu" }
        trap = { open = true }

        [[drill]]
        key = "made-up"
        target = 1
        trap = { open = true }
    """)
    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])
    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands), "--reports", str(tmp_path / "reports")])

    main(["export", "--hand-store", str(hands), "--bundle", str(tmp_path / "out"), "--catalogue", str(catalogue)])

    assert capsys.readouterr().out.splitlines()[-5:] == [
        f"Wrote 1 hands in 1 chunks to {tmp_path / 'out'} (everything 1, payments 0, open-pinfu 1, made-up 1)",
        "Short of hands, even drawing on every year of logs in the hand store:",
        "  payments: 0 of 3 hands, 3 short",
        "  open-pinfu: 1 of 4 hands, 3 short (trap hands: 0 of 2; lookalikes: 1 of 2)",
        "  made-up: 1 of 1 hands, made up from its other parts (trap hands: 0 of 1)",
    ]


def test_ingest_reports_what_it_did(tmp_path, capsys):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))
    logs, hands, reports = tmp_path / "logs", tmp_path / "hands.sqlite", tmp_path / "reports"
    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])

    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands), "--reports", str(reports)])

    [report_folder] = reports.iterdir()
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "1 logs (0 skipped), 2 hands (1 verified, 1 quarantined)",
        f"Wrote the ingest report to {report_folder} (0 hands changed and 0 removed since the previous run)",
    ]


def test_ingest_of_a_log_store_without_logs_stops_with_an_error_and_leaves_the_hand_store_alone(tmp_path):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))
    logs, hands = tmp_path / "logs", tmp_path / "hands.sqlite"
    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])
    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands), "--reports", str(tmp_path / "reports")])

    with pytest.raises(SystemExit, match="no logs") as stopped:
        main(["ingest", "--log-store", str(tmp_path / "typo"), "--hand-store", str(hands),
              "--reports", str(tmp_path / "reports")])

    assert stopped.value.code not in (0, None)
    with HandStore(hands) as store:
        assert store.get(f"{LOG_ID}/0/0")["quarantineReasons"] == []


def test_ingest_writes_its_report_and_diff_under_local(tmp_path, monkeypatch, no_network):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))
    monkeypatch.chdir(tmp_path)
    main(["add-logs", f"{LOG_ID}.xml"])

    main(["ingest"])
    main(["ingest"])

    report_folders = sorted((tmp_path / "local" / "ingest-reports").iterdir())
    assert len(report_folders) == 2
    assert all(sorted(path.name for path in folder.iterdir()) == ["diff.jsonl", "report.json"] for folder in report_folders)


@pytest.mark.parametrize(("options", "tagged"), [([], False), (["--high-fu", "30"], True)], ids=["default", "set-to-30"])
def test_ingest_tags_hands_with_the_high_fu_threshold_given(tmp_path, options, tagged):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))  # 30 fu
    logs, hands = tmp_path / "logs", tmp_path / "hands.sqlite"
    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])

    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands), "--reports", str(tmp_path / "reports"),
          *options])

    with HandStore(hands) as store:
        assert ("high-fu" in store.get(f"{LOG_ID}/0/0")["tags"]) == tagged


def test_a_dump_is_imported_into_the_log_store_under_local_and_ingested_without_the_network(tmp_path, monkeypatch, capsys,
                                                                                            no_network):
    make_dump(tmp_path / "dump.db", [(LOG_ID, compressed(game(init(), closed_win())))])
    monkeypatch.chdir(tmp_path)

    main(["import-dump", "dump.db"])
    main(["ingest"])

    assert capsys.readouterr().out.splitlines()[-2] == "1 logs (0 skipped), 1 hands (1 verified, 0 quarantined)"


def test_importing_a_dump_reports_what_it_added_kept_and_skipped(tmp_path, capsys):
    dump = make_dump(tmp_path / "dump.db", [(LOG_ID, compressed(game(init()))), ("my-game", compressed(game(init())))])
    logs = tmp_path / "logs"
    main(["import-dump", "--log-store", str(logs), str(dump)])

    main(["import-dump", "--log-store", str(logs), str(dump)])

    assert capsys.readouterr().out.splitlines() == [
        f"Added 1 logs to {logs} (0 already stored, 1 skipped: 1 not a log ID)",
        f"Added 0 logs to {logs} (1 already stored, 1 skipped: 1 not a log ID)",
    ]


@pytest.fixture
def tenhou(monkeypatch, no_network):
    """A fake Tenhou in place of the downloader's HTTP client."""
    fake = FakeTenhou(FakeClock())
    monkeypatch.setattr("logparser.downloader.urllib_get", fake)
    return fake


def test_logs_are_downloaded_into_the_log_store_under_local_and_ingested(tmp_path, monkeypatch, capsys, tenhou):
    tenhou.add_list("scc2024010112.html.gz", LOG_ID)
    tenhou.add_log(LOG_ID, game(init(), closed_win()))
    monkeypatch.chdir(tmp_path)

    main(["download", "--interval", "0"])
    main(["ingest"])

    assert capsys.readouterr().out.splitlines()[:2] == [
        "Read 1 scc lists; fetched 1 logs (0 failed); 0 left to fetch",
        "1 logs (0 skipped), 1 hands (1 verified, 0 quarantined)",
    ]
    assert (tmp_path / "local" / "downloader.sqlite").is_file()


def test_a_download_can_be_limited_and_given_other_locations(tmp_path, capsys, tenhou):
    other = "2024010112gm-00a9-0000-0123abce"
    tenhou.add_list("scc2024010112.html.gz", LOG_ID, other)
    tenhou.add_log(LOG_ID, game(init(), closed_win()))
    logs, state = tmp_path / "logs", tmp_path / "state.sqlite"

    main(["download", "--log-store", str(logs), "--state", str(state), "--interval", "0", "--max-logs", "1"])

    assert capsys.readouterr().out == "Read 1 scc lists; fetched 1 logs (0 failed); 1 left to fetch\n"
    assert list(LogStore(logs).log_ids()) == [LOG_ID] and state.is_file()


def test_the_logs_in_an_id_list_are_downloaded_and_lines_that_are_not_log_ids_are_reported(tmp_path, capsys, tenhou):
    stored, sanma = "2024010112gm-00a9-0000-0123abce", "2024010112gm-00b9-0000-0123abcf"
    tenhou.add_log(LOG_ID, game(init(), closed_win()))
    logs, ids = tmp_path / "logs", tmp_path / "ids.txt"
    LogStore(logs).add(stored, game(init(), closed_win()))
    ids.write_text(f"{LOG_ID}\n\n{stored}\nmy game\n{sanma}\n")

    main(["download", "--ids", str(ids), "--log-store", str(logs), "--state", str(tmp_path / "state.sqlite"),
          "--interval", "0"])

    out, err = capsys.readouterr()
    assert err == f"{ids}:4: not a log ID: 'my game'\n"
    assert out == "Fetched 1 logs (0 failed); 1 already stored, 2 skipped: 1 not a log ID, 1 sanma; 0 left to fetch\n"
    assert tenhou.urls() == [tenhou.log_url(LOG_ID)]


def test_a_download_from_an_id_list_that_cannot_be_read_stops_with_an_error(tmp_path, tenhou):
    with pytest.raises(SystemExit, match="ID list") as stopped:
        main(["download", "--ids", str(tmp_path / "missing.txt"), "--state", str(tmp_path / "state.sqlite"),
              "--log-store", str(tmp_path / "logs")])

    assert stopped.value.code not in (0, None)


def test_a_stopped_download_says_why_and_that_it_can_be_run_again(tmp_path, tenhou):
    tenhou.reply(FILE_INDEXES[0], 503, headers={"retry-after": "600"})

    with pytest.raises(SystemExit, match="503.*retry after 600.*[Rr]un it again"):
        main(["download", "--state", str(tmp_path / "state.sqlite"), "--log-store", str(tmp_path / "logs")])
