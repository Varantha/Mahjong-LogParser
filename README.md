# Mahjong Log Parser

Turns Tenhou game logs into verified, tagged hands, and builds from them the trainer bundle: the practice questions the Scoring Trainer, a separate website for learning to score riichi mahjong, ships.

This repo holds only the logic: the code, the tests and the trainer bundle's schema. No logs or other data are ever committed: Tenhou forbids redistributing its logs. Everything the pipeline reads and writes is built locally.

Terms such as *hand*, *answer key*, *quarantined hand* and *tag* are defined in [GLOSSARY.md](GLOSSARY.md). Decisions that need context are recorded in [docs/adr](docs/adr).

## How it works

```
Tenhou scc lists ─── download ──────┐
Database dumps ───── import-dump ───┼─► Log store ──(stage 1: ingest)──► Hand store ──(stage 2: export)──► Trainer bundle
<logId>.xml files ── add-logs ──────┘
```

**Log store.** The unparsed Tenhou logs, one `<logId>.xml` file per game, exactly as Tenhou serves it. A log ID such as `2012060420gm-0009-10011-acfd4b57` names one game, and Tenhou's replay viewer plays it at `https://tenhou.net/0/?log=<logId>`. That ID is the example game in Tenhou's manual, and its [replay link](https://tenhou.net/0/?log=2012060420gm-0009-10011-acfd4b57) still plays. Three commands fill the log store: `download` fetches Phoenix-room games from Tenhou, `import-dump` reads an existing database dump, and `add-logs` adds log files you already have.

**Stage 1: ingest** parses every win in the log store into a hand and keeps it in the hand store. Only 4-player games with open tanyao and red fives are taken; sanma and other rulesets are skipped. Each hand records:

- its ID, `<logId>/<roundIndex>/<winIndex>`, which depends only on the source log, so re-running ingest never changes it
- its tiles and calls, in `mpsz` notation
- its situation (winds, dealer, honba, riichi sticks, tsumo or ron, riichi, ippatsu, last tile, rinshan, chankan, first draw), worked out from the game's moves
- its answer key: the yaku, han, fu, limit tier, points and payments Tenhou recorded, plus the raw fu and the fu breakdown once the cross-check (below) has matched
- its plain values, the facts drills filter on directly: han, fu, raw fu, limit tier, dealer, tsumo or ron, open or closed, yaku, dora count, honba, riichi sticks and call types
- its tags, such as `kuisagari`
- a link to the round in Tenhou's replay viewer, for debugging

Every hand then goes through these checks:

1. **Tile total.** The concealed and called tiles come to 14, plus one per kan.
2. **Tile limits.** No tile appears more than 4 times, and there is at most one red five per suit.
3. **Winning tile.** The winning tile is the one actually drawn or discarded.
4. **Situation.** The situation worked out from the moves agrees with the situational yaku Tenhou gave.
5. **Payments.** The score changes Tenhou recorded match the points, honba and riichi sticks.
6. **Cross-check.** The [`mahjong`](https://github.com/MahjongRepository/mahjong) library, set to Tenhou rules, recalculates the hand and must match the answer key exactly: yaku, han, fu, limit tier and points.

A hand that fails any check is quarantined: it stays in the hand store with a reason code per failed check and never reaches the trainer bundle.

**Stage 2: export** builds the trainer bundle from the verified hands. Each drill in the drill catalogue ([`src/logparser/drills.toml`](src/logparser/drills.toml)) draws its hands from the hand store, and the bundle stores every hand once: a `manifest.json` plus chunk files of hands. The bundle's contract is the JSON Schema in [`src/logparser/schema/trainer-bundle.schema.json`](src/logparser/schema/trainer-bundle.schema.json). It never holds player names, replay links or quarantined hands.

Only `download` uses the network. Ingest and export read and write local files only.

## Running it

Install [uv](https://docs.astral.sh/uv/), then set up the project from the repo root:

```
uv sync
```

Every command runs as `uv run logparser COMMAND`, and `uv run logparser COMMAND --help` lists its options.

### Fill the log store

From Tenhou:

```
uv run logparser download
```

The downloader reads Tenhou's FileIndex and the `scc` lists of Phoenix-room games it names, then fetches every listed log the log store lacks. It skips games that ingest would skip (sanma, other rulesets). It follows Tenhou's rules for automatic downloads (https://tenhou.net/sc/raw/): one request at a time, the FileIndex at most every 20 minutes, and an scc list again only when its size has changed. Requests start 2 s apart by default; `--interval` changes that, and `--max-logs` caps how many logs one run fetches. It stops when Tenhou asks it to wait, and running it again carries on where it stopped.

From a database dump:

```
uv run logparser import-dump path/to/dump.db
```

A dump is an SQLite file with a table `logs(log_id, log_content)` holding each log's XML, bz2-compressed. Other columns are ignored and the dump is never changed. Logs the log store already holds are left as they are, and a row that holds no usable log is skipped with a reason.

From log files:

```
uv run logparser add-logs path/to/<logId>.xml ...
```

Each file must be named after its log ID.

### Stage 1: ingest

```
uv run logparser ingest
```

Parses every log in the log store and prints how many logs were skipped and why, and how many hands are verified and quarantined. Running it again replaces each log's hands, so a parser fix reaches every hand already stored.

### Stage 2: export

```
uv run logparser export
```

Writes the trainer bundle, replacing any bundle already in its folder. `--catalogue` uses another drill catalogue, `--chunk-size` sets how many hands go in each chunk file, and `--seed` changes how hands are drawn at random.

### Where data lives

By default everything lives under `local/` in the current folder, which git ignores. Each location can be changed on the command line:

| Data | Default | Option |
|---|---|---|
| Log store | `local/log-store/` | `--log-store` |
| Downloader state | `local/downloader.sqlite` | `--state` |
| Hand store | `local/hand-store.sqlite` | `--hand-store` |
| Trainer bundle | `local/bundle/` | `--bundle` |

## Tests

```
uv run pytest
```

Committed tests use only inputs built by hand, never copied from a log. Tests against real logs use fixtures kept in `local/fixtures/` (or the folder `LOGPARSER_FIXTURES` names): see [`tests/test_fixtures.py`](tests/test_fixtures.py) for their layout. Without fixtures those tests are skipped.

## Thanks to
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
