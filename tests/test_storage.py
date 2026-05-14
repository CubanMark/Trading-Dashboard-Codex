from pathlib import Path
from uuid import uuid4

import pandas as pd

from trading_dashboard.data.storage import connect, init_db, upsert_prices


def test_price_upsert_does_not_duplicate():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"test-{uuid4().hex}.sqlite3"
    init_db(db)
    rows = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "date": "2026-01-02",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1000,
            }
        ]
    )
    upsert_prices(db, rows, "test")
    rows.loc[0, "close"] = 101.5
    upsert_prices(db, rows, "test")
    with connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
        close = conn.execute("SELECT close FROM prices WHERE symbol = 'SPY'").fetchone()["close"]
    assert count == 1
    assert close == 101.5
