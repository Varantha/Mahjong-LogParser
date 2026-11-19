"""A hand's situation worked out from the game's moves, not from Tenhou's yaku list.

A round's moves are replayed one at a time. When a hand wins, the moves so far
say what situation it won in.

The live wall holds 70 tiles once the hands are dealt. Each kan moves one more
of them to the dead wall, and the player who made the kan draws their next tile
from the dead wall. Before that draw, another player can win on the tile added
to an added kan, which robs the kan (chankan). Tenhou lets no hand rob a closed
kan, not even kokushi musou, so a win on a closed kan's tile is bad data.

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

from dataclasses import dataclass

from logparser.calls import ADDED_KAN, KANS

LIVE_WALL = 70
DRAW, DISCARD, CALL = "draw", "discard", "call"
SITUATIONAL_YAKU = frozenset({"double-riichi", "ippatsu", "haitei", "houtei", "rinshan", "chankan", "tenhou", "chiihou"})
FIRST_DRAW_YAKU = frozenset({"tenhou", "chiihou"})


def situational_yaku(situation: dict) -> set[str]:
    """The situational yaku, as contract keys, that a hand in `situation` wins with."""
    won_with = {
        "double-riichi": situation["doubleRiichi"],
        "ippatsu": situation["ippatsu"],
        "haitei": situation["lastTile"] and situation["tsumo"],
        "houtei": situation["lastTile"] and not situation["tsumo"],
        "rinshan": situation["rinshan"],
        "chankan": situation["chankan"],
        "tenhou": situation["firstDraw"] and situation["dealer"],
        "chiihou": situation["firstDraw"] and not situation["dealer"],
    }
    return {key for key, won in won_with.items() if won}


@dataclass(frozen=True)
class Move:
    """A draw, a discard or a call: one of the moves a round is replayed from."""

    kind: str  # DRAW, DISCARD or CALL
    seat: int
    tile: int | None  # the tile drawn or discarded; for a call, the tile an added kan adds, else None
    call_type: str | None = None  # for a call, its type; None if its code is no four-player call


class RoundMoves:
    """What a round's moves have told us so far."""

    def __init__(self) -> None:
        self.unreadable_call = False  # a call code in the moves could not be read, so they can't be replayed
        self._last_move: Move | None = None
        self._draws = 0  # draws from the live wall
        self._kans = 0
        self._dead_wall_draw_due: int | None = None  # the seat whose next draw is from the dead wall
        self._last_draw_from_dead_wall = False
        self._robbable_kan_by: int | None = None  # the seat whose added kan was the last move
        self._called = False  # a call has been made this round, closed kans included
        self._discarded: set[int] = set()  # seats that have discarded this round
        self._riichi: set[int] = set()  # seats whose riichi was accepted
        self._double_riichi: set[int] = set()  # seats that declared riichi with their first discard
        self._ippatsu: set[int] = set()  # seats in their ippatsu window

    def play(self, move: Move) -> None:
        """Replays one more move. A call whose code could not be read can't be replayed: once the
        round has one, its situation can't be worked out."""
        self._last_move = move
        if move.kind == CALL and move.call_type is None:
            self.unreadable_call = True
            return
        self._next_move()
        if move.kind == DRAW:
            self._draw(move.seat)
        elif move.kind == DISCARD:
            self._discard(move.seat)
        else:
            self._call(move.seat, move.call_type)

    def _draw(self, seat: int) -> None:
        self._last_draw_from_dead_wall = seat == self._dead_wall_draw_due
        if self._last_draw_from_dead_wall:
            self._dead_wall_draw_due = None
        else:
            self._draws += 1

    def _discard(self, seat: int) -> None:
        self._discarded.add(seat)
        self._ippatsu.discard(seat)

    def _call(self, seat: int, call_type: str) -> None:
        self._called = True
        if call_type == ADDED_KAN:
            self._robbable_kan_by = seat
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
        if self._robbable_kan_by is not None:
            self._robbable_kan_by = None
            self._ippatsu.clear()

    def situation(self, *, winner: int, discarder: int) -> dict:
        """The situation flags of a win by `winner` now. `discarder` is the winner on a tsumo."""
        tsumo = winner == discarder
        rinshan = tsumo and self._last_draw_from_dead_wall
        chankan = not tsumo and self._robbable_kan_by == discarder
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

    def tile_handed_over(self, *, winner: int, discarder: int) -> int | None:
        """The tile the last move handed the winner, or None if it handed over none.

        On a tsumo that is the winner's own draw. On a ron it is the discarder's discard, or the
        tile the discarder added to a kan (robbing a kan). Both wins of a double ron are on the same
        discard: a win is no move.
        """
        move = self._last_move
        if move is None:
            return None
        if winner == discarder:
            handed_over = move.kind == DRAW and move.seat == winner
        else:
            handed_over = move.kind in (DISCARD, CALL) and move.seat == discarder
        return move.tile if handed_over else None
