"""A hand's situation worked out from the game's moves, not from Tenhou's yaku list.

A round's moves are replayed one at a time. When a hand wins, the moves so far
say what situation it won in.

The live wall holds 70 tiles once the hands are dealt. Each kan moves one more
of them to the dead wall, and the player who made the kan draws their next tile
from the dead wall. Before that draw, the tile added to an added kan can be won
on, which robs the kan (chankan).

Tenhou logs a riichi in two steps: the declaration, before its discard, and
the acceptance once nobody wins on that discard. A riichi that is declared
with the player's first discard of the round, before any call (closed kans
included), is a double riichi.

A tsumo on the player's first draw of the round, before any call (closed kans
included), is on the first draw: tenhou for the dealer, chiihou for the others.

The ippatsu window opens when a riichi is accepted. It closes at the player's
next discard, or at any call by anyone, closed kans included. An added kan
closes it only after the chance to rob the kan has passed.
"""

from logparser.calls import ADDED_KAN, KANS

LIVE_WALL = 70


class RoundMoves:
    """What a round's moves have told us so far."""

    def __init__(self) -> None:
        self._draws = 0  # draws from the live wall
        self._kans = 0
        self._dead_wall_draw_due: int | None = None  # the seat whose next draw is from the dead wall
        self._last_draw_from_dead_wall = False
        self._added_kan_robbable = False  # the last move added a tile to a kan
        self._called = False  # a call has been made this round, closed kans included
        self._discarded: set[int] = set()  # seats that have discarded this round
        self._riichi: set[int] = set()  # seats whose riichi was accepted
        self._double_riichi: set[int] = set()  # seats that declared riichi with their first discard
        self._ippatsu: set[int] = set()  # seats in their ippatsu window

    def draw(self, seat: int) -> None:
        self._next_move()
        self._last_draw_from_dead_wall = seat == self._dead_wall_draw_due
        if self._last_draw_from_dead_wall:
            self._dead_wall_draw_due = None
        else:
            self._draws += 1

    def discard(self, seat: int) -> None:
        self._next_move()
        self._discarded.add(seat)
        self._ippatsu.discard(seat)

    def call(self, seat: int, call_type: str) -> None:
        self._next_move()
        self._called = True
        if call_type == ADDED_KAN:
            self._added_kan_robbable = True
        else:
            self._ippatsu.clear()
        if call_type in KANS:
            self._kans += 1
            self._dead_wall_draw_due = seat

    def declare_riichi(self, seat: int) -> None:
        if seat not in self._discarded and not self._called:
            self._double_riichi.add(seat)

    def accept_riichi(self, seat: int) -> None:
        self._riichi.add(seat)
        self._ippatsu.add(seat)

    def _next_move(self) -> None:
        """Nobody robbed the last added kan, so it closes every ippatsu window now."""
        if self._added_kan_robbable:
            self._added_kan_robbable = False
            self._ippatsu.clear()

    def situation(self, *, winner: int, tsumo: bool) -> dict:
        """The situation flags of a win by `winner` now."""
        rinshan = tsumo and self._last_draw_from_dead_wall
        chankan = not tsumo and self._added_kan_robbable
        riichi = winner in self._riichi
        return {
            "riichi": riichi,
            "doubleRiichi": riichi and winner in self._double_riichi,
            "ippatsu": winner in self._ippatsu,
            # The last tile is a draw from the live wall, or the discard after it.
            "lastTile": self._draws + self._kans == LIVE_WALL and not (rinshan or chankan),
            "rinshan": rinshan,
            "chankan": chankan,
            "firstDraw": tsumo and winner not in self._discarded and not self._called,
        }
