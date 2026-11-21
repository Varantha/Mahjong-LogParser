"""The drill engine: each drill in the drill catalogue is drawn from the whole hand store.

These tests give the engine hands built by hand: just an ID, plain values and tags, the parts
of a hand a drill filters on.
"""

import pytest

from logparser.drills import CatalogueError, Shortfall, draw_drills, load_catalogue


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


KUISAGARI = """
    [[drill]]
    key = "kuisagari"
    target = 6
    pool = { open = true }
    trap = { tags = "kuisagari" }
"""


def test_a_drill_short_of_trap_hands_is_made_up_with_lookalikes_and_says_which_part_fell_short(tmp_path):
    trap_hand = hand(1, yaku=["honitsu"], open=True, tags=["kuisagari"])
    lookalikes = [hand(number, yaku=["haku"], open=True) for number in range(2, 10)]

    [kuisagari] = draw_drills(catalogue(tmp_path, KUISAGARI), [trap_hand, *lookalikes])

    assert (len(kuisagari.hand_ids), kuisagari.short_by, trap_hand["id"] in kuisagari.hand_ids) == (6, 0, True)
    assert kuisagari.shortfalls == [Shortfall(part="trap hands", wanted=3, found=1)]


def test_a_drill_short_of_lookalikes_is_made_up_with_trap_hands(tmp_path):
    trap_hands = [hand(number, yaku=["honitsu"], open=True, tags=["kuisagari"]) for number in range(8)]
    lookalike = hand(8, yaku=["haku"], open=True)

    [kuisagari] = draw_drills(catalogue(tmp_path, KUISAGARI), [*trap_hands, lookalike])

    assert (len(drawn_ids(kuisagari) & ids(trap_hands)), lookalike["id"] in kuisagari.hand_ids) == (5, True)
    assert kuisagari.shortfalls == [Shortfall(part="lookalikes", wanted=3, found=1)]


def test_a_drill_made_up_from_its_other_parts_draws_them_on_the_newest_year_first(tmp_path):
    trap_hand = hand(1, year=2024, yaku=["honitsu"], open=True, tags=["kuisagari"])
    lookalikes_2024 = [hand(number, year=2024, yaku=["haku"], open=True) for number in range(2, 7)]
    lookalikes_2023 = [hand(number, year=2023, yaku=["haku"], open=True) for number in range(7, 12)]

    [kuisagari] = draw_drills(catalogue(tmp_path, KUISAGARI), [trap_hand, *lookalikes_2024, *lookalikes_2023])

    assert (len(kuisagari.hand_ids), drawn_ids(kuisagari) & ids(lookalikes_2023)) == (6, set())


def test_a_drill_whose_whole_pool_is_short_takes_every_pool_hand_and_says_which_parts_fell_short(tmp_path):
    trap_hand = hand(1, yaku=["honitsu"], open=True, tags=["kuisagari"])
    lookalikes = [hand(2, yaku=["haku"], open=True), hand(3, yaku=["haku"], open=True)]
    closed = hand(4)

    [kuisagari] = draw_drills(catalogue(tmp_path, KUISAGARI), [trap_hand, *lookalikes, closed])

    assert (drawn_ids(kuisagari), kuisagari.short_by) == (ids([trap_hand, *lookalikes]), 3)
    assert kuisagari.shortfalls == [Shortfall(part="trap hands", wanted=3, found=1),
                                    Shortfall(part="lookalikes", wanted=3, found=2)]


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


def test_a_quota_the_hand_store_cannot_fill_is_made_up_from_the_rest_of_the_pool(tmp_path):
    haneman = [hand(number, han=6, limitTier="haneman") for number in range(10)]
    yakuman = hand(10, han=13, limitTier="yakuman")

    [big_hands] = draw_drills(catalogue(tmp_path, BIG_HANDS), [*haneman, yakuman])

    assert (len(big_hands.hand_ids), big_hands.short_by, yakuman["id"] in big_hands.hand_ids) == (4, 0, True)
    assert big_hands.shortfalls == [Shortfall(part="limitTier = yakuman", wanted=2, found=1)]


