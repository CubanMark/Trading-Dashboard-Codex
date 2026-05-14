from __future__ import annotations

import pandas as pd

from ..config import EXCLUDED_PULLBACK_SUB_INDUSTRIES, SYMBOL_SECTORS
from ..compute.indicators import atr, percentile_rank, sma

WARNING = "Research scanner only; Pullback-v2a is not accepted as a tradable edge."
SCANNER_LIMIT_PER_VARIANT = 25


def pullback_hits(
    price_map: dict[str, pd.DataFrame],
    latest_date: str,
    equity_symbols: list[str],
    metadata: dict[str, tuple[str | None, str | None]] | None = None,
) -> list[dict]:
    spy_ok = spy_market_regime(price_map)
    rows_by_scanner: dict[str, list[dict]] = {
        "pullback_3d_research": [],
        "pullback_ma10_research": [],
        "pullback_ma20_research": [],
    }
    perf_map: dict[str, float] = {}
    symbol_meta = metadata or symbol_metadata(equity_symbols)
    for symbol in equity_symbols:
        frame = price_map.get(symbol, empty_price_frame())
        if len(frame) >= 22:
            perf_map[symbol] = float(frame["close"].iloc[-1] / frame["close"].iloc[-22] - 1)
    ranks = percentile_rank(pd.Series(perf_map)) if perf_map else pd.Series(dtype=float)

    for symbol in equity_symbols:
        sector, industry = symbol_meta.get(symbol, SYMBOL_SECTORS.get(symbol, (None, None)))
        if industry in EXCLUDED_PULLBACK_SUB_INDUSTRIES:
            continue
        frame = price_map.get(symbol, empty_price_frame())
        for scanner_id, label, ma_window, trigger_note in matching_pullback_variants(frame, spy_ok):
            rows_by_scanner[scanner_id].append(
                hit_row(symbol, latest_date, frame, ranks.get(symbol), sector, industry, scanner_id, label, ma_window, trigger_note)
            )
    rows: list[dict] = []
    for scanner_rows in rows_by_scanner.values():
        rows.extend(sorted(scanner_rows, key=lambda row: (row["rs_rank"] or 0), reverse=True)[:SCANNER_LIMIT_PER_VARIANT])
    return annotate_overlaps(rows)


def annotate_overlaps(rows: list[dict]) -> list[dict]:
    labels_by_symbol: dict[str, set[str]] = {}
    for row in rows:
        labels_by_symbol.setdefault(row["symbol"], set()).add(row["scanner_label"])
    for row in rows:
        other_labels = sorted(labels_by_symbol.get(row["symbol"], set()) - {row["scanner_label"]})
        row["also_in"] = ", ".join(other_labels)
    return rows


def symbol_metadata(equity_symbols: list[str]) -> dict[str, tuple[str | None, str | None]]:
    # Metadata is currently sourced from symbols during rendering/fetch; this fallback keeps scanner pure.
    return {symbol: SYMBOL_SECTORS.get(symbol, (None, None)) for symbol in equity_symbols}


def empty_price_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])


def spy_market_regime(price_map: dict[str, pd.DataFrame]) -> bool:
    spy = price_map.get("SPY", empty_price_frame())
    if len(spy) < 200:
        return False
    ma200 = sma(spy["close"], 200)
    return bool(pd.notna(ma200.iloc[-1]) and spy["close"].iloc[-1] > ma200.iloc[-1])


def is_pullback_candidate(frame: pd.DataFrame, spy_ok: bool) -> bool:
    if not spy_ok or len(frame) < 252:
        return False
    close = frame["close"]
    ma50 = sma(close, 50)
    ma200 = sma(close, 200)
    if pd.isna(ma50.iloc[-1]) or pd.isna(ma200.iloc[-1]):
        return False
    trend_ok = close.iloc[-1] > ma50.iloc[-1] > ma200.iloc[-1]
    three_down = close.iloc[-1] < close.iloc[-2] < close.iloc[-3] < close.iloc[-4]
    return bool(trend_ok and three_down)


