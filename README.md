# Mahjong Log Parser

Turns Tenhou game logs into verified, tagged hands, and builds from them the trainer bundle: the practice questions the Scoring Trainer, a separate website for learning to score riichi mahjong, ships.

This repo holds only the logic: the code, the tests and the trainer bundle's schema. No logs or other data are ever committed: Tenhou forbids redistributing its logs. Everything the pipeline reads and writes is built locally.

Terms such as *hand*, *answer key*, *quarantined hand* and *tag* are defined in [GLOSSARY.md](GLOSSARY.md). Decisions that need context are recorded in [docs/adr](docs/adr).

## How it works

```
Tenhou scc lists ─── download ──────┐
Log ID lists ─────── download --ids ┤
Database dumps ───── import-dump ───┼─► Log store ──(stage 1: ingest)──► Hand store ──(stage 2: export)──► Trainer bundle
<logId>.xml files ── add-logs ──────┘
```

**Log store.** The unparsed Tenhou logs, one `<logId>.xml` file per game, exactly as Tenhou serves it. A log ID such as `2012060420gm-0009-10011-acfd4b57` names one game, and Tenhou's replay viewer plays it at `https://tenhou.net/0/?log=<logId>`. That ID is the example game in Tenhou's manual, and its [replay link](https://tenhou.net/0/?log=2012060420gm-0009-10011-acfd4b57) still plays. Three commands fill the log store: `download` fetches Phoenix-room games from Tenhou, or the games a list of log IDs names, `import-dump` reads an existing database dump, and `add-logs` adds log files you already have.

**Stage 1: ingest** parses every win in the log store into a hand and keeps it in the hand store. Only 4-player games with open tanyao and red fives are taken; sanma and other rulesets are skipped. Each hand records:

- its ID, `<logId>/<roundIndex>/<winIndex>`, which depends only on the source log, so re-running ingest never changes it
- its tiles and calls, in `mpsz` notation, with each call also as its call string, such as `c423p` (below)
- its situation (winds, dealer, honba, riichi sticks, tsumo or ron, riichi, ippatsu, last tile, rinshan, chankan, first draw), worked out from the game's moves, and whether it is the second winner of a double ron, which collects none of the honba and riichi sticks on the table
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

**Stage 2: export** builds the trainer bundle from the verified hands. Each drill in the drill catalogue ([`src/logparser/drills.toml`](src/logparser/drills.toml)) draws its hands by searching the whole hand store, and the bundle stores every hand once, even when it is in several drills: a `manifest.json` plus chunk files of hands. The manifest lists each drill's key with the IDs of its hands and the chunks that hold them, and counts hands per drill, tag and limit tier. The hands lie in the order of the first drill that holds them, as the catalogue lists its drills: a drill's hands fill few chunks and the first drill's fill the first ones, so the trainer can deal a drill's first hand before every chunk has arrived. The bundle's contract is the JSON Schema in [`src/logparser/schema/trainer-bundle.schema.json`](src/logparser/schema/trainer-bundle.schema.json). It never holds player names, replay links or quarantined hands.

The trainer leaves out double riichi, haitei, houtei, rinshan, chankan, tenhou and chiihou. A hand won in one of those situations stays in the hand store and never reaches the bundle, so a bundle hand's situation gives only its winds, dealer, honba, riichi sticks, second winner, tsumo or ron, riichi and ippatsu.

In the bundle each call is its call string: the call's tiles as they lie on the table, left to right, then the suit.

| Call string | Call |
|---|---|
| `c423p` | Chi of 234p, calling the 4p |
| `c555p`, `5c55p`, `55c5p` | Pon of 5p from the player on the left (kamicha), across (toimen), on the right (shimocha) |
| `c1111z`, `1c111z`, `111c1z` | Open kan of East from the left, across, the right |
| `c5c055p` | Added kan: the 5p called from the left, the red 5p added to it |
| `f505f5m` | Closed kan of 5m |

`c` goes before a turned tile: the called tile, and for an added kan the added tile, which follows it. The turned tile's place says whose discard it was. `f` goes before a face-down tile, the two outer tiles of a closed kan; its red five lies second so that it shows.

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

The downloader reads Tenhou's FileIndex and the `scc` lists of Phoenix-room games it names, then fetches every listed log the log store lacks. It skips games that ingest would skip (sanma, other rulesets). It follows Tenhou's rules for automatic downloads (https://tenhou.net/sc/raw/): one request at a time, the FileIndex at most every 20 minutes, and an scc list again only when its size has changed. Requests start 2 s apart by default; `--interval` changes that, and `--max-logs` caps how many logs one run fetches. It stops when Tenhou asks it to wait, and running it again carries on where it stopped. While it runs it prints a timestamped progress line to stderr every 500 logs, such as `2026-11-20 03:15:02 1500/175480 done: 1500 fetched, 0 failed`.

From a list of log IDs:

```
uv run logparser download --ids local/log-ids.txt
```

`--ids FILE` fetches the logs a file names, one log ID per line, instead of reading the scc lists. Blank lines and spaces around an ID are ignored; a line that is not a log ID is reported with its line number and skipped. The logs are fetched in log ID order, oldest game first, and the same logs are skipped as above: those the log store already holds, games ingest would skip, and logs Tenhou could not give in an earlier run. Everything else works as above too: one request at a time, `--interval` and `--max-logs`, the same downloader state and lock, so it never runs alongside another download, and stopping when Tenhou asks it to wait.

Keep an ID list under `local/`, which git ignores, and never commit one: a list of log IDs is an index of Tenhou's logs, and Tenhou doesn't allow redistributing those.

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

Parses every log in the log store and prints how many logs were skipped and why, and how many hands are verified and quarantined. Running it again replaces each log's hands, so a parser fix reaches every hand already stored. The hand store holds only hands parsed from logs still in the log store: the hands of a log that has left it are dropped. A missing or empty log store would drop every hand, so ingest refuses it with an error and changes nothing.

Every ingest also writes an ingest report, in a folder of its own named after the time it ran, under `local/ingest-reports/` (`--reports` picks another folder):

- `report.json`: the logs read and skipped; the hands parsed, verified, quarantined, changed and removed; the IDs of the quarantined hands, by reason code; and how many verified hands have each tag and reach each limit tier.
- `diff.jsonl`: one line per hand whose answer key, plain values or tags changed since the previous run, by hand ID, with each changed value before and after and the tags added and removed. It also lists each hand removed since the previous run, `{"id": ..., "removed": true}`: a hand its log no longer gives, after a parser or filter change, or whose log has left the log store. The previous run is what the hand store held, so the first run's diff is empty, and hands from logs new to the log store are not listed.

A report shows how often each tag and limit tier occurs. After a parser change, the diff shows which hands it changed and how.

`--high-fu` sets the fewest fu, after rounding, that a hand tagged `high-fu` has (default 50). Only hands with 4 han or fewer get the tag: from 5 han a hand is mangan or more whatever its fu. The threshold is still being tuned against a year of logs: re-running ingest with another value retags every hand, the report counts the hands tagged at that value, and the diff lists the hands that gained or lost the tag.

### Stage 2: export

```
uv run logparser export
```

Writes the trainer bundle, replacing any bundle already in its folder. A hand store ingested before calls had call strings is refused: run ingest again first. `--catalogue` uses another drill catalogue, `--chunk-size` sets how many hands go in each chunk file, and `--seed` changes how hands are drawn at random.

The drill catalogue is configuration: adding or retuning a drill means editing [`drills.toml`](src/logparser/drills.toml) and exporting again, with no code changes. Its format is described at the top of that file. Each drill names:

- its **pool**, the hands it may take, as conditions on plain values and tags (`pool = { tsumo = true }`, `pool = { limitTier = ["sanbaiman", "yakuman"] }`, `pool = { tags = "kuisagari" }`). With no pool it takes any hand, at real-game frequency.
- its **target**, how many hands it aims for.
- optionally a **trap**, with a share of **lookalikes** (about half unless set): pool hands without the trap, so the drill doesn't give the answer away. A tag that gives the answer away, `open-pinfu-shape` (the fu) or `fu-mangan` (the points), can only be a trap, in a drill with lookalikes; export refuses a catalogue that uses it any other way.
- or optionally **quotas**, shares of the drill kept for rarer pool hands so they appear more often than in real games.

The catalogue holds every drill in the drill table, each aiming for 1,000 hands:

| Drill | Pool | Mixed in |
|---|---|---|
| `everything` | Any hand, at real-game frequency | |
| `fu-rounding-edge` | `knife-edge-fu` | |
| `tricky-waits` | `ambiguous-wait` | |
| `high-fu` | `high-fu` | |
| `open-hand-fu` | Open hands with 1–4 han | About half `open-pinfu-shape`, half lookalikes |
| `mangan-or-not` | Hands with 3–4 han | About half `fu-mangan`, half lookalikes |
| `open-hand-han` | Hands with sanshoku, ittsu, chanta, junchan, honitsu or chinitsu | About half open, half closed lookalikes |
| `hidden-dora` | Hands holding dora named by the dora indicators | About half `wraparound-dora`, half lookalikes |
| `big-hands` | Haneman and above | A fifth sanbaiman, kazoe yakuman or yakuman |
| `tsumo-payments` | Tsumo hands | |
| `ron-payments` | Ron hands | |

A drill draws on the newest year of logs first and reaches back a year at a time only while it is short. A drill is never shrunk to fit. When every year in the hand store together still leaves one part of a drill short, such as its quota of sanbaiman and above, the drill's other parts make up the difference, newest year first. A drill falls short of its target only when its whole pool does. Export lists each drill with a part that ran out after the summary line, with how many hands the drill has and how many each short part found. For example, on a small hand store:

```
Short of hands, even drawing on every year of logs in the hand store:
  big-hands: 1000 of 1000 hands, made up from its other parts (limitTier = sanbaiman/kazoe-yakuman/yakuman: 160 of 200)
  high-fu: 960 of 1000 hands, 40 short
```

The rare parts need the logs of many games: sanbaiman and above are about 1 in 1,200 hands. A year of Phoenix games, about 200,000 of them, should leave no part of a drill short.

### Where data lives

By default everything lives under `local/` in the current folder, which git ignores. Each location can be changed on the command line:

| Data | Default | Option |
|---|---|---|
| Log store | `local/log-store/` | `--log-store` |
| Downloader state | `local/downloader.sqlite` | `--state` |
| Hand store | `local/hand-store.sqlite` | `--hand-store` |
| Ingest reports | `local/ingest-reports/` | `--reports` |
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
