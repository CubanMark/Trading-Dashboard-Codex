from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..config import INDEX_SYMBOLS, SECTOR_ETFS, SYMBOL_SECTORS, Settings
from .storage import log_quality, log_run, replace_actions, replace_extreme_return_events, replace_prices, replace_sentiment_rows, upsert_symbols
from .universe import load_equity_universe

COMMON_SPLIT_RATIOS = (2.0, 3.0, 4.0, 5.0, 10.0)


def fetch_prices(settings: Settings, use_mock: bool = False) -> None:
    upsert_symbols(settings.db_path, symbol_rows(settings))
    if use_mock:
        prices, actions = mock_prices(settings.all_price_symbols, settings.years)
        replace_prices(settings.db_path, prices, "mock", settings.all_price_symbols)
        replace_actions(settings.db_path, actions, "mock", settings.all_price_symbols)
        log_quality(settings.db_path, "fetch_source", "warning", "Used deterministic mock price data")
        quality_check_prices(settings, prices, actions, "mock")
        fetch_sentiment(settings.db_path, settings.years, use_mock=True)
        return

    try:
        prices, actions = yfinance_prices(settings.all_price_symbols, settings.years)
    except Exception as exc:  # pragma: no cover - depends on network/provider
        log_run(settings.db_path, "fetch", "warning", f"yfinance failed: {exc}. Falling back to mock data.")
        prices, actions = mock_prices(settings.all_price_symbols, settings.years)
        source = "mock-fallback"
    else:
        source = "yfinance"

    replacement_symbols = settings.all_price_symbols if source == "mock-fallback" else fetched_symbols(prices)
    replace_prices(settings.db_path, prices, source, replacement_symbols)
    replace_actions(settings.db_path, actions, source, replacement_symbols)
    quality_check_prices(settings, prices, actions, source)
    fetch_sentiment(settings.db_path, settings.years, use_mock=(source == "mock-fallback"))


def fetch_sentiment(db_path: "Path", years: int, use_mock: bool = False) -> None:
    if use_mock:
        replace_sentiment_rows(db_path, mock_sentiment_rows(years))
        return
    try:
        rows = cnn_fear_greed_rows(years)
        replace_sentiment_rows(db_path, rows)
        log_quality(db_path, "sentiment_fetch", "ok", f"{len(rows)} Fear & Greed rows from CNN")
    except Exception as exc:
        log_quality(db_path, "sentiment_fetch", "warning", f"CNN Fear & Greed fetch failed: {exc}")


def cnn_fear_greed_rows(years: int) -> list[dict]:
    import json
    import urllib.request

    start = date.today() - timedelta(days=min(365, int(years * 365.25)))
    url = f"https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start.isoformat()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
        "Origin": "https://edition.cnn.com",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    rows: list[dict] = []
    for point in payload.get("fear_and_greed_historical", {}).get("data", []):
        ts_ms = point.get("x")
        score = point.get("y")
        rating = point.get("rating", "")
        if ts_ms is None or score is None:
            continue
        date_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append({"date": date_str, "score": float(score), "rating": str(rating), "source": "cnn"})
    # CNN API can return two intraday entries for the current day; keep the last (most recent) per date
    deduped: dict[str, dict] = {}
    for row in rows:
        deduped[row["date"]] = row
    return sorted(deduped.values(), key=lambda r: r["date"])


def _fg_rating(score: float) -> str:
    if score <= 25:
        return "Extreme Fear"
    if score <= 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


