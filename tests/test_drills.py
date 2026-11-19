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

    assert (drill.trap.conditions, drill.lookalikes) == ({"tags": "fu-mangan"}, 0.3)


def test_a_catalogue_with_two_drills_under_one_key_is_refused(tmp_path):
    with pytest.raises(CatalogueError, match="'payments'"):
        catalogue(tmp_path, '[[drill]]\nkey = "payments"\ntarget = 500\n\n[[drill]]\nkey = "payments"\ntarget = 50\n')


# The drill catalogue this repo ships.

def shipped_drill(key: str, hands: list[dict]):
    [drill] = [drill for drill in draw_drills(load_catalogue(), hands) if drill.key == key]
    return drill


def numbered(count: int, start: int = 0, **values) -> list[dict]:
    return [hand(number, **values) for number in range(start, start + count)]


def test_the_catalogue_holds_every_drill_in_the_drill_table_each_aiming_for_500():
    assert [(drill.key, drill.target) for drill in load_catalogue()] == [
        ("everything", 500), ("fu-rounding-edge", 500), ("tricky-waits", 500), ("high-fu", 500),
        ("open-hand-fu", 500), ("mangan-or-not", 500), ("open-hand-han", 500), ("hidden-dora", 500),
        ("big-hands", 500), ("payments", 500), ("rare-situations", 500)]


@pytest.mark.parametrize("key, tag", [
    ("fu-rounding-edge", "knife-edge-fu"),
    ("tricky-waits", "ambiguous-wait"),
    ("high-fu", "high-fu"),
])
def test_a_drill_on_a_tag_that_gives_nothing_away_takes_only_hands_with_that_tag(key, tag):
    tagged = numbered(300, tags=[tag]) + numbered(300, 300, tags=[tag, "kuisagari"], open=True)
    untagged = numbered(400, 600) + numbered(400, 1000, tags=["kuisagari"], open=True)

    drill = shipped_drill(key, tagged + untagged)

    assert (len(drill.hand_ids), drawn_ids(drill) <= ids(tagged)) == (500, True)


def test_everything_draws_500_hands_of_every_kind():
    hands = (numbered(200) + numbered(200, 200, tsumo=True, dealer=True)
             + numbered(200, 400, han=13, limitTier="yakuman", yaku=["kokushi-musou"], open=False))

    everything = shipped_drill("everything", hands)

    assert len(everything.hand_ids) == 500 and everything.short_by == 0


def test_open_hand_fu_takes_open_hands_up_to_4_han_half_of_them_with_the_open_pinfu_shape():
    open_pinfu_shape = (numbered(200, han=1, rawFu=20, open=True, tags=["open-pinfu-shape"])
                        + numbered(200, 200, han=4, rawFu=20, open=True, tags=["open-pinfu-shape"]))
    lookalikes = numbered(200, 400, han=2, rawFu=24, open=True) + numbered(200, 600, han=3, rawFu=32, open=True)
    # Raw fu 20 is only a trap below mangan, and a closed hand at 20 fu is pinfu tsumo.
    other_hands = (numbered(200, 800, han=5, rawFu=20, limitTier="mangan", open=True, tags=["open-pinfu-shape"])
                   + numbered(200, 1000, han=2, fu=20, rawFu=20, tsumo=True, yaku=["menzen-tsumo", "pinfu"]))

    open_hand_fu = shipped_drill("open-hand-fu", open_pinfu_shape + lookalikes + other_hands)

    drawn = drawn_ids(open_hand_fu)
    assert (len(drawn & ids(open_pinfu_shape)), len(drawn & ids(lookalikes)), len(drawn)) == (250, 250, 500)


def test_mangan_or_not_takes_hands_with_3_or_4_han_half_of_them_pushed_to_mangan_by_fu():
    fu_mangan = (numbered(200, han=3, fu=70, limitTier="mangan", tags=["fu-mangan"])
                 + numbered(200, 200, han=4, fu=40, limitTier="mangan", tags=["fu-mangan"]))
    lookalikes = numbered(200, 400, han=3, fu=60) + numbered(200, 600, han=4, fu=30)
    other_hands = numbered(200, 800, han=2, fu=70) + numbered(200, 1000, han=5, fu=40, limitTier="mangan")

    mangan_or_not = shipped_drill("mangan-or-not", fu_mangan + lookalikes + other_hands)

    drawn = drawn_ids(mangan_or_not)
    assert (len(drawn & ids(fu_mangan)), len(drawn & ids(lookalikes)), len(drawn)) == (250, 250, 500)


def test_open_hand_han_takes_hands_with_a_yaku_worth_less_open_half_of_them_closed_lookalikes():
    open_hands = (numbered(150, yaku=["honitsu"], open=True) + numbered(150, 150, yaku=["sanshoku-doujun"], open=True)
                  + numbered(50, 300, yaku=["chanta"], open=True) + numbered(50, 350, yaku=["junchan"], open=True))
    closed_hands = (numbered(150, 400, yaku=["riichi", "ittsu"]) + numbered(150, 550, yaku=["chinitsu"]))
    other_hands = numbered(300, 700, yaku=["tanyao"], open=True) + numbered(300, 1000, yaku=["sanshoku-doukou"])

    open_hand_han = shipped_drill("open-hand-han", open_hands + closed_hands + other_hands)

    drawn = drawn_ids(open_hand_han)
    assert (len(drawn & ids(open_hands)), len(drawn & ids(closed_hands)), len(drawn)) == (250, 250, 500)


