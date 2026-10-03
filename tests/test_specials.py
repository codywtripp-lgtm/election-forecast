from pipeline.specials import all_boards, cycle_signal, parse_board


def test_boards_parse_every_cycle_with_sane_swings():
    df = all_boards()
    assert set(range(2017, 2027)) <= set(df["board_year"])
    assert df["swing"].between(-100, 100).all()
    # swing = special margin − presidential margin (rounded whole points on the boards)
    assert ((df["margin"] - df["pres_margin"] - df["swing"]).abs() <= 2).mean() > 0.95


def test_cycle_signal_uses_only_specials_before_cutoff():
    s = cycle_signal(all_boards(), 2018)
    assert s["n"] > 50 and 5 < s["median_swing"] < 15


def test_parse_2026_board_has_recent_rows():
    b = parse_board(2026)
    assert len(b) > 20 and b["date"].max().year == 2026
