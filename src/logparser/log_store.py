"""The log store: unparsed Tenhou logs, keyed by log ID.

It is a folder holding one `<logId>.xml` file per log, exactly as Tenhou
serves it. Logs are local data and are never committed.
"""

import re
from collections.abc import Iterator
from pathlib import Path

# YYYYMMDDHH + "gm" + game type (hex) + lobby + hash, e.g. 2012060420gm-0009-10011-acfd4b57, the example
# game in Tenhou's manual.
LOG_ID = re.compile(r"\d{10}gm-[0-9a-f]{4}-[0-9a-f]{4,5}-[0-9a-f]{8}")


class LogStore:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def add(self, log_id: str, xml_text: str) -> None:
        if not LOG_ID.fullmatch(log_id):
            raise ValueError(f"not a Tenhou log ID: {log_id!r}")
        self.folder.mkdir(parents=True, exist_ok=True)
        partial = self._path(log_id).with_suffix(".partial")
        partial.write_text(xml_text, encoding="utf-8")
        partial.replace(self._path(log_id))

    def add_file(self, path: Path) -> str:
        """Adds a log from a file named `<logId>.xml` and returns its log ID."""
        path = Path(path)
        self.add(path.stem, path.read_text(encoding="utf-8"))
        return path.stem

    def log_ids(self) -> Iterator[str]:
        if self.folder.exists():
            yield from sorted(path.stem for path in self.folder.glob("*.xml") if LOG_ID.fullmatch(path.stem))

    def __contains__(self, log_id: str) -> bool:
        return self._path(log_id).is_file()

    def read(self, log_id: str) -> str:
        return self._path(log_id).read_text(encoding="utf-8")

    def _path(self, log_id: str) -> Path:
        return self.folder / f"{log_id}.xml"
