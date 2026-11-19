"""Reads the hands out of one Tenhou mjlog XML log."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from logparser.tiles import mpsz, tile
from logparser.yaku import TENHOU_YAKU_KEYS, YAKUMAN_HAN

REPLAY_URL = "https://tenhou.net/0/?log={log_id}&ts={round_index}&tw={seat}"


@dataclass
class ParsedLog:
    hands: list[dict] = field(default_factory=list)


WINDS = ("east", "south", "west", "north")


@dataclass
class _Round:
    """What a round's moves have told us so far."""

    index: int
    number: int  # Tenhou's seed[0]: round wind * 4 + hand number - 1
    dealer: int
    wins: int = 0
    riichi: set[int] = field(default_factory=set)  # seats whose riichi was accepted


def parse_log(log_id: str, xml_text: str) -> ParsedLog:
    root = ET.fromstring(xml_text)
    parsed = ParsedLog()
    round_ = None
    for event in root:
        if event.tag == "INIT":
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


def _hand(log_id: str, round_: _Round, agari: ET.Element) -> dict:
    winner = int(agari.get("who"))
    honba, sticks = _ints(agari.get("ba"))
    concealed = _ints(agari.get("hai"))
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
            "winningTile": tile(int(agari.get("machi"))),
            "doraIndicators": mpsz(_ints(agari.get("doraHai"))),
            "uraDoraIndicators": mpsz(_ints(agari.get("doraHaiUra", ""))),
        },
        "answerKey": _answer_key(agari),
    }


def _answer_key(agari: ET.Element) -> dict:
    """Tenhou's recorded result. Yaku worth 0 han (Tenhou lists ura dora 0) are left out."""
    if agari.get("yakuman"):
        recorded = [(tenhou_id, YAKUMAN_HAN) for tenhou_id in _ints(agari.get("yakuman"))]
    else:
        values = _ints(agari.get("yaku"))
        recorded = [(tenhou_id, han) for tenhou_id, han in zip(values[::2], values[1::2]) if han > 0]
    fu, points, _limit = _ints(agari.get("ten"))
    return {
        "yaku": [{"key": TENHOU_YAKU_KEYS[tenhou_id], "han": han} for tenhou_id, han in recorded],
        "han": sum(han for _, han in recorded),
        "fu": fu,
        "points": points,
    }


def _ints(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v]
