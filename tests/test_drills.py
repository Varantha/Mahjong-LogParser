"""The drill engine: each drill in the drill catalogue is drawn from the whole hand store.

These tests give the engine hands built by hand: just an ID, plain values and tags, the parts
of a hand a drill filters on.
"""

import pytest

from logparser.drills import draw_drills, load_catalogue


def hand(number: int, *, year: int = 2024, tags: tuple[str, ...] = (), **plain_values) -> dict:
    """A verified hand: by default a closed 1 han 30 fu ron with riichi, from a log of `year`."""
    return {
        "id": f"{year}010112gm-00a9-0000-{number:08x}/0/0",
        "plainValues": {
            "han": 1, "fu": 30, "rawFu": 30, "limitTier": "none", "dealer": False, "tsumo": False, "open": False,
            "yaku": ["riichi"], "doraCount": 0, "honba": 0, "riichiSticks": 0, "callTypes": [],
            **plain_values,
        },
        "tags": list(tags),
    }


def catalogue(tmp_path, toml: str):
    path = tmp_path / "drills.toml"
    path.write_text(toml)
    return load_catalogue(path)


def drawn_ids(drill) -> set[str]:
    return set(drill.hand_ids)


def test_a_drill_takes_only_hands_from_its_pool(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "payments"
        target = 500
        pool = { tsumo = true }
    """)
    tsumo, ron = hand(1, tsumo=True), hand(2)

    [payments] = draw_drills(drills, [tsumo, ron])

    assert (payments.key, drawn_ids(payments)) == ("payments", {tsumo["id"]})


def test_a_condition_with_several_values_takes_hands_with_any_of_them(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "big-hands"
        target = 500
        pool = { limitTier = ["haneman", "yakuman"] }
    """)
    haneman, baiman, yakuman = hand(1, limitTier="haneman"), hand(2, limitTier="baiman"), hand(3, limitTier="yakuman")

    [big_hands] = draw_drills(drills, [haneman, baiman, yakuman])

    assert drawn_ids(big_hands) == {haneman["id"], yakuman["id"]}


def test_a_condition_on_yaku_call_types_or_tags_takes_hands_holding_any_of_its_values(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "rare-situations"
        target = 500
        pool = { yaku = ["haitei", "rinshan"] }

        [[drill]]
        key = "chi-hands"
        target = 500
        pool = { callTypes = "chi" }

        [[drill]]
        key = "kuisagari-hands"
        target = 500
        pool = { tags = "kuisagari" }
    """)
    haitei = hand(1, yaku=["menzen-tsumo", "haitei"], tsumo=True)
    rinshan = hand(2, yaku=["rinshan", "dora"], tsumo=True)
    chi_kuisagari = hand(3, yaku=["ittsu"], open=True, callTypes=["pon", "chi"], tags=["kuisagari"])
    riichi = hand(4)

    rare, chi, kuisagari = draw_drills(drills, [haitei, rinshan, chi_kuisagari, riichi])

    assert (drawn_ids(rare), drawn_ids(chi), drawn_ids(kuisagari)) == (
        {haitei["id"], rinshan["id"]}, {chi_kuisagari["id"]}, {chi_kuisagari["id"]})
