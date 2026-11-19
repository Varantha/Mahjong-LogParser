"""Reads the hands out of one Tenhou mjlog XML log.

Every win (AGARI) in a taken game becomes a hand record, a JSON-ready dict:

    id                 <logId>/<roundIndex>/<winIndex>
    replayUrl          Tenhou replay of the round from the winner's seat (hand store only)
    situation          winds, dealer, honba, riichi sticks, tsumo, riichi
    tiles              concealed tiles, calls, winning tile and dora indicators, in mpsz.
                       Each call is {type, tiles, calledTile, calledFrom}, in the order made.
    answerKey          Tenhou's recorded yaku (contract keys), han, fu, points and payments
    quarantineReasons  one reason code per failed check; empty when verified
    tags               the keys of the hand's tags (see `logparser.tags`)
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from logparser.calls import Call, decode_call
from logparser.payments import payments, score_changes
from logparser.situation import RoundMoves
from logparser.tags import hand_tags
from logparser.tiles import mpsz, tile
from logparser.verification import quarantine_reasons
from logparser.yaku import TENHOU_YAKU_KEYS, YAKUMAN_HAN

REPLAY_URL = "https://tenhou.net/0/?log={log_id}&ts={round_index}&tw={seat}"
WINDS = ("east", "south", "west", "north")

# Bits of the GO tag's `type` attribute.
NO_RED_FIVES = 0x02
NO_OPEN_TANYAO = 0x04
SANMA = 0x10

# Move tags: a letter for the seat (0-3), then a tile ID, e.g. <T84/> is seat 0 drawing tile 84.
DRAW_TAGS = "TUVW"
DISCARD_TAGS = "DEFG"
MOVE_TAG = re.compile(r"([TUVWDEFG])(\d+)")  # DORA also starts with D, so the whole tag must match
DRAW, DISCARD, CALL = "draw", "discard", "call"


@dataclass
class ParsedLog:
    hands: list[dict] = field(default_factory=list)
    skipped: str | None = None  # why the whole game was not taken: "sanma", "ruleset" or "malformed"


@dataclass(frozen=True)
class _Move:
    """A draw, a discard or a call (an N tag)."""

    kind: str
    seat: int
    tile: int | None  # the tile drawn or discarded; for a call, the tile an added kan adds, else None
    call_type: str | None = None  # for a call, its type; None if its code is no four-player call


@dataclass
class _Round:
    """What a round's moves have told us so far."""

    index: int
    number: int  # Tenhou's seed[0]: round wind * 4 + hand number - 1
    dealer: int
    wins: int = 0
    moves: RoundMoves = field(default_factory=RoundMoves)
    unreadable_call: bool = False  # a call code in the moves could not be read, so they can't be replayed
    last_move: _Move | None = None


def parse_log(log_id: str, xml_text: str) -> ParsedLog:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ParsedLog(skipped="malformed")
    parsed = ParsedLog()
    round_ = None
    for event in root:
        if event.tag == "GO":
            parsed.skipped = _skip_reason(int(event.get("type")))
            if parsed.skipped:
                return parsed
        elif event.tag == "INIT":
            round_ = _Round(
                index=0 if round_ is None else round_.index + 1,
                number=_ints(event.get("seed"))[0],
                dealer=int(event.get("oya")),
            )
        elif event.tag == "REACH":
            if event.get("step") == "1":
                round_.moves.declare_riichi(int(event.get("who")))
            elif event.get("step") == "2":
                round_.moves.accept_riichi(int(event.get("who")))
        elif event.tag == "AGARI":
            parsed.hands.append(_hand(log_id, round_, event))
            round_.wins += 1
        elif (move := _move(event)) is not None:
            round_.last_move = move
            _replay(round_, move)
    return parsed


def _move(event: ET.Element) -> _Move | None:
    """The move in a draw, discard or call tag; None for any other tag."""
    if event.tag == "N":
        seat = int(event.get("who"))
        try:
            call = decode_call(int(event.get("m")))
        except ValueError:
            return _Move(CALL, seat, None)
        return _Move(CALL, seat, call.added_tile, call.type)
    if match := MOVE_TAG.fullmatch(event.tag):
        letter, tile_id = match[1], int(match[2])
        if letter in DRAW_TAGS:
            return _Move(DRAW, DRAW_TAGS.index(letter), tile_id)
        return _Move(DISCARD, DISCARD_TAGS.index(letter), tile_id)
    return None


def _replay(round_: _Round, move: _Move) -> None:
    """Plays one more move into the round's moves."""
    if move.kind == DRAW:
        round_.moves.draw(move.seat)
    elif move.kind == DISCARD:
        round_.moves.discard(move.seat)
    elif move.call_type is None:
        round_.unreadable_call = True
    else:
        round_.moves.call(move.seat, move.call_type)


def _skip_reason(game_type: int) -> str | None:
    """Only 4-player games with open tanyao and red fives are taken, east-only or hanchan."""
    if game_type & SANMA:
        return "sanma"
    if game_type & (NO_RED_FIVES | NO_OPEN_TANYAO):
        return "ruleset"
    return None