def test_hidden_dora_takes_hands_holding_dora_half_of_them_named_by_an_indicator_that_wraps_round():
    wraparound = numbered(400, yaku=["riichi", "dora"], doraCount=1, tags=["wraparound-dora"])
    lookalikes = numbered(400, 400, yaku=["tanyao", "dora", "aka-dora"], doraCount=3, open=True)
    # Red fives and ura dora: dora a player doesn't find by reading the dora indicators.
    other_dora = (numbered(200, 800, yaku=["riichi", "aka-dora"], doraCount=1)
                  + numbered(200, 1000, yaku=["riichi", "ura-dora"], doraCount=2))
    no_dora = numbered(200, 1200)

    hidden_dora = shipped_drill("hidden-dora", wraparound + lookalikes + other_dora + no_dora)

    drawn = drawn_ids(hidden_dora)
    assert (len(drawn & ids(wraparound)), len(drawn & ids(lookalikes)), len(drawn)) == (250, 250, 500)


def test_big_hands_takes_haneman_and_above_giving_a_fifth_of_the_drill_to_sanbaiman_kazoe_yakuman_and_yakuman():
    common = numbered(600, han=6, limitTier="haneman") + numbered(200, 600, han=8, limitTier="baiman")
    rare = (numbered(30, 800, han=11, limitTier="sanbaiman") + numbered(30, 830, han=13, limitTier="kazoe-yakuman")
            + numbered(40, 860, han=13, limitTier="yakuman"))
    mangan = numbered(300, 900, han=5, limitTier="mangan")

    big_hands = shipped_drill("big-hands", common + rare + mangan)

    assert (len(big_hands.hand_ids), drawn_ids(big_hands) >= ids(rare), drawn_ids(big_hands) & ids(mangan)) == (
        500, True, set())


def test_big_hands_short_of_sanbaiman_and_above_says_so_rather_than_shrinking():
    # About what the logs of 3,000 games hold: a few thousand haneman and baiman, 22 hands above them.
    common = numbered(2000, han=6, limitTier="haneman")
    rare = numbered(8, 2000, han=11, limitTier="sanbaiman") + numbered(14, 2008, han=13, limitTier="yakuman")

    big_hands = shipped_drill("big-hands", common + rare)

    assert (len(big_hands.hand_ids), big_hands.target, big_hands.short_by) == (422, 500, 78)
    assert big_hands.shortfalls == [
        Shortfall(part="limitTier = sanbaiman/kazoe-yakuman/yakuman", wanted=100, found=22)]


def test_payments_takes_tsumo_hands_dealer_and_non_dealer_some_with_honba():
    non_dealer = numbered(300, tsumo=True, yaku=["menzen-tsumo"]) + numbered(100, 300, tsumo=True, honba=1)
    dealer = numbered(150, 400, tsumo=True, dealer=True) + numbered(50, 550, tsumo=True, dealer=True, honba=2)
    ron = numbered(300, 600, honba=1)

    payments = shipped_drill("payments", non_dealer + dealer + ron)

    drawn = drawn_ids(payments)
    assert (len(drawn), drawn & ids(ron)) == (500, set())
    assert drawn & ids(dealer) and drawn & ids(non_dealer) and drawn & ids(non_dealer[300:] + dealer[150:])


def situations(counts: dict[str, int]) -> dict[str, list[dict]]:
    """For each situational yaku, that many hands with it, numbered so no two hands share an ID."""
    hands, start = {}, 0
    for yaku, count in counts.items():
        hands[yaku] = numbered(count, start, yaku=["riichi", yaku], tsumo=yaku in ("haitei", "rinshan"))
        start += count
    return hands


def test_rare_situations_gives_haitei_houtei_rinshan_chankan_and_double_riichi_equal_shares_and_leaves_out_ippatsu():
    # In real games ippatsu outnumbers the others put together, and haitei and houtei outnumber chankan.
    hands = situations({"ippatsu": 3000, "haitei": 400, "houtei": 400, "rinshan": 300, "double-riichi": 150,
                        "chankan": 120})

    rare_situations = shipped_drill("rare-situations", [hand for group in hands.values() for hand in group])

    drawn = drawn_ids(rare_situations)
    assert {yaku: len(drawn & ids(group)) for yaku, group in hands.items()} == {
        "ippatsu": 0, "haitei": 100, "houtei": 100, "rinshan": 100, "double-riichi": 100, "chankan": 100}


def test_rare_situations_short_of_chankan_says_so_and_is_not_filled_up_with_the_other_situations():
    hands = situations({"haitei": 400, "houtei": 400, "rinshan": 300, "double-riichi": 150, "chankan": 12})

    rare_situations = shipped_drill("rare-situations", [hand for group in hands.values() for hand in group])

    assert (len(rare_situations.hand_ids), rare_situations.short_by) == (412, 88)
    assert rare_situations.shortfalls == [Shortfall(part="yaku = chankan", wanted=100, found=12)]
