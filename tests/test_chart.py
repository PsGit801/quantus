import os

from _synthetic import TEST_CFG, confirmed_w

from ddbot.charts.chart import render
from ddbot.patterns.double_bottom import check_confirmation, detect


def test_render_produces_nonempty_png(tmp_path):
    df = confirmed_w()
    pattern = check_confirmation(detect(df, "TEST", "1d", TEST_CFG)[0], df, TEST_CFG)

    out = render(df, pattern, str(tmp_path))

    assert os.path.exists(out)
    assert out.endswith(".png")
    assert os.path.getsize(out) > 0