def mock_sentiment_rows(years: int) -> list[dict]:
    end = pd.Timestamp.today().normalize()
    periods = min(252, max(22, int(min(1, years) * 252)))
    dates = pd.bdate_range(end=end, periods=periods)
    rng = np.random.default_rng(42)
    scores = np.clip(50 + np.cumsum(rng.normal(0, 1.5, len(dates))), 5, 95)
    return [
        {"date": d.strftime("%Y-%m-%d"), "score": float(s), "rating": _fg_rating(float(s)), "source": "mock"}
        for d, s in zip(dates, scores)
    ]


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
        try:
            batch_prices, batch_actions = yfinance_batch(yf, batch, start)
        except Exception:
            batch_prices, batch_actions = [], []
        price_frames.extend(batch_prices)
        action_rows.extend(batch_actions)
    fetched = {str(frame["symbol"].iloc[0]) for frame in price_frames if not frame.empty}
    missing_after_batches = [symbol for symbol in symbols if symbol not in fetched]
    for symbol in missing_after_batches:
        try:
            retry_prices, retry_actions = yfinance_batch(yf, [symbol], start)
        except Exception:
            retry_prices, retry_actions = [], []
        if retry_prices:
            price_frames.extend(retry_prices)
            action_rows.extend(retry_actions)
    if not price_frames:
        raise RuntimeError("No usable yfinance price frames")
    return pd.concat(price_frames, ignore_index=True), pd.DataFrame(action_rows)


def fetched_symbols(prices: pd.DataFrame) -> list[str]:
    if prices.empty or "symbol" not in prices.columns:
        return []
    return sorted(prices["symbol"].dropna().astype(str).unique().tolist())


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
        frame = drop_unfinished_session(frame)
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


def drop_unfinished_session(
    frame: pd.DataFrame,
    now: datetime | None = None,
    cutoff: time = time(17, 30),
) -> pd.DataFrame:
    now_et = now_in_new_york(now)
    if now_et.time() >= cutoff:
        return frame.copy()
    today = pd.Timestamp(now_et.date())
    dates = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    return frame.loc[dates < today].copy()


