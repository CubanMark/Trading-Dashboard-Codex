from pathlib import Path
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from trading_dashboard.data.fetch import drop_unfinished_session
from trading_dashboard.data.fetch import fetch_prices, symbols_by_fetch_start
from trading_dashboard.config import Settings
from trading_dashboard.data.storage import connect, init_db, replace_actions, replace_prices


def test_replace_prices_removes_prior_mock_rows_for_symbols():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"replace-{uuid4().hex}.sqlite3"
    init_db(db)
    replace_prices(
        db,
        pd.DataFrame(
            [
                price_row("SPY", "2026-05-14", 1000, "mock"),
                price_row("SPY", "2026-05-13", 990, "mock"),
            ]
        ).drop(columns=["source"]),
        "mock",
        ["SPY"],
    )
    replace_prices(
        db,
        pd.DataFrame([price_row("SPY", "2026-05-13", 700, "yfinance")]).drop(columns=["source"]),
        "yfinance",
        ["SPY"],
    )
    with connect(db) as conn:
        rows = [dict(row) for row in conn.execute("SELECT date, close, source FROM prices WHERE symbol = 'SPY' ORDER BY date")]
    assert rows == [{"date": "2026-05-13", "close": 700.0, "source": "yfinance"}]


def test_replace_prices_can_preserve_unfetched_symbol_history():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"preserve-{uuid4().hex}.sqlite3"
    init_db(db)
    replace_prices(
        db,
        pd.DataFrame(
            [
                price_row("ANF", "2026-05-13", 100, "yfinance"),
                price_row("SPY", "2026-05-13", 500, "yfinance"),
            ]
        ).drop(columns=["source"]),
        "yfinance",
        ["ANF", "SPY"],
    )
    replace_actions(db, pd.DataFrame(), "yfinance", ["ANF", "SPY"])

    replace_prices(
        db,
        pd.DataFrame([price_row("SPY", "2026-05-14", 510, "yfinance")]).drop(columns=["source"]),
        "yfinance",
        ["SPY"],
    )
    replace_actions(db, pd.DataFrame(), "yfinance", ["SPY"])

    with connect(db) as conn:
        rows = [
            dict(row)
            for row in conn.execute("SELECT symbol, date, close FROM prices ORDER BY symbol, date")
        ]
    assert rows == [
        {"symbol": "ANF", "date": "2026-05-13", "close": 100.0},
        {"symbol": "SPY", "date": "2026-05-14", "close": 510.0},
    ]


def test_symbols_by_fetch_start_uses_overlap_for_existing_symbols():
    grouped = symbols_by_fetch_start(
        ["ANF", "SPY"],
        years=5,
        latest_dates={"SPY": "2026-05-14"},
    )

    overlap_start = pd.Timestamp("2026-05-04").date()
    assert grouped[overlap_start] == ["SPY"]
    assert any("ANF" in symbols for start, symbols in grouped.items() if start != overlap_start)


def test_fetch_prices_upserts_yfinance_rows_without_replacing_history(monkeypatch):
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"incremental-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "ANF,Abercrombie,Consumer Discretionary,Specialty Retail,S&P 400,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    replace_prices(
        db,
        pd.DataFrame(
            [
                price_row("ANF", "2026-05-13", 100, "yfinance"),
                price_row("SPY", "2026-05-13", 500, "yfinance"),
            ]
        ).drop(columns=["source"]),
        "yfinance",
        ["ANF", "SPY"],
    )
    calls = {}

    def fake_yfinance_prices(symbols, years, batch_size=80, latest_dates=None):
        calls["latest_dates"] = latest_dates
        return (
            pd.DataFrame([price_row("SPY", "2026-05-14", 510, "yfinance")]).drop(columns=["source"]),
            pd.DataFrame(columns=["symbol", "date", "action_type", "value"]),
        )

    monkeypatch.setattr("trading_dashboard.data.fetch.yfinance_prices", fake_yfinance_prices)
    monkeypatch.setattr("trading_dashboard.data.fetch.fetch_sentiment", lambda *args, **kwargs: None)

    fetch_prices(Settings(db_path=db, universe_csv_path=universe, years=5))

    with connect(db) as conn:
        rows = [
            dict(row)
            for row in conn.execute("SELECT symbol, date, close FROM prices ORDER BY symbol, date")
        ]
    assert calls["latest_dates"]["ANF"] == "2026-05-13"
    assert calls["latest_dates"]["SPY"] == "2026-05-13"
    assert rows == [
        {"symbol": "ANF", "date": "2026-05-13", "close": 100.0},
        {"symbol": "SPY", "date": "2026-05-13", "close": 500.0},
        {"symbol": "SPY", "date": "2026-05-14", "close": 510.0},
    ]


