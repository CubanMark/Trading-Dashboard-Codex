from pathlib import Path
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from trading_dashboard.data.fetch import drop_unfinished_session
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
