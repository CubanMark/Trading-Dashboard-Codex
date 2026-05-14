from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..config import INDEX_SYMBOLS, SECTOR_ETFS, SYMBOL_SECTORS, Settings
from .storage import log_quality, log_run, replace_actions, replace_prices, upsert_symbols
from .universe import load_equity_universe


def fetch_prices(settings: Settings, use_mock: bool = False) -> None:
    upsert_symbols(settings.db_path, symbol_rows(settings))
    if use_mock:
        prices, actions = mock_prices(settings.all_price_symbols, settings.years)
        replace_prices(settings.db_path, prices, "mock", settings.all_price_symbols)
        replace_actions(settings.db_path, actions, "mock", settings.all_price_symbols)
        log_quality(settings.db_path, "fetch_source", "warning", "Used deterministic mock price data")
        return

    try:
        prices, actions = yfinance_prices(settings.all_price_symbols, settings.years)
    except Exception as exc:  # pragma: no cover - depends on network/provider
        log_run(settings.db_path, "fetch", "warning", f"yfinance failed: {exc}. Falling back to mock data.")
        prices, actions = mock_prices(settings.all_price_symbols, settings.years)
        source = "mock-fallback"
    else:
        source = "yfinance"

    replace_prices(settings.db_path, prices, source, settings.all_price_symbols)
    replace_actions(settings.db_path, actions, source, settings.all_price_symbols)
    quality_check_prices(settings, prices, source)


def symbol_rows(settings: Settings) -> list[dict]:
    rows: list[dict] = []
    equity_rows = load_equity_universe(settings.universe_csv_path)
    if not equity_rows:
        equity_rows = [
            symbol_row(symbol, symbol, "equity", *SYMBOL_SECTORS.get(symbol, (None, None)))
            for symbol in settings.equity_symbols
        ]
    rows.extend(equity_rows)
    for symbol in settings.all_price_symbols:
        if symbol in SECTOR_ETFS:
            sector = SECTOR_ETFS[symbol]
            rows.append(symbol_row(symbol, symbol, "sector_etf", sector, None))
        elif symbol in INDEX_SYMBOLS:
            rows.append(symbol_row(symbol, symbol, "index_macro", None, None))
    return rows


def symbol_row(symbol: str, name: str, asset_class: str, sector: str | None, industry: str | None) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "asset_class": asset_class,
        "sector": sector,
        "industry": industry,
        "source": "config",
        "active": 1,
    }


def yfinance_prices(symbols: list[str], years: int, batch_size: int = 80) -> tuple[pd.DataFrame, pd.DataFrame]:
    import yfinance as yf

    start = date.today() - timedelta(days=int(years * 365.25) + 80)
    price_frames: list[pd.DataFrame] = []
    action_rows: list[dict] = []
    for batch in chunks(symbols, batch_size):
        batch_prices, batch_actions = yfinance_batch(yf, batch, start)
        price_frames.extend(batch_prices)
        action_rows.extend(batch_actions)
    if not price_frames:
        raise RuntimeError("No usable yfinance price frames")
    return pd.concat(price_frames, ignore_index=True), pd.DataFrame(action_rows)


def yfinance_batch(yf, symbols: list[str], start: date) -> tuple[list[pd.DataFrame], list[dict]]:
    raw = yf.download(
        tickers=" ".join(symbols),
        start=start.isoformat(),
        auto_adjust=False,
        actions=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if raw.empty:
        return [], []

    price_frames: list[pd.DataFrame] = []
    action_rows: list[dict] = []
    for symbol in symbols:
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol not in raw.columns.get_level_values(0):
                continue
            part = raw[symbol].copy()
        else:
            part = raw.copy()
        part = part.rename(columns=str.lower)
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(part.columns):
            continue
        frame = part.reset_index().rename(columns={"Date": "date", "index": "date"})
        frame["symbol"] = symbol
        price_frames.append(frame[["symbol", "date", "open", "high", "low", "close", "volume"]].dropna(subset=["close"]))
        for action_col in ["dividends", "stock splits"]:
            if action_col in part.columns:
                nonzero = part[action_col].dropna()
                nonzero = nonzero[nonzero != 0]
                action_type = "dividend" if action_col == "dividends" else "split"
                for action_date, value in nonzero.items():
                    action_rows.append({"symbol": symbol, "date": action_date, "action_type": action_type, "value": float(value)})

    return price_frames, action_rows


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[idx : idx + size] for idx in range(0, len(values), size)]


def mock_prices(symbols: list[str], years: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    end = pd.Timestamp.today().normalize()
    periods = max(320, years * 252)
    dates = pd.bdate_range(end=end, periods=periods)
    frames: list[pd.DataFrame] = []
    for idx, symbol in enumerate(symbols):
        rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
        drift = 0.00015 + idx * 0.00001
        noise = rng.normal(drift, 0.012 + (idx % 5) * 0.001, len(dates))
        close = 100 * np.exp(np.cumsum(noise))
        high = close * (1 + rng.uniform(0.001, 0.018, len(dates)))
        low = close * (1 - rng.uniform(0.001, 0.018, len(dates)))
        open_ = close * (1 + rng.normal(0, 0.004, len(dates)))
        volume = rng.integers(800_000, 10_000_000, len(dates))
        frames.append(
            pd.DataFrame(
                {
                    "symbol": symbol,
                    "date": dates,
                    "open": open_,
                    "high": np.maximum.reduce([open_, high, close]),
                    "low": np.minimum.reduce([open_, low, close]),
                    "close": close,
                    "volume": volume,
                }
            )
        )
    return pd.concat(frames, ignore_index=True), pd.DataFrame(columns=["symbol", "date", "action_type", "value"])


def quality_check_prices(settings: Settings, prices: pd.DataFrame, source: str) -> None:
    if prices.empty:
        log_quality(settings.db_path, "prices_present", "error", f"No prices from {source}")
        return
    missing_close = int(prices["close"].isna().sum())
    status = "ok" if missing_close == 0 else "warning"
    log_quality(settings.db_path, "missing_close", status, f"{missing_close} missing close values from {source}")
    fetched_symbols = set(prices["symbol"].unique())
    missing_symbols = sorted(set(settings.all_price_symbols) - fetched_symbols)
    log_quality(
        settings.db_path,
        "missing_symbols",
        "ok" if not missing_symbols else "warning",
        f"{len(missing_symbols)} symbols missing from {source}",
    )
    latest_by_symbol = prices.groupby("symbol")["date"].max()
    stale = latest_by_symbol[latest_by_symbol < latest_by_symbol.max() - pd.Timedelta(days=10)]
    log_quality(settings.db_path, "stale_symbols", "ok" if stale.empty else "warning", f"{len(stale)} stale symbols")
