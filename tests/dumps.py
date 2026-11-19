"""Builds small database dumps in V1's format for tests.

A dump is an SQLite file with a table `logs(log_id, log_content)` holding
bz2-compressed log XML. The logs put in one come from `tenhou_xml`, so nothing
here is copied from a real log or dump.
"""

import bz2
import sqlite3


def make_dump(path, rows):
    """Writes a dump holding `rows` of (log_id, log_content) as given and returns its path."""
    with sqlite3.connect(path) as dump:
        dump.execute("CREATE TABLE logs(log_id TEXT PRIMARY KEY, log_content BLOB)")
        dump.executemany("INSERT INTO logs VALUES (?, ?)", rows)
    dump.close()
    return path


def compressed(xml_text):
    return bz2.compress(xml_text.encode("utf-8"))
