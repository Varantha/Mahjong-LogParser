# Mahjong - Process game logs

Repo to process Tenhou game logs. Idea is to export them for use in a seperate website which will be used to train scoring in Riichi. 

## V2

V2 lives in `src/logparser` and is run with [uv](https://docs.astral.sh/uv/):

```
uv sync
uv run logparser add-logs path/to/<logId>.xml ...   # fill the log store
uv run logparser ingest                             # log store -> hand store
uv run logparser export                             # hand store -> trainer bundle
uv run pytest
```

Local data lives under the git-ignored `local/` folder: `local/log-store/`, `local/hand-store.sqlite` and `local/bundle/`. Each command takes options to use other locations. No logs or other data are ever committed: Tenhou forbids redistributing its logs.

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