@pytest.mark.parametrize("entry, problem", [
    ('pool = { limittier = "yakuman" }', "limittier"),
    ('quotas = [{ share = 0.5, where = { dealr = true } }]', "dealr"),
    ('trap = { tags = "no-such-tag" }', "no-such-tag"),
    ('pool = { open = true }\nlookalike = 0.3', "lookalike"),
    ('quotas = [{ share = 0.5, were = { dealer = true } }]', "were"),
    ('trap = { open = true }\nlookalikes = 1.5', "lookalikes"),
    ('lookalikes = 0.5', "lookalikes"),
    ('quotas = [{ share = 0.6, where = { dealer = true } }, { share = 0.6, where = { honba = 1 } }]', "quotas"),
    ('trap = { open = true }\nquotas = [{ share = 0.5, where = { dealer = true } }]', "quotas"),
    # A tag that gives the answer away never gets a drill of its own: it can only be a trap, with lookalikes.
    ('pool = { tags = "fu-mangan" }', "fu-mangan gives the answer away"),
    ('pool = { open = true }\nquotas = [{ share = 0.5, where = { tags = ["kuisagari", "open-pinfu-shape"] } }]',
     "open-pinfu-shape gives the answer away"),
    ('pool = { han = [3, 4] }\ntrap = { tags = "fu-mangan" }\nlookalikes = 0', "fu-mangan gives the answer away"),
])
def test_a_drill_the_engine_cannot_follow_is_refused_naming_the_drill_and_the_problem(tmp_path, entry, problem):
    with pytest.raises(CatalogueError, match=f"'payments'.*{problem}"):
        catalogue(tmp_path, f'[[drill]]\nkey = "payments"\ntarget = 500\n{entry}\n')


def test_a_tag_that_gives_the_answer_away_can_be_the_trap_of_a_drill_that_mixes_in_lookalikes(tmp_path):
    [drill] = catalogue(tmp_path, """
        [[drill]]
        key = "mangan-or-not"
        target = 500
        pool = { han = [3, 4] }
        trap = { tags = "fu-mangan" }
        lookalikes = 0.3
    """)

    assert (drill.trap.wanted, drill.lookalikes) == ({"tags": "fu-mangan"}, 0.3)


def test_a_catalogue_with_two_drills_under_one_key_is_refused(tmp_path):
    with pytest.raises(CatalogueError, match="'payments'"):
        catalogue(tmp_path, '[[drill]]\nkey = "payments"\ntarget = 500\n\n[[drill]]\nkey = "payments"\ntarget = 50\n')


# The drill catalogue this repo ships.

def shipped_drill(key: str, hands: list[dict]):
    [drill] = [drill for drill in draw_drills(load_catalogue(), hands) if drill.key == key]
    return drill


def numbered(count: int, start: int = 0, **values) -> list[dict]:
    return [hand(number, **values) for number in range(start, start + count)]


def test_the_catalogue_holds_every_drill_in_the_drill_table_each_aiming_for_1000():
    assert [(drill.key, drill.target) for drill in load_catalogue()] == [
        ("everything", 1000), ("fu-rounding-edge", 1000), ("tricky-waits", 1000), ("high-fu", 1000),
        ("open-hand-fu", 1000), ("mangan-or-not", 1000), ("open-hand-han", 1000), ("hidden-dora", 1000),
        ("big-hands", 1000), ("tsumo-payments", 1000), ("ron-payments", 1000)]


@pytest.mark.parametrize("key, tag", [
    ("fu-rounding-edge", "knife-edge-fu"),
    ("tricky-waits", "ambiguous-wait"),
    ("high-fu", "high-fu"),
])
def test_a_drill_on_a_tag_that_gives_nothing_away_takes_only_hands_with_that_tag(key, tag):
    tagged = numbered(600, tags=[tag]) + numbered(600, 600, tags=[tag, "kuisagari"], open=True)
    untagged = numbered(800, 1200) + numbered(800, 2000, tags=["kuisagari"], open=True)

    drill = shipped_drill(key, tagged + untagged)

    assert (len(drill.hand_ids), drawn_ids(drill) <= ids(tagged)) == (1000, True)


