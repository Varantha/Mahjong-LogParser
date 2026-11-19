"""The drill engine: each drill in the drill catalogue is drawn from the whole hand store.

These tests give the engine hands built by hand: just an ID, plain values and tags, the parts
of a hand a drill filters on.
"""

import pytest

from logparser.drills import Shortfall, draw_drills, load_catalogue


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


def ids(hands: list[dict]) -> set[str]:
    return {hand["id"] for hand in hands}


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


def test_a_drill_with_no_pool_draws_its_target_of_hands_at_random_from_every_hand_repeatably_by_seed(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "everything"
        target = 3
    """)
    hands = [hand(number) for number in range(10)]

    [first], [same_seed], [other_seed] = (draw_drills(drills, hands, seed=seed) for seed in (1, 1, 2))

    assert len(first.hand_ids) == 3 and drawn_ids(first) <= {hand["id"] for hand in hands}
    assert (first.hand_ids == same_seed.hand_ids, first.hand_ids == other_seed.hand_ids) == (True, False)


def test_a_drill_draws_only_on_the_newest_year_of_logs_when_that_year_holds_enough_hands(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "everything"
        target = 2
    """)
    newest = [hand(number, year=2024) for number in range(3)]
    older = [hand(number, year=2023) for number in range(3)]

    [everything] = draw_drills(drills, older + newest)

    assert len(everything.hand_ids) == 2 and drawn_ids(everything) <= ids(newest)


def test_a_drill_short_of_hands_draws_on_older_years_one_at_a_time_until_it_has_enough(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "everything"
        target = 4
    """)
    in_2024, in_2023 = [hand(number, year=2024) for number in range(2)], [hand(0, year=2023)]
    in_2022, in_2021 = [hand(number, year=2022) for number in range(3)], [hand(number, year=2021) for number in range(3)]

    [everything] = draw_drills(drills, in_2021 + in_2022 + in_2023 + in_2024)

    from_2022 = drawn_ids(everything) - ids(in_2024 + in_2023)
    assert (len(everything.hand_ids), len(from_2022)) == (4, 1) and from_2022 <= ids(in_2022)


def test_a_drill_the_whole_hand_store_cannot_fill_takes_every_pool_hand_and_says_how_short_it_falls(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "payments"
        target = 5
        pool = { tsumo = true }
    """)
    tsumo = [hand(1, year=2024, tsumo=True), hand(2, year=2023, tsumo=True), hand(3, year=2019, tsumo=True)]
    ron = [hand(number, year=2024) for number in range(4, 10)]

    [payments] = draw_drills(drills, tsumo + ron)

    assert (drawn_ids(payments), payments.target, payments.short_by) == (ids(tsumo), 5, 2)


def test_a_drill_the_hand_store_can_fill_falls_short_by_nothing(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "everything"
        target = 2
    """)

    [everything] = draw_drills(drills, [hand(number) for number in range(3)])

    assert everything.short_by == 0


def test_lookalikes_from_the_same_pool_without_the_trap_make_up_their_share_of_the_drill(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "open-hand-han"
        target = 4
        pool = { yaku = ["ittsu", "honitsu"] }
        trap = { open = true }
        lookalikes = 0.25
    """)
    open_ittsu = [hand(number, yaku=["ittsu"], open=True, callTypes=["chi"]) for number in range(5)]
    closed_ittsu = [hand(number, yaku=["riichi", "ittsu"]) for number in range(5, 10)]
    open_tanyao = [hand(number, yaku=["tanyao"], open=True, callTypes=["pon"]) for number in range(10, 15)]

    [open_hand_han] = draw_drills(drills, open_ittsu + closed_ittsu + open_tanyao)

    drawn = drawn_ids(open_hand_han)
    assert (len(drawn & ids(open_ittsu)), len(drawn & ids(closed_ittsu)), len(drawn)) == (3, 1, 4)


