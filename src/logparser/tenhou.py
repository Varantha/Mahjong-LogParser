"""Reads the hands out of one Tenhou mjlog XML log.

Every win (AGARI) in a taken game becomes a hand record, a JSON-ready dict:

    id                 <logId>/<roundIndex>/<winIndex>
    replayUrl          Tenhou replay of the round from the winner's seat (hand store only)
    situation          winds, dealer, honba, riichi sticks, tsumo, riichi
    tiles              concealed tiles, calls, winning tile and dora indicators, in mpsz.
                       Each call is {type, tiles, calledTile, calledFrom}, in the order made.
    answerKey          Tenhou's recorded yaku (contract keys), han, fu and points
    quarantineReasons  one reason code per failed check; empty when verified
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from logparser.calls import Call, decode_call
from logparser.tiles import mpsz, tile
from logparser.verification import quarantine_reasons
from logparser.yaku import TENHOU_YAKU_KEYS, YAKUMAN_HAN

REPLAY_URL = "https://tenhou.net/0/?log={log_id}&ts={round_index}&tw={seat}"
WINDS = ("east", "south", "west", "north")

# Bits of the GO tag's `type` attribute.
NO_RED_FIVES = 0x02
NO_OPEN_TANYAO = 0x04
SANMA = 0x10


@dataclass
class ParsedLog:
    hands: list[dict] = field(default_factory=list)
    skipped: str | None = None  # why the whole game was not taken: "sanma", "ruleset" or "malformed"


@dataclass
class _Round:
    """What a round's moves have told us so far."""

    index: int
    number: int  # Tenhou's seed[0]: round wind * 4 + hand number - 1
    dealer: int
    wins: int = 0
    riichi: set[int] = field(default_factory=set)  # seats whose riichi was accepted


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
        elif event.tag == "REACH" and event.get("step") == "2":
            round_.riichi.add(int(event.get("who")))
        elif event.tag == "AGARI":
            parsed.hands.append(_hand(log_id, round_, event))
            round_.wins += 1
    return parsed


def _skip_reason(game_type: int) -> str | None:
    """Only 4-player games with open tanyao and red fives are taken, east-only or hanchan."""
    if game_type & SANMA:
        return "sanma"
    if game_type & (NO_RED_FIVES | NO_OPEN_TANYAO):
        return "ruleset"
    return None


def _hand(log_id: str, round_: _Round, agari: ET.Element) -> dict:
    winner = int(agari.get("who"))
    honba, sticks = _ints(agari.get("ba"))
    concealed = _ints(agari.get("hai"))
    calls = [decode_call(code) for code in reversed(_ints(agari.get("m", "")))]  # Tenhou lists them latest first
    yaku = _recorded_yaku(agari)
    reasons = quarantine_reasons(
        concealed=concealed,
        calls=calls,
        unknown_yaku=[tenhou_id for tenhou_id, _ in yaku if tenhou_id not in TENHOU_YAKU_KEYS],
    )
    return {
        "id": f"{log_id}/{round_.index}/{round_.wins}",
        "replayUrl": REPLAY_URL.format(log_id=log_id, round_index=round_.index, seat=winner),
        "situation": {
            "roundWind": WINDS[round_.number // 4],
            "seatWind": WINDS[(winner - round_.dealer) % 4],
            "dealer": winner == round_.dealer,
            "honba": honba,
            "riichiSticks": sticks,
            "tsumo": winner == int(agari.get("fromWho")),
            "riichi": winner in round_.riichi,
        },
        "tiles": {
            "concealed": mpsz(concealed),
            "calls": [_call_record(call) for call in calls],
            "winningTile": tile(int(agari.get("machi"))),
            "doraIndicators": mpsz(_ints(agari.get("doraHai"))),
            "uraDoraIndicators": mpsz(_ints(agari.get("doraHaiUra", ""))),
        },
        "answerKey": _answer_key(agari, yaku),
        "quarantineReasons": reasons,
    }


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


def _answer_key(agari: ET.Element, yaku: list[tuple[int, int]]) -> dict:
    """Tenhou's recorded result, with yaku under their contract keys."""
    fu, points, _limit = _ints(agari.get("ten"))
    return {
        "yaku": [{"key": TENHOU_YAKU_KEYS[i], "han": han} for i, han in yaku if i in TENHOU_YAKU_KEYS],
        "han": sum(han for _, han in yaku),
        "fu": fu,
        "points": points,
    }


def _ints(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v]
