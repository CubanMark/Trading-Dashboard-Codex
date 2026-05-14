from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def pct_change_over(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods)


def last_valid(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def percentile_rank(values: pd.Series) -> pd.Series:
    return values.rank(pct=True) * 100