def matching_pullback_variants(frame: pd.DataFrame, spy_ok: bool) -> list[tuple[str, str, int | None, str]]:
    if not base_uptrend_ok(frame, spy_ok):
        return []
    matches: list[tuple[str, str, int | None, str]] = []
    close = frame["close"]
    if len(frame) >= 4 and close.iloc[-1] < close.iloc[-2] < close.iloc[-3] < close.iloc[-4]:
        matches.append(("pullback_3d_research", "3D Pullback", None, "3 lower closes in an uptrend"))
    if near_moving_average(frame, 10):
        matches.append(("pullback_ma10_research", "Pullback MA10", 10, "Close near SMA10 in an uptrend"))
    if near_moving_average(frame, 20):
        matches.append(("pullback_ma20_research", "Pullback MA20", 20, "Close near SMA20 in an uptrend"))
    return matches


def base_uptrend_ok(frame: pd.DataFrame, spy_ok: bool) -> bool:
    if not spy_ok or len(frame) < 252:
        return False
    close = frame["close"]
    ma50 = sma(close, 50)
    ma200 = sma(close, 200)
    if pd.isna(ma50.iloc[-1]) or pd.isna(ma200.iloc[-1]):
        return False
    return bool(close.iloc[-1] > ma50.iloc[-1] > ma200.iloc[-1])


def near_moving_average(frame: pd.DataFrame, window: int, max_distance_pct: float = 0.02) -> bool:
    if len(frame) < window:
        return False
    close = frame["close"]
    average = sma(close, window)
    if pd.isna(average.iloc[-1]) or average.iloc[-1] == 0:
        return False
    distance = abs(float(close.iloc[-1] / average.iloc[-1] - 1))
    recently_pulled_back = close.iloc[-1] < close.tail(10).max()
    return bool(distance <= max_distance_pct and recently_pulled_back)


def ma_distance_pct(frame: pd.DataFrame, window: int | None) -> float | None:
    if window is None or len(frame) < window:
        return None
    average = sma(frame["close"], window)
    if pd.isna(average.iloc[-1]) or average.iloc[-1] == 0:
        return None
    return float(frame["close"].iloc[-1] / average.iloc[-1] - 1)


def hit_row(
    symbol: str,
    latest_date: str,
    frame: pd.DataFrame,
    rs_rank: float | None,
    sector: str | None,
    industry: str | None,
    scanner_id: str,
    scanner_label: str,
    ma_window: int | None,
    trigger_note: str,
) -> dict:
    atr14 = atr(frame, 14)
    latest_close = float(frame["close"].iloc[-1])
    atr_pct = None if pd.isna(atr14.iloc[-1]) or latest_close == 0 else float(atr14.iloc[-1] / latest_close)
    perf_1w = None if len(frame) < 6 else float(latest_close / frame["close"].iloc[-6] - 1)
    perf_1m = None if len(frame) < 22 else float(latest_close / frame["close"].iloc[-22] - 1)
    avg_volume = None if len(frame) < 50 else float(frame["volume"].tail(50).mean())
    high_52w = frame["high"].tail(252).max()
    distance = None if pd.isna(high_52w) or high_52w == 0 else float(latest_close / high_52w - 1)
    return {
        "scanner_id": scanner_id,
        "scanner_label": scanner_label,
        "date": latest_date,
        "symbol": symbol,
        "sector": sector,
        "industry": industry,
        "rs_rank": None if rs_rank is None or pd.isna(rs_rank) else float(rs_rank),
        "perf_1w": perf_1w,
        "perf_1m": perf_1m,
        "atr_pct": atr_pct,
        "ma_distance_pct": ma_distance_pct(frame, ma_window),
        "avg_volume_50d": avg_volume,
        "distance_to_52w_high": distance,
        "also_in": "",
        "trigger_note": trigger_note,
        "warning": WARNING,
    }
