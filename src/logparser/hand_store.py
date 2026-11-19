"""The hand store: every hand parsed from the log store, verified or quarantined.

It is a single SQLite file. Each hand is kept as its JSON record, keyed by
hand ID, next to the log it came from and whether it is verified. It is local
data and is never committed.
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS hands (
    id TEXT PRIMARY KEY,
    log_id TEXT NOT NULL,
    verified INTEGER NOT NULL,
    record TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS hands_by_log ON hands (log_id);
"""


class HandStore:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def __enter__(self) -> "HandStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def replace_log(self, log_id: str, hands: Iterable[dict]) -> None:
        """Replaces every hand from one log, so a re-run never leaves stale hands behind."""
        with self._db:
            self._db.execute("DELETE FROM hands WHERE log_id = ?", (log_id,))
            self._db.executemany(
                "INSERT INTO hands (id, log_id, verified, record) VALUES (?, ?, ?, ?)",
                [(hand["id"], log_id, not hand["quarantineReasons"], json.dumps(hand)) for hand in hands],
            )

    def hand_ids(self) -> Iterator[str]:
        for (hand_id,) in self._db.execute("SELECT id FROM hands ORDER BY id"):
            yield hand_id

    def get(self, hand_id: str) -> dict:
        row = self._db.execute("SELECT record FROM hands WHERE id = ?", (hand_id,)).fetchone()
        if row is None:
            raise KeyError(hand_id)
        return json.loads(row[0])

    def verified_hand_ids(self) -> Iterator[str]:
        for (hand_id,) in self._db.execute("SELECT id FROM hands WHERE verified ORDER BY id"):
            yield hand_id
