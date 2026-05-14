from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    asset_class TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    source TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    action_type TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date, action_type)
);

CREATE TABLE IF NOT EXISTS macro_series (
    series_id TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    note TEXT,
    PRIMARY KEY (series_id, date)
);

CREATE TABLE IF NOT EXISTS dimension_metrics (
    metric_id TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL,
    prior_value REAL,
    change_1w REAL,
    label TEXT,
    status TEXT NOT NULL,
    trend TEXT,
    note TEXT,
    PRIMARY KEY (metric_id, date)
);

CREATE TABLE IF NOT EXISTS sector_returns (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    sector TEXT NOT NULL,
    return_1w REAL,
    return_1m REAL,
    status TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS industry_returns (
    industry TEXT NOT NULL,
    date TEXT NOT NULL,
    sector TEXT,
    return_1w REAL,
    return_1m REAL,
    constituents INTEGER NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (industry, date)
);

CREATE TABLE IF NOT EXISTS scanner_hits (
    scanner_id TEXT NOT NULL,
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    scanner_label TEXT,
    sector TEXT,
    industry TEXT,
    rs_rank REAL,
    perf_1w REAL,
    perf_1m REAL,
    atr_pct REAL,
    ma_distance_pct REAL,
    avg_volume_50d REAL,
    distance_to_52w_high REAL,
    also_in TEXT,
    trigger_note TEXT,
    warning TEXT NOT NULL,
    PRIMARY KEY (scanner_id, date, symbol)
);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    step TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        ensure_column(conn, "dimension_metrics", "prior_value", "REAL")
        ensure_column(conn, "dimension_metrics", "change_1w", "REAL")
        ensure_column(conn, "sector_returns", "return_1w", "REAL")
        ensure_column(conn, "industry_returns", "return_1w", "REAL")
        ensure_column(conn, "scanner_hits", "scanner_label", "TEXT")
        ensure_column(conn, "scanner_hits", "perf_1w", "REAL")
        ensure_column(conn, "scanner_hits", "ma_distance_pct", "REAL")
        ensure_column(conn, "scanner_hits", "also_in", "TEXT")
        ensure_column(conn, "scanner_hits", "trigger_note", "TEXT")


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log_run(db_path: Path, step: str, status: str, message: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO run_log (run_at, step, status, message) VALUES (?, ?, ?, ?)",
            (now_utc(), step, status, message),
        )


def log_quality(db_path: Path, check_name: str, status: str, message: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO data_quality_checks (checked_at, check_name, status, message) VALUES (?, ?, ?, ?)",
            (now_utc(), check_name, status, message),
        )


def upsert_symbols(db_path: Path, rows: Iterable[dict]) -> None:
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO symbols (symbol, name, asset_class, sector, industry, source, active)
            VALUES (:symbol, :name, :asset_class, :sector, :industry, :source, :active)
            ON CONFLICT(symbol) DO UPDATE SET
              name=excluded.name,
              asset_class=excluded.asset_class,
              sector=excluded.sector,
              industry=excluded.industry,
              source=excluded.source,
              active=excluded.active
            """,
            list(rows),
        )


def upsert_prices(db_path: Path, prices: pd.DataFrame, source: str) -> None:
    if prices.empty:
        return
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["source"] = source
    cols = ["symbol", "date", "open", "high", "low", "close", "volume", "source"]
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO prices (symbol, date, open, high, low, close, volume, source)
            VALUES (:symbol, :date, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT(symbol, date) DO UPDATE SET
              open=excluded.open,
              high=excluded.high,
              low=excluded.low,
              close=excluded.close,
              volume=excluded.volume,
              source=excluded.source
            """,
            frame[cols].to_dict("records"),
        )


def replace_prices(db_path: Path, prices: pd.DataFrame, source: str, symbols: Iterable[str]) -> None:
    symbol_list = list(symbols)
    if not symbol_list:
        return
    marks = ",".join(["?"] * len(symbol_list))
    frame = prepare_prices(prices, source)
    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM prices WHERE symbol IN ({marks})", symbol_list)
        frame.to_sql("prices", conn, if_exists="append", index=False, chunksize=10000)


def prepare_prices(prices: pd.DataFrame, source: str) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume", "source"])
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["source"] = source
    return frame[["symbol", "date", "open", "high", "low", "close", "volume", "source"]]


def upsert_actions(db_path: Path, actions: pd.DataFrame, source: str) -> None:
    if actions.empty:
        return
    frame = actions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["source"] = source
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO corporate_actions (symbol, date, action_type, value, source)
            VALUES (:symbol, :date, :action_type, :value, :source)
            ON CONFLICT(symbol, date, action_type) DO UPDATE SET
              value=excluded.value,
              source=excluded.source
            """,
            frame[["symbol", "date", "action_type", "value", "source"]].to_dict("records"),
        )


def replace_actions(db_path: Path, actions: pd.DataFrame, source: str, symbols: Iterable[str]) -> None:
    symbol_list = list(symbols)
    if not symbol_list:
        return
    marks = ",".join(["?"] * len(symbol_list))
    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM corporate_actions WHERE symbol IN ({marks})", symbol_list)
    upsert_actions(db_path, actions, source)


def clear_computed_outputs(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM dimension_metrics")
        conn.execute("DELETE FROM sector_returns")
        conn.execute("DELETE FROM industry_returns")
        conn.execute("DELETE FROM scanner_hits")


def replace_table_rows(db_path: Path, table: str, rows: list[dict], key_where: str | None = None, key_args: tuple = ()) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join([f":{col}" for col in columns])
    col_list = ", ".join(columns)
    with connect(db_path) as conn:
        if key_where:
            conn.execute(f"DELETE FROM {table} WHERE {key_where}", key_args)
        conn.executemany(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", rows)


def read_prices(db_path: Path, symbols: list[str] | None = None) -> pd.DataFrame:
    sql = "SELECT symbol, date, open, high, low, close, volume FROM prices"
    params: list[str] = []
    if symbols:
        marks = ",".join(["?"] * len(symbols))
        sql += f" WHERE symbol IN ({marks})"
        params = symbols
    sql += " ORDER BY symbol, date"
    with connect(db_path) as conn:
        frame = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
    return frame
