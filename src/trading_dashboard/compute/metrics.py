from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd

from ..config import EXCLUDED_PULLBACK_SUB_INDUSTRIES, SECTOR_ETFS, Settings
from ..data.storage import clear_computed_outputs, connect, log_quality, read_prices
from ..scanners.pullback import pullback_hits
from .indicators import atr, last_valid, pct_change_over, sma

MIN_INDUSTRY_CONSTITUENTS = 3


def compute_all_metrics(settings: Settings) -> None:
    prices = read_prices(settings.db_path)
    if prices.empty:
        log_quality(settings.db_path, "compute_input", "error", "No prices available for compute step")
        return
    latest_date = prices["date"].max().strftime("%Y-%m-%d")
    equity_symbols = settings.equity_symbols
    price_map = price_frames_by_symbol(prices)
    symbol_meta = load_symbol_metadata(settings)
    log_compute_quality(settings, price_map, equity_symbols, symbol_meta)
    metric_rows = dimension_metric_rows(price_map, latest_date, equity_symbols)
    sector_rows = sector_return_rows(price_map, latest_date)
    scanner_rows = pullback_hits(price_map, latest_date, equity_symbols, symbol_meta)
    log_scanner_quality(settings, price_map, equity_symbols, symbol_meta, scanner_rows)
    industry_rows = industry_return_rows(price_map, latest_date, equity_symbols, symbol_meta)
    clear_computed_outputs(settings.db_path)
    write_compute_outputs(settings, metric_rows, sector_rows, industry_rows, scanner_rows, latest_date)


def price_frames_by_symbol(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        symbol: frame.sort_values("date").reset_index(drop=True)
        for symbol, frame in prices.groupby("symbol", sort=False)
    }


def dimension_metric_rows(price_map: dict[str, pd.DataFrame], latest_date: str, equity_symbols: list[str]) -> list[dict]:
    rows = [
        breadth_metric(price_map, latest_date, equity_symbols),
        sentiment_metric(latest_date),
        risk_metric(price_map, latest_date),
        credit_metric(latest_date),
        volatility_metric(price_map, latest_date),
        obos_metric(price_map, latest_date),
    ]
    return rows


