from ddbot.patterns.swings import swing_highs, swing_lows


def test_swing_lows_finds_the_two_bottoms():
    lows = [110, 108, 106, 104, 102, 100, 102, 104, 106, 108,
            110, 108, 106, 104, 102, 100.5, 103, 101]
    assert swing_lows(lows, k=2) == [5, 15]


def test_swing_highs_finds_the_peak():
    highs = [1, 2, 3, 4, 5, 4, 3, 2, 1]
    assert swing_highs(highs, k=2) == [4]


def test_edges_are_never_swings():
    # Bars within k of either end can't be evaluated.
    lows = [1, 2, 3]
    assert swing_lows(lows, k=2) == []
