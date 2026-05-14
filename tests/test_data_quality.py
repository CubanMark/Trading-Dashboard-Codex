from pathlib import Path
from uuid import uuid4

import pandas as pd

from trading_dashboard.config import Settings
from trading_dashboard.data.fetch import quality_check_prices
from trading_dashboard.data.storage import connect, init_db


def test_quality_check_logs_invalid_ohlc_and_universe_examples():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"quality-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "AAPL,Apple,Technology,Technology Hardware,S&P 500,300,100,100000000,True\n"
        "MSFT,Microsoft,Technology,Software,S&P 500,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    settings = Settings(db_path=db, universe_csv_path=universe, years=1)
    prices = pd.DataFrame(
        [
            price_row("AAPL", "2026-01-02", 10, 12, 9, 11),
            price_row("AAPL", "2026-01-05", 11, 10, 12, 11),
            price_row("AAPL", "2026-01-06", 11, 12, 9, -1),
        ]
    )

    quality_check_prices(settings, prices, pd.DataFrame(), "test")

    with connect(db) as conn:
        rows = {
            row["check_name"]: dict(row)
            for row in conn.execute("SELECT check_name, status, message FROM data_quality_checks")
        }
    assert rows["invalid_ohlc"]["status"] == "error"
    assert "AAPL" in rows["invalid_ohlc"]["message"]
    assert rows["nonpositive_prices"]["status"] == "error"
    assert rows["missing_symbols"]["status"] == "warning"
    assert "MSFT" in rows["missing_symbols"]["message"]
    assert rows["universe_coverage"]["status"] == "warning"
    assert "2 active equities expected; 1 loaded" in rows["universe_coverage"]["message"]


def test_quality_check_splits_extreme_returns_by_corporate_action():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"quality-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "AAPL,Apple,Technology,Technology Hardware,S&P 500,300,100,100000000,True\n"
        "MSFT,Microsoft,Technology,Software,S&P 500,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    settings = Settings(db_path=db, universe_csv_path=universe, years=1)
    prices = pd.DataFrame(
        [
            price_row("AAPL", "2026-01-02", 100, 101, 99, 100),
            price_row("AAPL", "2026-01-05", 45, 46, 44, 45),
            price_row("MSFT", "2026-01-02", 100, 101, 99, 100),
            price_row("MSFT", "2026-01-05", 40, 41, 39, 40),
        ]
    )
    actions = pd.DataFrame(
        [
            {"symbol": "AAPL", "date": "2026-01-05", "action_type": "split", "value": 2.0},
        ]
    )

    quality_check_prices(settings, prices, actions, "test")

    with connect(db) as conn:
        rows = {
            row["check_name"]: dict(row)
            for row in conn.execute("SELECT check_name, status, message FROM data_quality_checks")
        }
    assert rows["corporate_action_returns"]["status"] == "warning"
    assert "AAPL" in rows["corporate_action_returns"]["message"]
    assert rows["extreme_daily_returns"]["status"] == "warning"
    assert "MSFT" in rows["extreme_daily_returns"]["message"]
    assert "AAPL" not in rows["extreme_daily_returns"]["message"]
    assert rows["extreme_return_diagnostics"]["status"] == "warning"
    assert "corporate_action=1" in rows["extreme_return_diagnostics"]["message"]
    assert "likely_real_move=1" in rows["extreme_return_diagnostics"]["message"]


def test_quality_check_diagnoses_split_like_and_reversal_extremes():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"quality-{uuid4().hex}.sqlite3"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "AAPL,Apple,Technology,Technology Hardware,S&P 500,300,100,100000000,True\n"
        "MSFT,Microsoft,Technology,Software,S&P 500,300,100,100000000,True\n",
        encoding="utf-8",
    )
    init_db(db)
    settings = Settings(db_path=db, universe_csv_path=universe, years=1)
    prices = pd.DataFrame(
        [
            price_row("AAPL", "2026-01-02", 100, 101, 99, 100),
            price_row("AAPL", "2026-01-05", 49, 50, 48, 49),
            price_row("AAPL", "2026-01-06", 50, 51, 49, 50),
            price_row("MSFT", "2026-01-02", 100, 101, 99, 100),
            price_row("MSFT", "2026-01-05", 250, 251, 249, 250),
            price_row("MSFT", "2026-01-06", 102, 103, 101, 102),
        ]
    )

    quality_check_prices(settings, prices, pd.DataFrame(), "test")

    with connect(db) as conn:
        rows = {
            row["check_name"]: dict(row)
            for row in conn.execute("SELECT check_name, status, message FROM data_quality_checks")
        }
    assert rows["extreme_return_diagnostics"]["status"] == "warning"
    assert "missing_corporate_action=1" in rows["extreme_return_diagnostics"]["message"]
    assert "possible_data_error=1" in rows["extreme_return_diagnostics"]["message"]
    assert "AAPL 2026-01-05 -51.0%" in rows["extreme_return_diagnostics"]["message"]


def price_row(symbol: str, date: str, open_: float, high: float, low: float, close: float) -> dict:
    return {
        "symbol": symbol,
        "date": date,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1_000_000,
    }