def now_in_new_york(now: datetime | None = None) -> datetime:
    zone = ZoneInfo("America/New_York")
    current = now or datetime.now(tz=zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
    return current.astimezone(zone)


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


def quality_check_prices(settings: Settings, prices: pd.DataFrame, actions: pd.DataFrame | None, source: str) -> None:
    if prices.empty:
        log_quality(settings.db_path, "prices_present", "error", f"No prices from {source}")
        return
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    log_quality(settings.db_path, "prices_present", "ok", f"{len(prices)} price rows from {source}")

    missing_close = int(prices["close"].isna().sum())
    status = "ok" if missing_close == 0 else "warning"
    log_quality(settings.db_path, "missing_close", status, f"{missing_close} missing close values from {source}")

    fetched_symbols = set(prices["symbol"].unique())
    missing_symbols = sorted(set(settings.all_price_symbols) - fetched_symbols)
    log_quality(
        settings.db_path,
        "missing_symbols",
        "ok" if not missing_symbols else "warning",
        f"{len(missing_symbols)} symbols missing from {source} after batch and single-symbol retry{example_suffix(missing_symbols)}",
    )

    latest_by_symbol = prices.groupby("symbol")["date"].max()
    stale = latest_by_symbol[latest_by_symbol < latest_by_symbol.max() - pd.Timedelta(days=10)]
    stale_symbols = sorted(stale.index.astype(str).tolist())
    log_quality(
        settings.db_path,
        "stale_symbols",
        "ok" if stale.empty else "warning",
        f"{len(stale_symbols)} stale symbols{example_suffix(stale_symbols)}",
    )

    price_cols = ["open", "high", "low", "close"]
    nonpositive_mask = prices[price_cols].le(0).any(axis=1)
    nonpositive_symbols = sorted(prices.loc[nonpositive_mask, "symbol"].astype(str).unique().tolist())
    log_quality(
        settings.db_path,
        "nonpositive_prices",
        "ok" if not nonpositive_symbols else "error",
        f"{int(nonpositive_mask.sum())} rows with nonpositive OHLC values{example_suffix(nonpositive_symbols)}",
    )

    invalid_ohlc_mask = (
        prices["high"].lt(prices["low"])
        | prices["close"].lt(prices["low"])
        | prices["close"].gt(prices["high"])
        | prices["open"].lt(prices["low"])
        | prices["open"].gt(prices["high"])
    )
    invalid_ohlc_symbols = sorted(prices.loc[invalid_ohlc_mask, "symbol"].astype(str).unique().tolist())
    log_quality(
        settings.db_path,
        "invalid_ohlc",
        "ok" if not invalid_ohlc_symbols else "error",
        f"{int(invalid_ohlc_mask.sum())} rows with invalid OHLC relationships{example_suffix(invalid_ohlc_symbols)}",
    )

    sorted_prices = prices.sort_values(["symbol", "date"]).copy()
    grouped_closes = sorted_prices.groupby("symbol")["close"]
    sorted_prices["previous_close"] = grouped_closes.shift(1)
    sorted_prices["next_close"] = grouped_closes.shift(-1)
    sorted_prices["daily_return"] = grouped_closes.pct_change()
    extreme_mask = sorted_prices["daily_return"].abs().gt(0.50).fillna(False)
    extreme_rows = sorted_prices.loc[
        extreme_mask,
        ["symbol", "date", "open", "high", "low", "close", "volume", "previous_close", "next_close", "daily_return"],
    ].copy()
    action_related, unexplained = classify_extreme_returns(extreme_rows, actions)
    diagnostics = diagnose_extreme_returns(extreme_rows, actions)
    replace_extreme_return_events(settings.db_path, extreme_return_event_rows(diagnostics, source))
    log_quality(
        settings.db_path,
        "corporate_action_returns",
        "ok" if not action_related else "warning",
        (
            f"{len(action_related)} rows with absolute daily return > 50% near corporate actions"
            f"{example_suffix(action_related)}"
        ),
    )
    log_quality(
        settings.db_path,
        "extreme_daily_returns",
        "ok" if not unexplained else "warning",
        f"{len(unexplained)} unexplained rows with absolute daily return > 50%{example_suffix(unexplained)}",
    )
    log_quality(
        settings.db_path,
        "extreme_return_diagnostics",
        "ok" if not diagnostics else "warning",
        extreme_return_diagnostics_message(diagnostics),
    )

    equity_symbols = set(settings.equity_symbols)
    equity_counts = prices[prices["symbol"].isin(equity_symbols)].groupby("symbol").size()
    min_history = min(220, max(50, settings.years * 180))
    sufficient_history = int((equity_counts >= min_history).sum())
    missing_equities = sorted(equity_symbols - set(equity_counts.index))
    short_history = sorted(equity_counts[equity_counts < min_history].index.astype(str).tolist())
    status = "ok" if not missing_equities and not short_history else "warning"
    log_quality(
        settings.db_path,
        "universe_coverage",
        status,
        (
            f"{len(equity_symbols)} active equities expected; {len(equity_counts)} loaded; "
            f"{sufficient_history} with >= {min_history} rows"
            f"{example_suffix(missing_equities, 'missing')}"
            f"{example_suffix(short_history, 'short')}"
        ),
    )


def example_suffix(values: list[str], label: str = "examples", limit: int = 5) -> str:
    if not values:
        return ""
    shown = ", ".join(values[:limit])
    more = "" if len(values) <= limit else f", +{len(values) - limit} more"
    return f"; {label}: {shown}{more}"


def classify_extreme_returns(extreme_rows: pd.DataFrame, actions: pd.DataFrame | None) -> tuple[list[str], list[str]]:
    if extreme_rows.empty:
        return [], []
    action_keys = corporate_action_keys(actions)
    action_related: list[str] = []
    unexplained: list[str] = []
    for record in extreme_rows.to_dict("records"):
        symbol = str(record["symbol"])
        action_window = action_dates_around(record["date"])
        target = action_related if any((symbol, day) in action_keys for day in action_window) else unexplained
        target.append(extreme_return_label(record))
    return sorted(set(action_related)), sorted(set(unexplained))


def diagnose_extreme_returns(extreme_rows: pd.DataFrame, actions: pd.DataFrame | None) -> list[dict]:
    if extreme_rows.empty:
        return []
    action_keys = corporate_action_keys(actions)
    return [diagnose_extreme_return(record, action_keys) for record in extreme_rows.to_dict("records")]


def diagnose_extreme_return(record: dict, action_keys: set[tuple[str, str]]) -> dict:
    symbol = str(record["symbol"])
    date_value = record["date"]
    action_window = action_dates_around(date_value)
    if any((symbol, day) in action_keys for day in action_window):
        label = "corporate_action"
        note = "Corporate action found within +/- 1 day"
    elif is_split_like_move(record):
        label = "missing_corporate_action"
        note = "Close/previous close ratio resembles a common split ratio, but no action was fetched"
    elif is_one_day_reversal(record):
        label = "possible_data_error"
        note = "Extreme move reverses near the prior close on the next bar"
    else:
        label = "likely_real_move"
        note = "No split-like ratio or one-day reversal pattern detected"
    return {
        "symbol": symbol,
        "date": pd.Timestamp(date_value).strftime("%Y-%m-%d"),
        "daily_return": nullable_float(record.get("daily_return")),
        "previous_close": nullable_float(record.get("previous_close")),
        "close": nullable_float(record.get("close")),
        "next_close": nullable_float(record.get("next_close")),
        "label": label,
        "note": note,
        "example": extreme_return_label(record),
    }


def extreme_return_event_rows(diagnostics: list[dict], source: str) -> list[dict]:
    return [
        {
            "symbol": item["symbol"],
            "date": item["date"],
            "daily_return": item["daily_return"],
            "previous_close": item["previous_close"],
            "close": item["close"],
            "next_close": item["next_close"],
            "label": item["label"],
            "note": item["note"],
            "source": source,
        }
        for item in diagnostics
    ]


def nullable_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def extreme_return_diagnostics_message(diagnostics: list[dict]) -> str:
    if not diagnostics:
        return "0 extreme returns diagnosed"
    counts: dict[str, int] = {}
    examples_by_label: dict[str, list[str]] = {}
    for item in diagnostics:
        label = str(item["label"])
        counts[label] = counts.get(label, 0) + 1
        examples_by_label.setdefault(label, []).append(str(item["example"]))
    parts = [f"{len(diagnostics)} extreme returns diagnosed"]
    for label in ["missing_corporate_action", "possible_data_error", "corporate_action", "likely_real_move"]:
        if label in counts:
            parts.append(f"{label}={counts[label]}")
    priority_examples = examples_by_label.get("missing_corporate_action") or examples_by_label.get("possible_data_error") or examples_by_label.get("likely_real_move") or []
    return "; ".join(parts) + example_suffix(priority_examples)


def extreme_return_label(record: dict) -> str:
    symbol = str(record["symbol"])
    day = pd.Timestamp(record["date"]).strftime("%Y-%m-%d")
    daily_return = record.get("daily_return")
    if daily_return is None or pd.isna(daily_return):
        return f"{symbol} {day}"
    return f"{symbol} {day} {float(daily_return):+.1%}"


def is_split_like_move(record: dict) -> bool:
    previous_close = record.get("previous_close")
    close = record.get("close")
    if previous_close is None or close is None or pd.isna(previous_close) or pd.isna(close) or float(previous_close) <= 0:
        return False
    ratio = abs(float(close) / float(previous_close))
    if ratio <= 0:
        return False
    candidates = list(COMMON_SPLIT_RATIOS) + [1 / value for value in COMMON_SPLIT_RATIOS]
    return any(abs(ratio - candidate) / candidate <= 0.08 for candidate in candidates)


def is_one_day_reversal(record: dict) -> bool:
    previous_close = record.get("previous_close")
    close = record.get("close")
    next_close = record.get("next_close")
    if any(value is None or pd.isna(value) for value in [previous_close, close, next_close]):
        return False
    previous = float(previous_close)
    current = float(close)
    following = float(next_close)
    if previous <= 0 or current <= 0 or following <= 0:
        return False
    current_vs_previous = abs(current / previous - 1)
    following_vs_previous = abs(following / previous - 1)
    following_vs_current = abs(following / current - 1)
    return current_vs_previous > 0.50 and following_vs_previous < 0.20 and following_vs_current > 0.35


def corporate_action_keys(actions: pd.DataFrame | None) -> set[tuple[str, str]]:
    if actions is None or actions.empty:
        return set()
    frame = actions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    return {(str(row["symbol"]), str(row["date"])) for row in frame.to_dict("records")}


def action_dates_around(value: object) -> list[str]:
    day = pd.Timestamp(value).normalize()
    return [(day + pd.Timedelta(days=offset)).strftime("%Y-%m-%d") for offset in (-1, 0, 1)]
