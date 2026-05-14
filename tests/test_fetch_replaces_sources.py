from pathlib import Path
from uuid import uuid4

import pandas as pd

from trading_dashboard.data.fetch import drop_current_session
from trading_dashboard.data.storage import connect, init_db, replace_prices


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


def test_drop_current_session_removes_unfinished_today_row():
    today = pd.Timestamp.today().normalize()
    yesterday = today - pd.Timedelta(days=1)
    frame = pd.DataFrame(
        [
            {"date": yesterday, "close": 100},
            {"date": today, "close": 101},
        ]
    )

    filtered = drop_current_session(frame)

    assert filtered["date"].tolist() == [yesterday]
