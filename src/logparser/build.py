"""Which build of LogParser wrote a file, and when, as the ingest report and the manifest say it."""

from datetime import datetime, timezone
from importlib.metadata import version


def generator() -> str:
    """The LogParser package and its version."""
    return f"mahjong-logparser {version('mahjong-logparser')}"


def timestamp(moment: datetime) -> str:
    """`moment` in UTC to the second, e.g. 2026-01-02T03:04:05Z."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
