"""The `logparser` command: add logs, ingest them, export the trainer bundle."""

import json

from logparser.cli import main
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
    assert manifest["drills"] == [{"key": "everything", "handIds": [f"{LOG_ID}/0/0"]}]


def test_every_location_can_be_given_on_the_command_line(tmp_path, no_network):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(), closed_win()))
    logs, hands, bundle = tmp_path / "logs", tmp_path / "hands.sqlite", tmp_path / "out"

    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])
    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands)])
    main(["export", "--hand-store", str(hands), "--bundle", str(bundle), "--chunk-size", "1", "--seed", "3"])

    manifest = json.loads((bundle / "manifest.json").read_text())
    assert (manifest["chunks"], manifest["build"]["seed"]) == (["hands-000.json"], 3)


def test_ingest_reports_what_it_did(tmp_path, capsys):
    (tmp_path / f"{LOG_ID}.xml").write_text(game(init(round_number=0), closed_win(who=1), init(round_number=1), short_win(who=2)))
    logs, hands = tmp_path / "logs", tmp_path / "hands.sqlite"
    main(["add-logs", "--log-store", str(logs), str(tmp_path / f"{LOG_ID}.xml")])

    main(["ingest", "--log-store", str(logs), "--hand-store", str(hands)])

    assert capsys.readouterr().out.splitlines()[-1] == "1 logs (0 skipped), 2 hands (1 verified, 1 quarantined)"