def _hand(log_id: str, round_: _Round, agari: ET.Element) -> dict:
    winner = int(agari.get("who"))
    discarder = int(agari.get("fromWho"))
    honba, sticks = _ints(agari.get("ba"))
    tsumo = winner == discarder
    concealed = _ints(agari.get("hai"))
    calls = _calls(agari)
    winning_tile = int(agari.get("machi"))
    dora_indicators = _ints(agari.get("doraHai"))
    ura_dora_indicators = _ints(agari.get("doraHaiUra", ""))
    yaku = _recorded_yaku(agari)
    # In a double ron Tenhou pays the honba and the riichi sticks to the first winner only. The
    # second winner's `ba` still shows the honba, but its score change leaves them out.
    first_win = round_.wins == 0
    answer_key = _answer_key(agari, yaku, tsumo=tsumo, dealer=winner == round_.dealer,
                             honba=honba if first_win else 0, riichi_sticks=sticks if first_win else 0)
    situation = {
        "roundWind": WINDS[round_.number // 4],
        "seatWind": WINDS[(winner - round_.dealer) % 4],
        "dealer": winner == round_.dealer,
        "honba": honba,
        "riichiSticks": sticks,
        "tsumo": tsumo,
        **round_.moves.situation(winner=winner, discarder=discarder),
    }
    reasons = quarantine_reasons(
        concealed=concealed,
        calls=calls,
        unreadable_call_in_moves=round_.unreadable_call,
        winning_tile=winning_tile,
        tile_from_moves=_tile_handed_over(round_.last_move, winner=winner, discarder=discarder),
        dora_indicators=dora_indicators,
        ura_dora_indicators=ura_dora_indicators,
        situation=situation,
        yaku=[recorded["key"] for recorded in answer_key["yaku"]],
        unknown_yaku=[tenhou_id for tenhou_id, _ in yaku if tenhou_id not in TENHOU_YAKU_KEYS],
        recorded_score_changes=_recorded_score_changes(agari),
        expected_score_changes=score_changes(answer_key["payments"], winner=winner, discarder=discarder,
                                             dealer=round_.dealer),
    )
    hand = {
        "id": f"{log_id}/{round_.index}/{round_.wins}",
        "replayUrl": REPLAY_URL.format(log_id=log_id, round_index=round_.index, seat=winner),
        "situation": situation,
        "tiles": {
            "concealed": mpsz(concealed),
            "calls": [_call_record(call) for call in calls or []],
            "winningTile": tile(winning_tile),
            "doraIndicators": mpsz(dora_indicators),
            "uraDoraIndicators": mpsz(ura_dora_indicators),
        },
        "answerKey": answer_key,
        "quarantineReasons": reasons,
    }
    hand["tags"] = hand_tags(hand)
    return hand


def _tile_handed_over(move: _Move | None, *, winner: int, discarder: int) -> int | None:
    """The tile the round's last move handed the winner, or None if it handed over none.

    On a tsumo that is the winner's own draw. On a ron it is the discarder's discard, or the
    tile the discarder added to a kan (robbing a kan). Both wins of a double ron are on the same
    discard: a win is no move.
    """
    if move is None:
        return None
    if winner == discarder:
        handed_over = move.kind == DRAW and move.seat == winner
    else:
        handed_over = move.kind in (DISCARD, CALL) and move.seat == discarder
    return move.tile if handed_over else None


def _calls(agari: ET.Element) -> list[Call] | None:
    """The winner's calls in the order they were made (Tenhou lists them latest first), or None if one can't be read."""
    try:
        return [decode_call(code) for code in reversed(_ints(agari.get("m", "")))]
    except ValueError:
        return None


def _call_record(call: Call) -> dict:
    return {
        "type": call.type,
        "tiles": mpsz(call.tiles),
        "calledTile": None if call.called_tile is None else tile(call.called_tile),
        "calledFrom": call.called_from,
    }


def _recorded_yaku(agari: ET.Element) -> list[tuple[int, int]]:
    """Tenhou's (yaku ID, han) pairs. Yaku worth 0 han (Tenhou lists ura dora 0) are left out."""
    if agari.get("yakuman"):
        return [(tenhou_id, YAKUMAN_HAN) for tenhou_id in _ints(agari.get("yakuman"))]
    values = _ints(agari.get("yaku"))
    return [(tenhou_id, han) for tenhou_id, han in zip(values[::2], values[1::2]) if han > 0]


def _answer_key(agari: ET.Element, yaku: list[tuple[int, int]], *, tsumo: bool, dealer: bool,
                honba: int, riichi_sticks: int) -> dict:
    """Tenhou's recorded result, with yaku under their contract keys."""
    fu, points, _limit = _ints(agari.get("ten"))
    return {
        "yaku": [{"key": TENHOU_YAKU_KEYS[i], "han": han} for i, han in yaku if i in TENHOU_YAKU_KEYS],
        "han": sum(han for _, han in yaku),
        "fu": fu,
        "points": points,
        "payments": payments(points, tsumo=tsumo, dealer=dealer, honba=honba, riichi_sticks=riichi_sticks),
    }


def _recorded_score_changes(agari: ET.Element) -> list[int]:
    """Each seat's score change in points. `sc` holds a score and a change per seat, in hundreds."""
    return [change * 100 for change in _ints(agari.get("sc", ""))[1::2]]


def _ints(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v]