def test_everything_draws_1000_hands_of_every_kind():
    hands = (numbered(400) + numbered(400, 400, tsumo=True, dealer=True)
             + numbered(400, 800, han=13, limitTier="yakuman", yaku=["kokushi-musou"], open=False))

    everything = shipped_drill("everything", hands)

    assert len(everything.hand_ids) == 1000 and everything.short_by == 0


def test_open_hand_fu_takes_open_hands_up_to_4_han_half_of_them_with_the_open_pinfu_shape():
    open_pinfu_shape = (numbered(400, han=1, rawFu=20, open=True, tags=["open-pinfu-shape"])
                        + numbered(400, 400, han=4, rawFu=20, open=True, tags=["open-pinfu-shape"]))
    lookalikes = numbered(400, 800, han=2, rawFu=24, open=True) + numbered(400, 1200, han=3, rawFu=32, open=True)
    # Raw fu 20 is only a trap below mangan, and a closed hand at 20 fu is pinfu tsumo.
    other_hands = (numbered(400, 1600, han=5, rawFu=20, limitTier="mangan", open=True, tags=["open-pinfu-shape"])
                   + numbered(400, 2000, han=2, fu=20, rawFu=20, tsumo=True, yaku=["menzen-tsumo", "pinfu"]))

    open_hand_fu = shipped_drill("open-hand-fu", open_pinfu_shape + lookalikes + other_hands)

    drawn = drawn_ids(open_hand_fu)
    assert (len(drawn & ids(open_pinfu_shape)), len(drawn & ids(lookalikes)), len(drawn)) == (500, 500, 1000)


def test_mangan_or_not_takes_hands_with_3_or_4_han_half_of_them_pushed_to_mangan_by_fu():
    fu_mangan = (numbered(400, han=3, fu=70, limitTier="mangan", tags=["fu-mangan"])
                 + numbered(400, 400, han=4, fu=40, limitTier="mangan", tags=["fu-mangan"]))
    lookalikes = numbered(400, 800, han=3, fu=60) + numbered(400, 1200, han=4, fu=30)
    other_hands = numbered(400, 1600, han=2, fu=70) + numbered(400, 2000, han=5, fu=40, limitTier="mangan")

    mangan_or_not = shipped_drill("mangan-or-not", fu_mangan + lookalikes + other_hands)

    drawn = drawn_ids(mangan_or_not)
    assert (len(drawn & ids(fu_mangan)), len(drawn & ids(lookalikes)), len(drawn)) == (500, 500, 1000)


def test_open_hand_han_takes_hands_with_a_yaku_worth_less_open_half_of_them_closed_lookalikes():
    open_hands = (numbered(300, yaku=["honitsu"], open=True) + numbered(300, 300, yaku=["sanshoku-doujun"], open=True)
                  + numbered(100, 600, yaku=["chanta"], open=True) + numbered(100, 700, yaku=["junchan"], open=True))
    closed_hands = (numbered(300, 800, yaku=["riichi", "ittsu"]) + numbered(300, 1100, yaku=["chinitsu"]))
    other_hands = numbered(600, 1400, yaku=["tanyao"], open=True) + numbered(600, 2000, yaku=["sanshoku-doukou"])

    open_hand_han = shipped_drill("open-hand-han", open_hands + closed_hands + other_hands)

    drawn = drawn_ids(open_hand_han)
    assert (len(drawn & ids(open_hands)), len(drawn & ids(closed_hands)), len(drawn)) == (500, 500, 1000)