def test_fetch_prices_keeps_existing_history_when_yfinance_fails(monkeypatch):
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"keep-existing-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "ANF,Abercrombie,Consumer Discretionary,Specialty Retail,S&P 400,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    replace_prices(
        db,
        pd.DataFrame([price_row("ANF", "2026-05-13", 100, "yfinance")]).drop(columns=["source"]),
        "yfinance",
        ["ANF"],
    )

    def fail_yfinance_prices(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr("trading_dashboard.data.fetch.yfinance_prices", fail_yfinance_prices)
    monkeypatch.setattr("trading_dashboard.data.fetch.fetch_sentiment", lambda *args, **kwargs: None)

    fetch_prices(Settings(db_path=db, universe_csv_path=universe, years=5))

    with connect(db) as conn:
        rows = [dict(row) for row in conn.execute("SELECT symbol, date, close, source FROM prices")]
    assert rows == [{"symbol": "ANF", "date": "2026-05-13", "close": 100.0, "source": "yfinance"}]


def test_fetch_prices_replaces_mock_bootstrap_history_with_first_yfinance_load(monkeypatch):
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"bootstrap-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "ANF,Abercrombie,Consumer Discretionary,Specialty Retail,S&P 400,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    replace_prices(
        db,
        pd.DataFrame(
            [
                price_row("ANF", "2026-05-13", 100, "mock"),
                price_row("ANF", "2026-05-14", 101, "mock"),
            ]
        ).drop(columns=["source"]),
        "mock",
        ["ANF"],
    )
    calls = {}

    def fake_yfinance_prices(symbols, years, batch_size=80, latest_dates=None):
        calls["latest_dates"] = latest_dates
        return (
            pd.DataFrame([price_row("ANF", "2026-05-12", 99, "yfinance")]).drop(columns=["source"]),
            pd.DataFrame(columns=["symbol", "date", "action_type", "value"]),
        )

    monkeypatch.setattr("trading_dashboard.data.fetch.yfinance_prices", fake_yfinance_prices)
    monkeypatch.setattr("trading_dashboard.data.fetch.fetch_sentiment", lambda *args, **kwargs: None)

    fetch_prices(Settings(db_path=db, universe_csv_path=universe, years=5))

    with connect(db) as conn:
        rows = [
            dict(row)
            for row in conn.execute("SELECT symbol, date, close, source FROM prices WHERE symbol = 'ANF' ORDER BY date")
        ]
    assert "ANF" not in calls["latest_dates"]
    assert rows == [{"symbol": "ANF", "date": "2026-05-12", "close": 99.0, "source": "yfinance"}]


def price_row(symbol: str, date: str, close: float, source: str) -> dict:
    return {
        "symbol": symbol,
        "date": date,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1_000_000,
        "source": source,
    }


def test_drop_unfinished_session_removes_today_before_new_york_cutoff():
    now = datetime(2026, 5, 14, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    today = pd.Timestamp("2026-05-14")
    yesterday = today - pd.Timedelta(days=1)
    frame = pd.DataFrame(
        [
            {"date": yesterday, "close": 100},
            {"date": today, "close": 101},
        ]
    )

    filtered = drop_unfinished_session(frame, now=now)

    assert filtered["date"].tolist() == [yesterday]


def test_drop_unfinished_session_keeps_today_after_new_york_cutoff():
    now = datetime(2026, 5, 14, 18, 0, tzinfo=ZoneInfo("America/New_York"))
    today = pd.Timestamp("2026-05-14")
    yesterday = today - pd.Timedelta(days=1)
    frame = pd.DataFrame(
        [
            {"date": yesterday, "close": 100},
            {"date": today, "close": 101},
        ]
    )

    filtered = drop_unfinished_session(frame, now=now)

    assert filtered["date"].tolist() == [yesterday, today]
