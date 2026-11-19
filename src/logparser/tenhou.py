"""Reads the hands out of one Tenhou mjlog XML log.

Every win (AGARI) in a taken game becomes a hand record, a JSON-ready dict:

    id                 <logId>/<roundIndex>/<winIndex>
    replayUrl          Tenhou replay of the round from the winner's seat (hand store only)
    situation          winds, dealer, honba, riichi sticks, the second winner of a double ron and
                       tsumo, plus riichi, double riichi,
                       ippatsu, last tile, rinshan, chankan and first draw, worked out from the
                       round's moves (see `logparser.situation`)
    tiles              concealed tiles, calls, winning tile and dora indicators, in mpsz.
                       Each call is {type, tiles, calledTile, calledFrom}, in the order made.
    answerKey          Tenhou's recorded yaku (contract keys), han, fu, limit tier, points and
                       payments, plus the raw fu and fu breakdown (contract keys) of a hand whose
                       cross-check matched; both are None for any other hand
    splitFu            the fu of each way of splitting the hand into sets and a pair that has a yaku,
                       ascending, for a hand whose cross-check matched; None for any other (hand
                       store only)
    quarantineReasons  one reason code per failed check; empty when verified
    plainValues        the facts drills filter on directly (see `logparser.plain_values`)
    tags               the keys of the hand's tags (see `logparser.tags`)
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from logparser.calls import ADDED_KAN, CLOSED_KAN, Call, decode_call
from logparser.payments import payments, score_changes
from logparser.plain_values import plain_values
from logparser.situation import CALL, DISCARD, DRAW, Move, RoundMoves
from logparser.tags import TagSettings, hand_tags
from logparser.tiles import mpsz, tile
from logparser.verification import Verification, verify
from logparser.winning_hand import WinningHand
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

# Limit codes: the third value of AGARI's `ten`, by limit tier. A yakuman and a kazoe yakuman share a code.
TENHOU_LIMITS = {0: "none", 1: "mangan", 2: "haneman", 3: "baiman", 4: "sanbaiman"}
TENHOU_YAKUMAN_LIMIT = 5


@dataclass
class ParsedLog:
    hands: list[dict] = field(default_factory=list)
    skipped: str | None = None  # why the whole game was not taken: "sanma", "ruleset" or "malformed"


@dataclass
class _Round:
    """A round of the log: where it is in the log, who deals, how many wins it has had, and its moves so far."""

    index: int
    number: int  # Tenhou's seed[0]: round wind * 4 + hand number - 1
    dealer: int
    wins: int = 0
    moves: RoundMoves = field(default_factory=RoundMoves)


def parse_log(log_id: str, xml_text: str, tag_settings: TagSettings = TagSettings()) -> ParsedLog:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ParsedLog(skipped="malformed")
    parsed = ParsedLog()
    round_ = None
    for event in root:
        if event.tag == "GO":
            parsed.skipped = skip_reason(int(event.get("type")))
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
            parsed.hands.append(_hand(log_id, round_, event, tag_settings))
            round_.wins += 1
        elif (move := _move(event)) is not None:
            round_.moves.play(move)
    return parsed


def _move(event: ET.Element) -> Move | None:
    """The move in a draw, discard or call tag; None for any other tag."""
    if event.tag == "N":
        seat = int(event.get("who"))
        try:
            call = decode_call(int(event.get("m")))
        except ValueError:
            return Move(CALL, seat, ())
        return Move(CALL, seat, _robbable_tiles(call), call.type)
    if match := MOVE_TAG.fullmatch(event.tag):
        letter, tile_id = match[1], int(match[2])
        if letter in DRAW_TAGS:
            return Move(DRAW, DRAW_TAGS.index(letter), (tile_id,))
        return Move(DISCARD, DISCARD_TAGS.index(letter), (tile_id,))
    return None


def _robbable_tiles(call: Call) -> tuple[int, ...]:
    """The tiles of a call that another player can rob: the tile an added kan adds, or any tile of a closed
    kan (kokushi musou only)."""
    if call.type == ADDED_KAN:
        return (call.added_tile,)
    if call.type == CLOSED_KAN:
        return call.tiles
    return ()


def skip_reason(game_type: int) -> str | None:
    """Why a game of this type, the GO tag's `type`, is not taken, or None if it is. Only 4-player games
    with open tanyao and red fives are taken, east-only or hanchan."""
    if game_type & SANMA:
        return "sanma"
    if game_type & (NO_RED_FIVES | NO_OPEN_TANYAO):
        return "ruleset"
    return None


def _hand(log_id: str, round_: _Round, agari: ET.Element, tag_settings: TagSettings) -> dict:
    """The hand record of one win. The winning hand and its answer key are read from the AGARI tag and
    the round's moves; verification checks one against the other; plain values and tags follow from
    the record."""
    winner, discarder = int(agari.get("who")), int(agari.get("fromWho"))
    winning_hand = WinningHand(
        concealed=_ints(agari.get("hai")),
        calls=_calls(agari),
        winning_tile=int(agari.get("machi")),
        dora_indicators=_ints(agari.get("doraHai")),
        ura_dora_indicators=_ints(agari.get("doraHaiUra", "")),
        situation=_situation(round_, agari, winner=winner, discarder=discarder),
    )
    yaku = _recorded_yaku(agari)
    answer_key = _answer_key(agari, yaku, winning_hand.situation)
    verification = verify(
        winning_hand,
        unreadable_call_in_moves=round_.moves.unreadable_call,
        tiles_from_moves=round_.moves.tiles_handed_over(winner=winner, discarder=discarder),
        answer_key=answer_key,
        unknown_yaku=[tenhou_id for tenhou_id, _ in yaku if tenhou_id not in TENHOU_YAKU_KEYS],
        recorded_score_changes=_recorded_score_changes(agari),
        expected_score_changes=score_changes(answer_key["payments"], winner=winner, discarder=discarder,
                                             dealer=round_.dealer),
    )
    hand = {
        "id": f"{log_id}/{round_.index}/{round_.wins}",
        "replayUrl": REPLAY_URL.format(log_id=log_id, round_index=round_.index, seat=winner),
        **_record(winning_hand, answer_key, verification),
    }
    hand["plainValues"] = plain_values(hand)
    hand["tags"] = hand_tags(hand, tag_settings)
    return hand


def _situation(round_: _Round, agari: ET.Element, *, winner: int, discarder: int) -> dict:
    """The situation of a win by `winner` on `discarder`'s tile (their own on a tsumo): the round and seat,
    the sticks on the table from `ba`, and what the round's moves say."""
    honba, sticks = _ints(agari.get("ba"))
    return {
        "roundWind": WINDS[round_.number // 4],
        "seatWind": WINDS[(winner - round_.dealer) % 4],
        "dealer": winner == round_.dealer,
        "honba": honba,
        "riichiSticks": sticks,
        "secondWinner": round_.wins > 0,
        "tsumo": winner == discarder,
        **round_.moves.situation(winner=winner, discarder=discarder),
    }


def _record(hand: WinningHand, answer_key: dict, verification: Verification) -> dict:
    """The parts of a hand record that come from the winning hand and its verification. Only a hand whose
    cross-check matched has a raw fu, a fu breakdown and the fu of its splits."""
    matched = verification.recalculation
    return {
        "situation": hand.situation,
        "tiles": {
            "concealed": mpsz(hand.concealed),
            "calls": [_call_record(call) for call in hand.calls or []],
            "winningTile": tile(hand.winning_tile),
            "doraIndicators": mpsz(hand.dora_indicators),
            "uraDoraIndicators": mpsz(hand.ura_dora_indicators),
        },
        "answerKey": {
            **answer_key,
            "rawFu": None if matched is None else matched.raw_fu,
            "fuBreakdown": None if matched is None else matched.fu_breakdown,
        },
        "splitFu": None if matched is None else matched.split_fu,
        "quarantineReasons": verification.reasons,
    }


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


def _answer_key(agari: ET.Element, yaku: list[tuple[int, int]], situation: dict) -> dict:
    """Tenhou's recorded result, with yaku under their contract keys."""
    fu, points, limit = _ints(agari.get("ten"))
    return {
        "yaku": [{"key": TENHOU_YAKU_KEYS[i], "han": han} for i, han in yaku if i in TENHOU_YAKU_KEYS],
        "han": sum(han for _, han in yaku),
        "fu": fu,
        "limitTier": _limit_tier(limit, yakuman=bool(agari.get("yakuman"))),
        "points": points,
        "payments": _payments(points, situation),
    }


def _payments(points: int, situation: dict) -> dict:
    """The winner's payments. In a double ron Tenhou pays the honba and the riichi sticks to the first
    winner only: the second winner's `ba` still shows the honba, but its score change leaves them out."""
    collects = not situation["secondWinner"]
    return payments(points, tsumo=situation["tsumo"], dealer=situation["dealer"],
                    honba=situation["honba"] if collects else 0,
                    riichi_sticks=situation["riichiSticks"] if collects else 0)


def _limit_tier(limit: int, *, yakuman: bool) -> str | None:
    """The limit tier Tenhou recorded, or None for a limit code Tenhou never records.

    Tenhou records a kazoe yakuman as a yakuman: it is the one won without a yakuman.
    """
    if limit == TENHOU_YAKUMAN_LIMIT:
        return "yakuman" if yakuman else "kazoe-yakuman"
    return TENHOU_LIMITS.get(limit)


def _recorded_score_changes(agari: ET.Element) -> list[int]:
    """Each seat's score change in points. `sc` holds a score and a change per seat, in hundreds."""
    return [change * 100 for change in _ints(agari.get("sc", ""))[1::2]]


def _ints(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v]
