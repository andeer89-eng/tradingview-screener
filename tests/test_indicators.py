"""Tests for indicator modules."""

import numpy as np
import pandas as pd
import pytest

from src.indicators.rsi import RSIIndicator
from src.indicators.macd import MACDIndicator
from src.indicators.bb import BollingerBands
from src.indicators.supertrend import SuperTrend
from src.indicators.custom import CustomSignalEngine


@pytest.fixture
def sample_data():
    """Generate deterministic OHLCV sample data."""
    rng = np.random.default_rng(42)
    n = 200
    returns = rng.normal(0.0002, 0.015, n)
    close = 100.0 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.008, n)))
    volume = rng.integers(100_000, 5_000_000, n).astype(float)
    idx = pd.date_range("2023-01-01", periods=n, freq="h")
    return pd.DataFrame({
        "high": high, "low": low, "close": close, "volume": volume,
    }, index=idx)


def test_rsi_range(sample_data):
    rsi = RSIIndicator()
    result = rsi.calculate(sample_data["close"])
    valid = result.values.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
    assert result.signal is not None


def test_macd_output(sample_data):
    macd = MACDIndicator()
    result = macd.calculate(sample_data["close"])
    assert len(result.macd) == len(sample_data)
    assert len(result.histogram) == len(sample_data)
    assert result.event is not None


def test_bollinger_bands(sample_data):
    bb = BollingerBands()
    result = bb.calculate(sample_data["close"])
    valid_idx = result.upper.dropna().index
    assert (result.upper[valid_idx] >= result.middle[valid_idx]).all()
    assert (result.middle[valid_idx] >= result.lower[valid_idx]).all()


def test_supertrend(sample_data):
    st = SuperTrend()
    result = st.calculate(sample_data["high"], sample_data["low"], sample_data["close"])
    assert result.signal is not None
    assert 0.0 <= result.strength <= 1.0


def test_composite_engine(sample_data):
    engine = CustomSignalEngine()
    result = engine.run(
        high=sample_data["high"],
        low=sample_data["low"],
        close=sample_data["close"],
        volume=sample_data["volume"],
    )
    assert -1.0 <= result.score <= 1.0
    assert result.rating in ("STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL")
    assert result.rsi_signal is not None
    assert result.macd_signal is not None
