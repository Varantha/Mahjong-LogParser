# Mahjong - Process game logs

Repo to process Tenhou game logs. Idea is to export them for use in a seperate website which will be used to train scoring in Riichi. 

## V2

V2 lives in `src/logparser` and is run with [uv](https://docs.astral.sh/uv/):

```
uv sync
uv run logparser add-logs path/to/<logId>.xml ...   # fill the log store
uv run logparser import-dump path/to/dump.db        # or fill it from a database dump
uv run logparser download                           # or fill it from Tenhou's Phoenix-room lists
uv run logparser ingest                             # log store -> hand store
uv run logparser export                             # hand store -> trainer bundle
uv run pytest
```

Local data lives under the git-ignored `local/` folder: `local/log-store/`, `local/downloader.sqlite`, `local/hand-store.sqlite` and `local/bundle/`. Each command takes options to use other locations. No logs or other data are ever committed: Tenhou forbids redistributing its logs.

- `download` is the only command that uses the network. It follows Tenhou's rules for automatic downloads (https://tenhou.net/sc/raw/): one request at a time, 2 s apart by default (`--interval`); the FileIndex at most every 20 minutes; an scc list again only when its size has changed. It skips logs the log store already holds and games ingest would skip (sanma, other rulesets), stops when Tenhou asks it to wait, and carries on where it stopped when run again. `--max-logs` caps a run.
- The trainer bundle's contract is the JSON Schema in `src/logparser/schema/trainer-bundle.schema.json`.
- The drill catalogue is `src/logparser/drills.toml`.
- Real-log test fixtures live in `local/fixtures/` (or set `LOGPARSER_FIXTURES`); see `tests/test_fixtures.py`. Without them those tests are skipped.

## thanks to 
```
Euophrys
https://github.com/Euophrys/

ApplySci
https://github.com/ApplySci

Nihisil
https://github.com/MahjongRepository/mahjong

NegativeMjark
https://github.com/NegativeMjark/
```