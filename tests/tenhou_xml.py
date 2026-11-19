"""Builders for small, hand-written Tenhou mjlog XML documents.

Every log a committed test parses is assembled here from made-up moves and
made-up hands. Nothing in this module is copied from a real log.

Tile IDs follow Tenhou's 136-tile layout: 0-35 are 1m-9m (four copies each),
36-71 are 1p-9p, 72-107 are 1s-9s and 108-135 are East, South, West, North,
Haku, Hatsu, Chun. The first copy of each five (16, 52, 88) is the red five.
"""

import re

PHOENIX_HANCHAN = 0xA9  # 4-player, kuitan, aka, hanchan
PHOENIX_EAST_ONLY = 0xA1  # 4-player, kuitan, aka, east-only
SANMA_HANCHAN = 0xB9  # 3-player
NO_AKA_HANCHAN = 0xAB  # red fives off
NO_KUITAN_HANCHAN = 0xAD  # open tanyao off


def ids(*tile_ids: int) -> str:
    return ",".join(str(t) for t in tile_ids)


def go(game_type: int = PHOENIX_HANCHAN) -> str:
    return f'<GO type="{game_type}" lobby="0"/>'


def un(names=("Alice", "Bob", "Carol", "Dave")) -> str:
    n0, n1, n2, n3 = names
    return (
        f'<UN n0="{n0}" n1="{n1}" n2="{n2}" n3="{n3}" '
        'dan="16,16,16,16" rate="2000.00,2000.00,2000.00,2000.00" sx="M,M,M,M"/>'
    )


def init(round_number: int = 0, honba: int = 0, sticks: int = 0, oya: int | None = None,
         dora_indicator: int = 130) -> str:
    """A round start. By default the dealer is the seat whose turn it is in that wind."""
    oya = round_number % 4 if oya is None else oya
    seed = f"{round_number},{honba},{sticks},2,3,{dora_indicator}"
    hands = " ".join(f'hai{seat}="{ids(*range(seat * 13, seat * 13 + 13))}"' for seat in range(4))
    return f'<INIT seed="{seed}" ten="250,250,250,250" oya="{oya}" {hands}/>'


def agari(*, who: int, from_who: int, hai: str, machi: int, ten: str,
          yaku: str | None = None, yakuman: str | None = None, ba: str = "0,0",
          dora: str = "130", ura: str | None = None, m: str | None = None,
          sc: str | None = None, dealer: int = 0, winning_move: bool = True) -> str:
    """A win. Unless `sc` is given, the recorded score changes settle `ten` and `ba` in full,
    with `dealer` dealing (seat 0, as in the first round of `init`).

    Unless `winning_move` is False, the win comes straight after the move that hands over its
    winning tile: the winner's draw of `machi` on a tsumo, or the discarder's discard of it on a ron.
    """
    move = (draw(who, machi) if who == from_who else discard(from_who, machi)) if winning_move else ""
    if sc is None:
        sc = settlement(who=who, from_who=from_who, ten=ten, ba=ba, dealer=dealer)
    attrs = [f'ba="{ba}"', f'hai="{hai}"']
    if m is not None:
        attrs.append(f'm="{m}"')
    attrs += [f'machi="{machi}"', f'ten="{ten}"']
    if yaku is not None:
        attrs.append(f'yaku="{yaku}"')
    if yakuman is not None:
        attrs.append(f'yakuman="{yakuman}"')
    attrs.append(f'doraHai="{dora}"')
    if ura is not None:
        attrs.append(f'doraHaiUra="{ura}"')
    attrs += [f'who="{who}"', f'fromWho="{from_who}"', f'sc="{sc}"']
    return f"{move}<AGARI {' '.join(attrs)}/>"


def draw(seat: int, tile_id: int) -> str:
    """A draw: T, U, V or W for seats 0-3, then the tile ID."""
    return f"<{'TUVW'[seat]}{tile_id}/>"


