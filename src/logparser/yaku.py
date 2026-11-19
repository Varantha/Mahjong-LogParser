"""Yaku keys owned by the trainer bundle contract.

Tenhou records yaku by numeric ID. Those IDs never leave stage 1: every yaku
is stored and exported under the stable key below, and the trainer turns the
key into display text. ID 36 (renhou) is not used on Tenhou, so it has no key.
"""

YAKUMAN_HAN = 13

TENHOU_YAKU_KEYS = {
    0: "menzen-tsumo",
    1: "riichi",
    2: "ippatsu",
    3: "chankan",
    4: "rinshan",
    5: "haitei",
    6: "houtei",
    7: "pinfu",
    8: "tanyao",
    9: "iipeikou",
    10: "seat-wind-east",
    11: "seat-wind-south",
    12: "seat-wind-west",
    13: "seat-wind-north",
    14: "round-wind-east",
    15: "round-wind-south",
    16: "round-wind-west",
    17: "round-wind-north",
    18: "haku",
    19: "hatsu",
    20: "chun",
    21: "double-riichi",
    22: "chiitoitsu",
    23: "chanta",
    24: "ittsu",
    25: "sanshoku-doujun",
    26: "sanshoku-doukou",
    27: "sankantsu",
    28: "toitoi",
    29: "sanankou",
    30: "shousangen",
    31: "honroutou",
    32: "ryanpeikou",
    33: "junchan",
    34: "honitsu",
    35: "chinitsu",
    37: "tenhou",
    38: "chiihou",
    39: "daisangen",
    40: "suuankou",
    41: "suuankou-tanki",
    42: "tsuuiisou",
    43: "ryuuiisou",
    44: "chinroutou",
    45: "chuuren-poutou",
    46: "junsei-chuuren-poutou",
    47: "kokushi-musou",
    48: "kokushi-musou-13-wait",
    49: "daisuushii",
    50: "shousuushii",
    51: "suukantsu",
    52: "dora",
    53: "ura-dora",
    54: "aka-dora",
}

# Tenhou IDs 37-51. On a yakuman win Tenhou lists only the yakuman.
YAKUMAN_KEYS = frozenset(TENHOU_YAKU_KEYS[tenhou_id] for tenhou_id in range(37, 52))
