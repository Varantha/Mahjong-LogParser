"""Reads the hands out of one Tenhou mjlog XML log."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from logparser.tiles import mpsz, tile


@dataclass
class ParsedLog:
    hands: list[dict] = field(default_factory=list)


def parse_log(log_id: str, xml_text: str) -> ParsedLog:
    root = ET.fromstring(xml_text)
    parsed = ParsedLog()
    for event in root:
        if event.tag == "AGARI":
            parsed.hands.append(_hand(event))
    return parsed


def _hand(agari: ET.Element) -> dict:
    concealed = _ints(agari.get("hai"))
    return {
        "tiles": {
            "concealed": mpsz(concealed),
            "winningTile": tile(int(agari.get("machi"))),
            "doraIndicators": mpsz(_ints(agari.get("doraHai"))),
            "uraDoraIndicators": mpsz(_ints(agari.get("doraHaiUra", ""))),
        },
    }


def _ints(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v]
