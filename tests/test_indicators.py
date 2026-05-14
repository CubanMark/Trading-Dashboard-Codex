import pandas as pd

from trading_dashboard.compute.indicators import atr, sma


def test_sma_uses_full_window():
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, 3)
    assert pd.isna(result.iloc[1])
    assert result.iloc[-1] == 4


def test_atr_computes_true_range_average():
    frame = pd.DataFrame(
        {
            "high": [11, 12, 13, 14],
            "low": [9, 10, 11, 12],
            "close": [10, 11, 12, 13],
        }
    )
    result = atr(frame, 2)
    assert pd.isna(result.iloc[0])
    assert result.iloc[-1] == 2