def test_lookalikes_make_up_about_half_a_drill_unless_the_catalogue_says_otherwise_and_a_tag_can_be_the_trap(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "kuisagari"
        target = 4
        pool = { open = true }
        trap = { tags = "kuisagari" }
    """)
    trap_hands = [hand(number, yaku=["honitsu"], open=True, tags=["kuisagari"]) for number in range(5)]
    lookalikes = [hand(number, yaku=["haku"], open=True) for number in range(5, 10)]

    [kuisagari] = draw_drills(drills, trap_hands + lookalikes)

    assert (len(drawn_ids(kuisagari) & ids(trap_hands)), len(drawn_ids(kuisagari) & ids(lookalikes))) == (2, 2)


def test_a_drill_short_of_trap_hands_is_not_filled_up_with_lookalikes_and_says_which_part_fell_short(tmp_path):
    drills = catalogue(tmp_path, """
        [[drill]]
        key = "kuisagari"
        target = 6
        pool = { open = true }
        trap = { tags = "kuisagari" }
    """)
    trap_hand = hand(1, yaku=["honitsu"], open=True, tags=["kuisagari"])
    lookalikes = [hand(number, yaku=["haku"], open=True) for number in range(2, 10)]

    [kuisagari] = draw_drills(drills, [trap_hand, *lookalikes])

    assert (len(kuisagari.hand_ids), kuisagari.short_by) == (4, 2)
    assert kuisagari.shortfalls == [Shortfall(part="trap hands", wanted=3, found=1)]


BIG_HANDS = """
    [[drill]]
    key = "big-hands"
    target = 4
    pool = { limitTier = ["haneman", "yakuman"] }
    quotas = [{ share = 0.5, where = { limitTier = "yakuman" } }]
"""


def test_a_quota_gives_its_share_of_a_drill_to_pool_hands_that_are_rarer_in_real_games(tmp_path):
    haneman = [hand(number, han=6, limitTier="haneman") for number in range(40)]
    yakuman = [hand(number, han=13, limitTier="yakuman") for number in range(40, 42)]
    mangan = [hand(number, han=5, limitTier="mangan") for number in range(42, 50)]

    [big_hands] = draw_drills(catalogue(tmp_path, BIG_HANDS), haneman + yakuman + mangan)

    assert (len(big_hands.hand_ids), drawn_ids(big_hands) >= ids(yakuman)) == (4, True)
    assert drawn_ids(big_hands) <= ids(haneman + yakuman)


def test_a_short_quota_reaches_back_through_the_years_while_the_rest_of_the_drill_stays_in_the_newest(tmp_path):
    haneman_2024 = [hand(number, year=2024, han=6, limitTier="haneman") for number in range(10)]
    yakuman_2023 = [hand(number, year=2023, han=13, limitTier="yakuman") for number in range(10, 12)]
    haneman_2022 = [hand(number, year=2022, han=6, limitTier="haneman") for number in range(12, 20)]

    [big_hands] = draw_drills(catalogue(tmp_path, BIG_HANDS), haneman_2024 + yakuman_2023 + haneman_2022)

    assert (len(drawn_ids(big_hands) & ids(haneman_2024)), drawn_ids(big_hands) & ids(haneman_2022)) == (2, set())
    assert drawn_ids(big_hands) >= ids(yakuman_2023)


def test_a_quota_the_hand_store_cannot_fill_is_not_made_up_from_the_rest_of_the_pool(tmp_path):
    haneman = [hand(number, han=6, limitTier="haneman") for number in range(10)]
    yakuman = hand(10, han=13, limitTier="yakuman")

    [big_hands] = draw_drills(catalogue(tmp_path, BIG_HANDS), [*haneman, yakuman])

    assert (len(big_hands.hand_ids), yakuman["id"] in big_hands.hand_ids) == (3, True)
    assert big_hands.shortfalls == [Shortfall(part="limitTier = yakuman", wanted=2, found=1)]
