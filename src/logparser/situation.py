"""A hand's situation worked out from the game's moves, not from Tenhou's yaku list.

A round's moves are replayed one at a time. When a hand wins, the moves so far
say what situation it won in.

The live wall holds 70 tiles once the hands are dealt. Each kan moves one more
of them to the dead wall, and the player who made the kan draws their next tile
from the dead wall.
"""

from logparser.calls import KANS

LIVE_WALL = 70


class RoundMoves:
    """What a round's moves have told us so far."""

    def __init__(self) -> None:
        self._draws = 0  # draws from the live wall
        self._kans = 0
        self._dead_wall_draw_due: int | None = None  # the seat whose next draw is from the dead wall
        self._last_draw_from_dead_wall = False

    def draw(self, seat: int) -> None:
        self._last_draw_from_dead_wall = seat == self._dead_wall_draw_due
        if self._last_draw_from_dead_wall:
            self._dead_wall_draw_due = None
        else:
            self._draws += 1

    def call(self, seat: int, call_type: str) -> None:
        if call_type in KANS:
            self._kans += 1
            self._dead_wall_draw_due = seat

    def situation(self, *, winner: int, tsumo: bool) -> dict:
        """The situation flags of a win by `winner` now."""
        rinshan = tsumo and self._last_draw_from_dead_wall
        return {
            "lastTile": self._draws + self._kans == LIVE_WALL and not rinshan,
            "rinshan": rinshan,
        }
