"""The `logparser` command.

    logparser add-logs FILE...   add <logId>.xml files to the log store
    logparser import-dump DUMP   add the logs in a database dump to the log store
    logparser download           fetch Phoenix-room logs from Tenhou into the log store
    logparser ingest             stage 1: log store -> hand store, plus an ingest report
    logparser export             stage 2: hand store -> trainer bundle

Local data lives under `local/` in the current folder by default (git ignores
it); every location can be overridden on the command line. Only `download`
uses the network.
"""

import argparse
from pathlib import Path

from logparser.downloader import DEFAULT_INTERVAL, Downloader, DownloadStopped
from logparser.drills import CATALOGUE_PATH, load_catalogue
from logparser.dump_import import import_dump
from logparser.export import DEFAULT_CHUNK_SIZE, export_bundle
from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore
from logparser.tags import TagSettings

LOCAL = Path("local")
LOG_STORE = LOCAL / "log-store"
HAND_STORE = LOCAL / "hand-store.sqlite"
INGEST_REPORTS = LOCAL / "ingest-reports"
BUNDLE = LOCAL / "bundle"
DOWNLOADER_STATE = LOCAL / "downloader.sqlite"


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    args.run(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logparser", description="Turns Tenhou logs into the trainer bundle.")
    commands = parser.add_subparsers(required=True, metavar="COMMAND")

    add_logs = commands.add_parser("add-logs", help="add Tenhou XML logs, named <logId>.xml, to the log store")
    add_logs.add_argument("files", nargs="+", type=Path, metavar="FILE")
    add_logs.add_argument("--log-store", type=Path, default=LOG_STORE)
    add_logs.set_defaults(run=_add_logs)

    import_dump_ = commands.add_parser(
        "import-dump", help="add the logs in a database dump (SQLite logs(log_id, log_content), bz2) to the log store")
    import_dump_.add_argument("dump", type=Path, metavar="DUMP")
    import_dump_.add_argument("--log-store", type=Path, default=LOG_STORE)
    import_dump_.set_defaults(run=_import_dump)

    download = commands.add_parser(
        "download", help="fetch the Phoenix-room logs in Tenhou's scc lists into the log store (uses the network)",
        description="Fetches the logs of the 4-player Phoenix-room games in Tenhou's scc lists that the log store "
                    "lacks, one request at a time. Stopping and running it again carries on where it stopped.")
    download.add_argument("--log-store", type=Path, default=LOG_STORE)
    download.add_argument("--state", type=Path, default=DOWNLOADER_STATE,
                          help="where the downloader keeps the lists it has read, to resume and to skip unchanged lists")
    download.add_argument("--interval", type=_seconds, default=DEFAULT_INTERVAL,
                          help=f"seconds between the starts of two requests (default {DEFAULT_INTERVAL:g})")
    download.add_argument("--max-logs", type=int, help="fetch at most this many logs, leaving the rest for later")
    download.set_defaults(run=_download)

    ingest_ = commands.add_parser("ingest", help="parse every win in the log store into the hand store")
    ingest_.add_argument("--log-store", type=Path, default=LOG_STORE)
    ingest_.add_argument("--hand-store", type=Path, default=HAND_STORE)
    ingest_.add_argument("--reports", type=Path, default=INGEST_REPORTS,
                         help="folder each ingest writes its report and diff into, in a folder named after the time it ran")
    ingest_.add_argument("--high-fu", type=int, default=TagSettings.high_fu, metavar="FU",
                         help=f"the fewest fu after rounding a hand tagged high-fu has, at 4 han or fewer "
                              f"(default {TagSettings.high_fu})")
    ingest_.set_defaults(run=_ingest)

    export = commands.add_parser("export", help="build the trainer bundle from the verified hands")
    export.add_argument("--hand-store", type=Path, default=HAND_STORE)
    export.add_argument("--bundle", type=Path, default=BUNDLE, help="folder the bundle is written to")
    export.add_argument("--catalogue", type=Path, default=CATALOGUE_PATH, help="drill catalogue (TOML)")
    export.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="hands per chunk file")
    export.add_argument("--seed", type=int, default=0, help="seed for drawing hands at random")
    export.set_defaults(run=_export)
    return parser


def _add_logs(args) -> None:
    store = LogStore(args.log_store)
    for path in args.files:
        store.add_file(path)
    print(f"Added {len(args.files)} logs to {args.log_store}")


def _import_dump(args) -> None:
    summary = import_dump(args.dump, LogStore(args.log_store))
    skipped = sum(summary.skipped.values())
    reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(summary.skipped.items()))
    print(
        f"Added {summary.added} logs to {args.log_store} "
        f"({summary.already_stored} already stored, {skipped} skipped{': ' + reasons if reasons else ''})"
    )


def _download(args) -> None:
    try:
        with Downloader(LogStore(args.log_store), args.state, interval=args.interval) as downloader:
            summary = downloader.run(max_logs=args.max_logs)
    except DownloadStopped as stopped:
        raise SystemExit(f"Download stopped: {stopped}. Run it again later to carry on.") from stopped
    print(f"Read {summary.lists_read} scc lists; fetched {summary.fetched} logs ({summary.failed} failed); "
          f"{summary.remaining} left to fetch")


def _seconds(value: str) -> float:
    seconds = float(value)
    if seconds < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return seconds


def _ingest(args) -> None:
    with HandStore(args.hand_store) as hands:
        summary = ingest(LogStore(args.log_store), hands, args.reports, tag_settings=TagSettings(high_fu=args.high_fu))
    skipped = sum(summary.skipped.values())
    reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(summary.skipped.items()))
    print(
        f"{summary.logs} logs ({skipped} skipped{': ' + reasons if reasons else ''}), "
        f"{summary.hands} hands ({summary.hands - summary.quarantined} verified, {summary.quarantined} quarantined)"
    )
    print(f"Wrote the ingest report to {summary.report_folder} "
          f"({summary.changed} hands changed and {summary.removed} removed since the previous run)")


def _export(args) -> None:
    with HandStore(args.hand_store) as hands:
        summary = export_bundle(hands, args.bundle, load_catalogue(args.catalogue),
                                chunk_size=args.chunk_size, seed=args.seed)
    manifest = summary.manifest
    drills = ", ".join(f"{key} {count}" for key, count in manifest["counts"]["drills"].items())
    print(f"Wrote {manifest['counts']['hands']} hands in {len(manifest['chunks'])} chunks to {args.bundle} ({drills})")
    if summary.drills_with_a_short_part:
        print("Short of hands, even drawing on every year of logs in the hand store:")
    for drill in summary.drills_with_a_short_part:
        # A short drill drawn in one part is short by that part alone; otherwise name the parts that ran out.
        parts = "; ".join(f"{short.part}: {short.found} of {short.wanted}"
                          for short in drill.shortfalls if not (drill.short_by and short.wanted == drill.target))
        how_short = f"{drill.short_by} short" if drill.short_by else "made up from its other parts"
        print(f"  {drill.key}: {len(drill.hand_ids)} of {drill.target} hands, {how_short}"
              + (f" ({parts})" if parts else ""))
