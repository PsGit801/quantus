import pandas as pd

from ddbot.data.yahoo import YahooDataProvider


def test_get_ohlcv_retries_then_succeeds(monkeypatch):
    """A transient failure should be retried, not skip the ticker."""
    calls = {"n": 0}

    def fake_download(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("transient DNS blip")
        idx = pd.date_range("2024-01-01", periods=5, freq="D")
        return pd.DataFrame(
            {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 100},
            index=idx,
        )

    import yfinance
    monkeypatch.setattr(yfinance, "download", fake_download)
    monkeypatch.setattr("time.sleep", lambda *_: None)  # don't actually wait

    df = YahooDataProvider(drop_forming_bar=False).get_ohlcv("AAPL", "1d", 90)
    assert calls["n"] == 2          # failed once, succeeded on retry
    assert not df.empty and list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_get_ohlcv_returns_empty_after_all_retries_fail(monkeypatch):
    def always_fail(*a, **k):
        raise ConnectionError("down")

    import yfinance
    monkeypatch.setattr(yfinance, "download", always_fail)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    df = YahooDataProvider().get_ohlcv("AAPL", "1d", 90)
    assert df.empty
