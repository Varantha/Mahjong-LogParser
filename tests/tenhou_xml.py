"""Builders for small, hand-written Tenhou mjlog XML documents.

Every log a committed test parses is assembled here from made-up moves and
made-up hands. Nothing in this module is copied from a real log.

Tile IDs follow Tenhou's 136-tile layout: 0-35 are 1m-9m (four copies each),
36-71 are 1p-9p, 72-107 are 1s-9s and 108-135 are East, South, West, North,
Haku, Hatsu, Chun. The first copy of each five (16, 52, 88) is the red five.
"""

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
          sc: str = "250,0,250,0,250,0,250,0") -> str:
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
    return f"<AGARI {' '.join(attrs)}/>"


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


def called_win(who: int = 1, from_who: int = 0) -> str:
    """A win with calls (made-up call codes): quarantined until calls are decoded."""
    hai = ids(0, 4, 8, 48, 53, 56, 108, 109)
    return agari(who=who, from_who=from_who, hai=hai, m="40426,52279", machi=56, ten="30,1000,0", yaku="8,1")