def test_hidden_dora_takes_hands_holding_dora_half_of_them_named_by_an_indicator_that_wraps_round():
    wraparound = numbered(800, yaku=["riichi", "dora"], doraCount=1, tags=["wraparound-dora"])
    lookalikes = numbered(800, 800, yaku=["tanyao", "dora", "aka-dora"], doraCount=3, open=True)
    # Red fives and ura dora: dora a player doesn't find by reading the dora indicators.
    other_dora = (numbered(400, 1600, yaku=["riichi", "aka-dora"], doraCount=1)
                  + numbered(400, 2000, yaku=["riichi", "ura-dora"], doraCount=2))
    no_dora = numbered(400, 2400)

    hidden_dora = shipped_drill("hidden-dora", wraparound + lookalikes + other_dora + no_dora)

    drawn = drawn_ids(hidden_dora)
    assert (len(drawn & ids(wraparound)), len(drawn & ids(lookalikes)), len(drawn)) == (500, 500, 1000)


def test_big_hands_takes_haneman_and_above_giving_a_fifth_of_the_drill_to_sanbaiman_kazoe_yakuman_and_yakuman():
    common = numbered(1200, han=6, limitTier="haneman") + numbered(400, 1200, han=8, limitTier="baiman")
    rare = (numbered(60, 1600, han=11, limitTier="sanbaiman") + numbered(60, 1660, han=13, limitTier="kazoe-yakuman")
            + numbered(80, 1720, han=13, limitTier="yakuman"))
    mangan = numbered(600, 1800, han=5, limitTier="mangan")

    big_hands = shipped_drill("big-hands", common + rare + mangan)

    assert (len(big_hands.hand_ids), drawn_ids(big_hands) >= ids(rare), drawn_ids(big_hands) & ids(mangan)) == (
        1000, True, set())


def test_big_hands_short_of_sanbaiman_and_above_says_so_and_makes_up_the_rest_with_haneman_and_baiman():
    # A few thousand haneman, but only 44 hands above baiman.
    common = numbered(4000, han=6, limitTier="haneman")
    rare = numbered(16, 4000, han=11, limitTier="sanbaiman") + numbered(28, 4016, han=13, limitTier="yakuman")

    big_hands = shipped_drill("big-hands", common + rare)

    assert (len(big_hands.hand_ids), big_hands.short_by, drawn_ids(big_hands) >= ids(rare)) == (1000, 0, True)
    assert big_hands.shortfalls == [
        Shortfall(part="limitTier = sanbaiman/kazoe-yakuman/yakuman", wanted=200, found=44)]


def test_tsumo_payments_takes_tsumo_hands_dealer_and_non_dealer_some_with_honba():
    non_dealer = numbered(600, tsumo=True, yaku=["menzen-tsumo"]) + numbered(200, 600, tsumo=True, honba=1)
    dealer = numbered(300, 800, tsumo=True, dealer=True) + numbered(100, 1100, tsumo=True, dealer=True, honba=2)
    ron = numbered(600, 1200, honba=1)

    tsumo_payments = shipped_drill("tsumo-payments", non_dealer + dealer + ron)

    drawn = drawn_ids(tsumo_payments)
    assert (len(drawn), drawn & ids(ron)) == (1000, set())
    assert drawn & ids(dealer) and drawn & ids(non_dealer) and drawn & ids(non_dealer[600:] + dealer[300:])


def test_ron_payments_takes_ron_hands_dealer_and_non_dealer_some_with_honba():
    non_dealer = numbered(600) + numbered(200, 600, honba=1)
    dealer = numbered(300, 800, dealer=True) + numbered(100, 1100, dealer=True, honba=2)
    tsumo = numbered(600, 1200, tsumo=True, honba=1)

    ron_payments = shipped_drill("ron-payments", non_dealer + dealer + tsumo)

    drawn = drawn_ids(ron_payments)
    assert (len(drawn), drawn & ids(tsumo)) == (1000, set())
    assert drawn & ids(dealer) and drawn & ids(non_dealer) and drawn & ids(non_dealer[600:] + dealer[300:])