def discard(seat: int, tile_id: int) -> str:
    """A discard: D, E, F or G for seats 0-3, then the tile ID."""
    return f"<{'DEFG'[seat]}{tile_id}/>"


def call(seat: int, code: int) -> str:
    """A call by `seat` (an N tag)."""
    return f'<N who="{seat}" m="{code}"/>'


def settlement(*, who: int, from_who: int, ten: str, ba: str, dealer: int) -> str:
    """Tenhou's `sc` for a win paid in full: each seat's score (all 25000) and change, in hundreds.

    The discarder pays a ron; on a tsumo each non-dealer pays a quarter of the points rounded
    up to 100 and the dealer pays the rest. Honba are 300 a hand and riichi sticks 1000 each.
    """
    points = int(ten.split(",")[1])
    honba, sticks = (int(v) for v in ba.split(","))
    changes = [0] * 4
    if who != from_who:
        changes[from_who] = -(points + 300 * honba)
    else:
        each_non_dealer = -(-points // 400) * 100
        for seat in set(range(4)) - {who}:
            if who == dealer:
                share = points // 3
            else:
                share = points - 2 * each_non_dealer if seat == dealer else each_non_dealer
            changes[seat] = -(share + 100 * honba)
    changes[who] = -sum(changes) + 1000 * sticks
    return ",".join(f"250,{change // 100}" for change in changes)


def turns(count: int, first_seat: int = 0, tile_id: int = 135) -> str:
    """`count` turns in seat order from `first_seat`, each a draw and a discard of the same made-up tile."""
    return "".join(draw(seat, tile_id) + discard(seat, tile_id)
                   for seat in ((first_seat + turn) % 4 for turn in range(count)))


def riichi(seat: int, tile_id: int = 135) -> str:
    """A riichi declared with a discard and accepted: Tenhou's REACH steps 1 and 2 around the discard."""
    return f'<REACH who="{seat}" step="1"/>{discard(seat, tile_id)}<REACH who="{seat}" step="2"/>'


def ryuukyoku() -> str:
    return '<RYUUKYOKU ba="0,0" sc="250,0,250,0,250,0,250,0"/>'


def game(*events: str, game_type: int = PHOENIX_HANCHAN) -> str:
    body = "".join(events)
    return f'<mjloggm ver="2.3">{go(game_type)}{un()}<TAIKYOKU oya="0"/>{body}</mjloggm>'


# A closed hand used across tests: 123m 456p 234s 789s and a pair of 9p.
# 1m 2m 3m = 0 4 8; 4p 5p 6p = 48 53 56; 9p 9p = 68 69; 2s 3s 4s = 76 80 84;
# 7s 8s 9s = 96 100 104.
CLOSED_HAND = ids(0, 4, 8, 48, 53, 56, 68, 69, 76, 80, 84, 96, 100, 104)


def closed_win(who: int = 1, from_who: int = 0) -> str:
    """CLOSED_HAND ron on 4s by a non-dealer: pinfu, 1 han 30 fu, 1000 points."""
    return agari(who=who, from_who=from_who, hai=CLOSED_HAND, machi=84, ten="30,1000,0", yaku="7,1")


def short_win(who: int = 1, from_who: int = 0) -> str:
    """A closed win with 13 tiles, CLOSED_HAND without its 1m: quarantined for its tile total."""
    hai = ids(4, 8, 48, 53, 56, 68, 69, 76, 80, 84, 96, 100, 104)
    return agari(who=who, from_who=from_who, hai=hai, machi=84, ten="30,1000,0", yaku="7,1")


# Where a called tile came from, relative to the caller (bits 0-1 of a call code).
SHIMOCHA, TOIMEN, KAMICHA = 1, 2, 3


def chi(tiles: tuple[int, int, int], called: int) -> int:
    """Tenhou's call code for a chi of three tile IDs in a run, calling `called` from kamicha."""
    tiles = tuple(sorted(tiles))
    suit, rank = divmod(tiles[0] // 4, 9)
    code = ((suit * 7 + rank) * 3 + tiles.index(called)) << 10 | 0b100 | KAMICHA
    for k, tile_id in enumerate(tiles):
        code |= tile_id % 4 << (3 + 2 * k)
    return code


def pon(tiles: tuple[int, int, int], called: int, from_seat: int) -> int:
    """Tenhou's call code for a pon of three copies of one kind."""
    tiles = tuple(sorted(tiles))
    (left_out,) = {0, 1, 2, 3} - {tile_id % 4 for tile_id in tiles}
    return ((tiles[0] // 4) * 3 + tiles.index(called)) << 9 | left_out << 5 | 0b1000 | from_seat


def added_kan(pon_tiles: tuple[int, int, int], called: int, from_seat: int) -> int:
    """Tenhou's call code for an added kan: the pon's code with bit 4 in place of bit 3."""
    return pon(pon_tiles, called, from_seat) ^ 0b11000


def open_kan(called: int, from_seat: int) -> int:
    return called << 8 | from_seat


def closed_kan(tile_id: int) -> int:
    return tile_id // 4 * 4 << 8


def m(*codes_in_call_order: int) -> str:
    """AGARI's `m` attribute: Tenhou lists the winner's calls latest first."""
    return ids(*reversed(codes_in_call_order))


# CALLED_HAND: a chi of 3m 4m red-5m calling the red 5m (8 12 16), then a pon of Chun
# from toimen (132 133 134). Concealed: 4p 5p 6p = 48 53 56; 9p 9p = 68 69;
# 2s 3s 4s = 76 80 84.
CALLED_HAND_CALLS = m(chi((8, 12, 16), called=16), pon((132, 133, 134), called=133, from_seat=TOIMEN))
CALLED_HAND = ids(48, 53, 56, 68, 69, 76, 80, 84)


def called_win(who: int = 1, from_who: int = 0) -> str:
    """CALLED_HAND ron on 4s by a non-dealer: chun and aka dora, 2 han 30 fu, 2000 points.

    The dora indicator is West (116), so North is dora and the hand holds none.
    """
    return agari(who=who, from_who=from_who, hai=CALLED_HAND, m=CALLED_HAND_CALLS, machi=84,
                 ten="30,2000,0", yaku="20,1,54,1", dora="116")


class Wall:
    """Hands out tile IDs for tiles written in mpsz, never the same ID twice, so a hand built
    from it holds each physical tile once. A 5 is a copy other than the red five; a 0 is the
    red five."""

    def __init__(self) -> None:
        self._taken: set[int] = set()

    def take(self, tiles: str) -> tuple[int, ...]:
        taken = []
        for ranks, suit in re.findall(r"([0-9]+)([mpsz])", tiles):
            for rank in ranks:
                kind = "mpsz".index(suit) * 9 + (int(rank) or 5) - 1
                copies = (0,) if rank == "0" else (1, 2, 3) if rank == "5" and suit != "z" else (0, 1, 2, 3)
                tile_id = next(kind * 4 + copy for copy in copies if kind * 4 + copy not in self._taken)
                self._taken.add(tile_id)
                taken.append(tile_id)
        return tuple(taken)


def win(wall: Wall, *, concealed: str, winning: str, ten: str, yaku: str | None = None, yakuman: str | None = None,
        calls: tuple[int, ...] = (), who: int = 1, tsumo: bool = False, dora: str = "1z",
        ura: str | None = None) -> str:
    """A win by `who` on `winning`, with `concealed` the rest of its concealed tiles. A ron is on
    the discard of the seat before. Tiles are in mpsz and come from `wall`, as do the tiles of
    `calls` (call codes, in the order made). The dora indicator is East unless given."""
    winning_tile = wall.take(winning)[0]
    return agari(who=who, from_who=who if tsumo else (who - 1) % 4, hai=ids(*wall.take(concealed), winning_tile),
                 m=m(*calls) if calls else None, machi=winning_tile, ten=ten, yaku=yaku, yakuman=yakuman,
                 dora=ids(*wall.take(dora)), ura=None if ura is None else ids(*wall.take(ura)))