def latest_symbol_frame(price_map: dict[str, pd.DataFrame], symbol: str) -> pd.DataFrame:
    return price_map.get(symbol, pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"]))


def traffic_light(value: float | None, green: bool, yellow: bool) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "na"
    if green:
        return "green"
    if yellow:
        return "yellow"
    return "red"


def metric(
    metric_id: str,
    date: str,
    value: float | None,
    label: str,
    status: str,
    trend: str,
    note: str,
    prior_value: float | None = None,
) -> dict:
    return {
        "metric_id": metric_id,
        "date": date,
        "value": value,
        "prior_value": prior_value,
        "change_1w": None if value is None or prior_value is None else value - prior_value,
        "label": label,
        "status": status,
        "trend": trend,
        "note": note,
    }


def breadth_metric(price_map: dict[str, pd.DataFrame], latest_date: str, equity_symbols: list[str]) -> dict:
    current = breadth_value(price_map, equity_symbols, 0)
    prior_result = breadth_value(price_map, equity_symbols, 5)
    if current is None:
        return metric("breadth_sp500_above_sma50", latest_date, None, "N/A", "na", "flat", "No equity universe data")
    value, valid_count = current
    prior = None if prior_result is None else prior_result[0]
    status = traffic_light(value, value > 60, 40 <= value <= 60)
    trend = trend_from_change(value, prior)
    return metric(
        "breadth_sp500_above_sma50",
        latest_date,
        value,
        f"{value:.0f}% > SMA50",
        status,
        trend,
        f"S&P 1500 liquid universe approximation; {valid_count}/{len(equity_symbols)} valid symbols",
        prior,
    )


def breadth_value(price_map: dict[str, pd.DataFrame], equity_symbols: list[str], lookback: int) -> tuple[float, int] | None:
    values: list[bool] = []
    for symbol in equity_symbols:
        frame = latest_symbol_frame(price_map, symbol)
        idx = len(frame) - 1 - lookback
        if idx < 49:
            continue
        ma50 = sma(frame["close"], 50)
        if pd.notna(ma50.iloc[idx]):
            values.append(bool(frame["close"].iloc[idx] > ma50.iloc[idx]))
    if not values:
        return None
    return sum(values) / len(values) * 100, len(values)


def sentiment_metric(latest_date: str) -> dict:
    return metric(
        "sentiment_fear_greed",
        latest_date,
        None,
        "Not available",
        "na",
        "flat",
        "Fear & Greed source is optional in Phase 1; no fallback value is fabricated",
    )


def risk_metric(price_map: dict[str, pd.DataFrame], latest_date: str) -> dict:
    xly = latest_symbol_frame(price_map, "XLY")
    xlp = latest_symbol_frame(price_map, "XLP")
    if xly.empty or xlp.empty:
        return metric("risk_xly_xlp_trend", latest_date, None, "N/A", "na", "flat", "Missing XLY or XLP")
    joined = xly[["date", "close"]].merge(xlp[["date", "close"]], on="date", suffixes=("_xly", "_xlp"))
    ratio = joined["close_xly"] / joined["close_xlp"]
    value = last_valid(ratio)
    prior = value_at_lookback(ratio, 5)
    change_20 = last_valid(pct_change_over(ratio, 20))
    if value is None or change_20 is None:
        return metric("risk_xly_xlp_trend", latest_date, None, "N/A", "na", "flat", "Insufficient XLY/XLP history")
    status = "green" if change_20 > 0 else "red"
    trend = trend_from_change(value, prior)
    return metric("risk_xly_xlp_trend", latest_date, value, f"XLY/XLP {value:.2f}", status, trend, f"20-day change {change_20:.2%}", prior)


def credit_metric(latest_date: str) -> dict:
    return metric(
        "credit_hy_oas",
        latest_date,
        None,
        "HY OAS N/A",
        "na",
        "flat",
        "FRED HY OAS is optional until an API key/source is configured",
    )


def volatility_metric(price_map: dict[str, pd.DataFrame], latest_date: str) -> dict:
    vix = latest_symbol_frame(price_map, "^VIX")
    vix3m = latest_symbol_frame(price_map, "^VIX3M")
    if vix.empty:
        return metric("volatility_vix", latest_date, None, "VIX N/A", "na", "flat", "Missing VIX")
    vix_value = float(vix["close"].iloc[-1])
    prior = value_at_lookback(vix["close"], 5)
    label = f"VIX {vix_value:.1f}"
    note = "VIX/VIX3M not available"
    status = "green" if vix_value < 20 else "yellow" if vix_value < 30 else "red"
    trend = trend_from_change(vix_value, prior)
    if not vix3m.empty:
        joined = vix[["date", "close"]].merge(vix3m[["date", "close"]], on="date", suffixes=("_vix", "_vix3m"))
        if not joined.empty and joined["close_vix3m"].iloc[-1] != 0:
            term = float(joined["close_vix"].iloc[-1] / joined["close_vix3m"].iloc[-1])
            label = f"VIX {vix_value:.1f}"
            note = f"VIX/VIX3M {term:.2f}"
            if term > 1:
                status = "red"
    return metric("volatility_vix", latest_date, vix_value, label, status, trend, note, prior)


def obos_metric(price_map: dict[str, pd.DataFrame], latest_date: str) -> dict:
    spy = latest_symbol_frame(price_map, "SPY")
    if len(spy) < 60:
        return metric("obos_spy_sma50_atr", latest_date, None, "N/A", "na", "flat", "Insufficient SPY history")
    ma50 = sma(spy["close"], 50)
    atr14 = atr(spy, 14)
    if pd.isna(ma50.iloc[-1]) or pd.isna(atr14.iloc[-1]) or atr14.iloc[-1] == 0:
        return metric("obos_spy_sma50_atr", latest_date, None, "N/A", "na", "flat", "Cannot compute SMA50/ATR")
    value = float((spy["close"].iloc[-1] - ma50.iloc[-1]) / atr14.iloc[-1])
    prior = None
    prior_idx = len(spy) - 6
    if prior_idx >= 49 and pd.notna(ma50.iloc[prior_idx]) and pd.notna(atr14.iloc[prior_idx]) and atr14.iloc[prior_idx] != 0:
        prior = float((spy["close"].iloc[prior_idx] - ma50.iloc[prior_idx]) / atr14.iloc[prior_idx])
    abs_value = abs(value)
    status = "green" if abs_value < 2 else "yellow" if abs_value < 3 else "red"
    trend = trend_from_change(value, prior)
    return metric("obos_spy_sma50_atr", latest_date, value, f"{value:.1f} ATR", status, trend, "SPY distance to SMA50 in ATR units", prior)


def sector_return_rows(price_map: dict[str, pd.DataFrame], latest_date: str) -> list[dict]:
    rows: list[dict] = []
    for symbol, sector in SECTOR_ETFS.items():
        frame = latest_symbol_frame(price_map, symbol)
        if len(frame) < 22:
            rows.append({"symbol": symbol, "date": latest_date, "sector": sector, "return_1w": None, "return_1m": None, "status": "na"})
            continue
        ret_1w = None if len(frame) < 6 else float(frame["close"].iloc[-1] / frame["close"].iloc[-6] - 1)
        ret_1m = float(frame["close"].iloc[-1] / frame["close"].iloc[-22] - 1)
        rows.append({"symbol": symbol, "date": latest_date, "sector": sector, "return_1w": ret_1w, "return_1m": ret_1m, "status": "ok"})
    return rows


def industry_return_rows(
    price_map: dict[str, pd.DataFrame],
    latest_date: str,
    equity_symbols: list[str],
    symbol_meta: dict[str, tuple[str | None, str | None]],
) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for symbol in equity_symbols:
        sector, industry = symbol_meta.get(symbol, (None, None))
        if not industry:
            continue
        frame = latest_symbol_frame(price_map, symbol)
        if len(frame) < 22:
            continue
        latest_close = frame["close"].iloc[-1]
        if pd.isna(latest_close) or latest_close == 0:
            continue
        ret_1w = None
        if len(frame) >= 6 and pd.notna(frame["close"].iloc[-6]) and frame["close"].iloc[-6] != 0:
            ret_1w = float(latest_close / frame["close"].iloc[-6] - 1)
        if pd.isna(frame["close"].iloc[-22]) or frame["close"].iloc[-22] == 0:
            continue
        ret_1m = float(latest_close / frame["close"].iloc[-22] - 1)
        grouped.setdefault(industry, []).append({"sector": sector, "return_1w": ret_1w, "return_1m": ret_1m})

    rows: list[dict] = []
    for industry, members in grouped.items():
        valid_1m = [row["return_1m"] for row in members if row["return_1m"] is not None and not math.isnan(row["return_1m"])]
        if len(valid_1m) < MIN_INDUSTRY_CONSTITUENTS:
            continue
        valid_1w = [row["return_1w"] for row in members if row["return_1w"] is not None and not math.isnan(row["return_1w"])]
        sectors = [row["sector"] for row in members if row["sector"]]
        sector = max(set(sectors), key=sectors.count) if sectors else None
        rows.append(
            {
                "industry": industry,
                "date": latest_date,
                "sector": sector,
                "return_1w": None if not valid_1w else sum(valid_1w) / len(valid_1w),
                "return_1m": sum(valid_1m) / len(valid_1m),
                "constituents": len(valid_1m),
                "status": "ok",
            }
        )
    return sorted(rows, key=lambda row: row["return_1m"], reverse=True)


def write_compute_outputs(
    settings: Settings,
    metric_rows: list[dict],
    sector_rows: list[dict],
    industry_rows: list[dict],
    scanner_rows: list[dict],
    latest_date: str,
) -> None:
    with connect(settings.db_path) as conn:
        conn.execute("DELETE FROM dimension_metrics WHERE date = ?", (latest_date,))
        conn.executemany(
            """
            INSERT INTO dimension_metrics (metric_id, date, value, prior_value, change_1w, label, status, trend, note)
            VALUES (:metric_id, :date, :value, :prior_value, :change_1w, :label, :status, :trend, :note)
            """,
            metric_rows,
        )
        conn.execute("DELETE FROM sector_returns WHERE date = ?", (latest_date,))
        conn.executemany(
            """
            INSERT INTO sector_returns (symbol, date, sector, return_1w, return_1m, status)
            VALUES (:symbol, :date, :sector, :return_1w, :return_1m, :status)
            """,
            sector_rows,
        )
        conn.execute("DELETE FROM industry_returns WHERE date = ?", (latest_date,))
        if industry_rows:
            conn.executemany(
                """
                INSERT INTO industry_returns (industry, date, sector, return_1w, return_1m, constituents, status)
                VALUES (:industry, :date, :sector, :return_1w, :return_1m, :constituents, :status)
                """,
                industry_rows,
            )
        conn.execute("DELETE FROM scanner_hits WHERE date = ?", (latest_date,))
        if scanner_rows:
            conn.executemany(
                """
                INSERT INTO scanner_hits (
                    scanner_id, date, symbol, scanner_label, sector, industry, rs_rank, perf_1w, perf_1m, atr_pct,
                    ma_distance_pct, avg_volume_50d, distance_to_52w_high, also_in, trigger_note, warning
                )
                VALUES (
                    :scanner_id, :date, :symbol, :scanner_label, :sector, :industry, :rs_rank, :perf_1w, :perf_1m,
                    :atr_pct, :ma_distance_pct, :avg_volume_50d, :distance_to_52w_high, :also_in, :trigger_note, :warning
                )
                """,
                scanner_rows,
            )
    log_quality(settings.db_path, "compute_complete", "ok", f"Computed outputs for {latest_date} at {datetime.now(timezone.utc).isoformat()}")


def load_symbol_metadata(settings: Settings) -> dict[str, tuple[str | None, str | None]]:
    with connect(settings.db_path) as conn:
        rows = conn.execute("SELECT symbol, sector, industry FROM symbols WHERE asset_class = 'equity' AND active = 1").fetchall()
    return {row["symbol"]: (row["sector"], row["industry"]) for row in rows}


def log_compute_quality(
    settings: Settings,
    price_map: dict[str, pd.DataFrame],
    equity_symbols: list[str],
    symbol_meta: dict[str, tuple[str | None, str | None]],
) -> None:
    expected = set(equity_symbols)
    priced = {symbol for symbol in expected if symbol in price_map and not price_map[symbol].empty}
    sufficient = {
        symbol
        for symbol in priced
        if len(price_map[symbol]) >= 220 and pd.notna(price_map[symbol]["close"].iloc[-1])
    }
    missing = sorted(expected - priced)
    short = sorted(priced - sufficient)
    status = "ok" if not missing and len(sufficient) >= max(1, int(len(expected) * 0.90)) else "warning"
    log_quality(
        settings.db_path,
        "compute_universe_coverage",
        status,
        (
            f"{len(expected)} active equities; {len(priced)} priced; {len(sufficient)} with >= 220 rows"
            f"{quality_examples(missing, 'missing')}"
            f"{quality_examples(short, 'short')}"
        ),
    )

    missing_sector = sorted(symbol for symbol in expected if not symbol_meta.get(symbol, (None, None))[0])
    missing_industry = sorted(symbol for symbol in expected if not symbol_meta.get(symbol, (None, None))[1])
    mapping_status = "ok" if not missing_sector and not missing_industry else "warning"
    log_quality(
        settings.db_path,
        "symbol_mapping_coverage",
        mapping_status,
        (
            f"{len(missing_sector)} equities missing sector; {len(missing_industry)} missing industry"
            f"{quality_examples(missing_sector, 'sector')}"
            f"{quality_examples(missing_industry, 'industry')}"
        ),
    )


def quality_examples(values: list[str], label: str, limit: int = 5) -> str:
    if not values:
        return ""
    shown = ", ".join(values[:limit])
    more = "" if len(values) <= limit else f", +{len(values) - limit} more"
    return f"; {label}: {shown}{more}"


def log_scanner_quality(
    settings: Settings,
    price_map: dict[str, pd.DataFrame],
    equity_symbols: list[str],
    symbol_meta: dict[str, tuple[str | None, str | None]],
    scanner_rows: list[dict],
) -> None:
    excluded = [
        symbol
        for symbol in equity_symbols
        if symbol_meta.get(symbol, (None, None))[1] in EXCLUDED_PULLBACK_SUB_INDUSTRIES
    ]
    with_history = [
        symbol
        for symbol in equity_symbols
        if symbol not in excluded and len(price_map.get(symbol, pd.DataFrame())) >= 252
    ]
    missing_history = sorted(set(equity_symbols) - set(excluded) - set(with_history))
    log_quality(
        settings.db_path,
        "scanner_coverage",
        "ok" if not missing_history else "warning",
        (
            f"{len(with_history)} symbols scanned; {len(excluded)} excluded by industry; "
            f"{len(scanner_rows)} research hits"
            f"{quality_examples(missing_history, 'short_history')}"
        ),
    )


def value_at_lookback(series: pd.Series, lookback: int) -> float | None:
    valid = series.dropna()
    if len(valid) <= lookback:
        return None
    return float(valid.iloc[-1 - lookback])


def trend_from_change(value: float | None, prior: float | None) -> str:
    if value is None or prior is None:
        return "flat"
    if value > prior:
        return "up"
    if value < prior:
        return "down"
    return "flat"
