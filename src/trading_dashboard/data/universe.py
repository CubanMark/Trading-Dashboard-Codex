from __future__ import annotations

from pathlib import Path

import pandas as pd


SYMBOL_CLASSIFICATION_OVERRIDES = {
    "PINS": ("Technology Services", "Internet Software / Services"),
    "ULS": ("Commercial Services", "Miscellaneous Commercial Services"),
}


def load_equity_universe(path: Path) -> list[dict]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    required = {"ticker", "security", "gics_sector", "gics_sub_industry"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Universe file {path} is missing required columns: {sorted(required - set(frame.columns))}")
    if "passes" in frame.columns:
        frame = frame[frame["passes"].astype(bool)]
    rows: list[dict] = []
    for record in frame.to_dict("records"):
        symbol = normalize_yahoo_symbol(str(record["ticker"]))
        sector, industry = classification_for_symbol(
            symbol,
            clean_optional(record.get("gics_sector")),
            clean_optional(record.get("gics_sub_industry")),
        )
        rows.append(
            {
                "symbol": symbol,
                "name": str(record.get("security") or symbol),
                "asset_class": "equity",
                "sector": sector,
                "industry": industry,
                "source": "sp1500_universe_csv",
                "active": 1,
            }
        )
    return dedupe_rows(rows)


def classification_for_symbol(symbol: str, sector: str | None, industry: str | None) -> tuple[str | None, str | None]:
    return SYMBOL_CLASSIFICATION_OVERRIDES.get(symbol, (sector, industry))


def normalize_yahoo_symbol(ticker: str) -> str:
    return ticker.strip().replace(".", "-")


def clean_optional(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def dedupe_rows(rows: list[dict]) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for row in rows:
        by_symbol[row["symbol"]] = row
    return sorted(by_symbol.values(), key=lambda row: row["symbol"])
