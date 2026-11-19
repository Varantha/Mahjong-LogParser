"""The `logparser` command.

    logparser add-logs FILE...   add <logId>.xml files to the log store
    logparser import-dump DUMP   add the logs in a database dump to the log store
    logparser ingest             stage 1: log store -> hand store
    logparser export             stage 2: hand store -> trainer bundle

Local data lives under `local/` in the current folder by default (git ignores
it); every location can be overridden on the command line.
"""

import argparse
from pathlib import Path

from logparser.dump_import import import_dump
from logparser.export import CATALOGUE_PATH, DEFAULT_CHUNK_SIZE, export_bundle, load_catalogue
from logparser.hand_store import HandStore
from logparser.ingest import ingest
from logparser.log_store import LogStore

LOCAL = Path("local")
LOG_STORE = LOCAL / "log-store"
HAND_STORE = LOCAL / "hand-store.sqlite"
BUNDLE = LOCAL / "bundle"


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

    ingest_ = commands.add_parser("ingest", help="parse every win in the log store into the hand store")
    ingest_.add_argument("--log-store", type=Path, default=LOG_STORE)
    ingest_.add_argument("--hand-store", type=Path, default=HAND_STORE)
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


def _ingest(args) -> None:
    with HandStore(args.hand_store) as hands:
        summary = ingest(LogStore(args.log_store), hands)
    skipped = sum(summary.skipped.values())
    reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(summary.skipped.items()))
    print(
        f"{summary.logs} logs ({skipped} skipped{': ' + reasons if reasons else ''}), "
        f"{summary.hands} hands ({summary.hands - summary.quarantined} verified, {summary.quarantined} quarantined)"
    )


def _export(args) -> None:
    with HandStore(args.hand_store) as hands:
        manifest = export_bundle(hands, args.bundle, load_catalogue(args.catalogue),
                                 chunk_size=args.chunk_size, seed=args.seed)
    drills = ", ".join(f"{key} {count}" for key, count in manifest["counts"]["drills"].items())
    print(f"Wrote {manifest['counts']['hands']} hands in {len(manifest['chunks'])} chunks to {args.bundle} ({drills})")
