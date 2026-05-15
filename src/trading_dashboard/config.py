from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "db" / "trading_dashboard.sqlite3"
PAGES_DIR = ROOT / "pages"
UNIVERSE_CSV_PATH = ROOT / "inputs" / "universe" / "sp1500_universe_filtered.csv"

INDEX_SYMBOLS = ["SPY", "QQQ", "IWM", "^VIX", "^VIX3M", "TLT", "HYG", "LQD"]
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLV": "Health Care",
    "XLF": "Financials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

DEFAULT_EQUITY_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "AVGO",
    "LLY",
    "JPM",
    "V",
    "XOM",
    "UNH",
    "MA",
    "COST",
    "HD",
]

SYMBOL_SECTORS = {
    "AAPL": ("Technology", "Technology Hardware"),
    "MSFT": ("Technology", "Software"),
    "NVDA": ("Technology", "Semiconductors"),
    "AMZN": ("Consumer Discretionary", "Broadline Retail"),
    "META": ("Communication Services", "Interactive Media"),
    "GOOGL": ("Communication Services", "Interactive Media"),
    "AVGO": ("Technology", "Semiconductors"),
    "LLY": ("Health Care", "Pharmaceuticals"),
    "JPM": ("Financials", "Diversified Banks"),
    "V": ("Financials", "Transaction Processing"),
    "XOM": ("Energy", "Integrated Oil"),
    "UNH": ("Health Care", "Managed Health Care"),
    "MA": ("Financials", "Transaction Processing"),
    "COST": ("Consumer Staples", "Consumer Staples Merchandise Retail"),
    "HD": ("Consumer Discretionary", "Home Improvement Retail"),
}

EXCLUDED_PULLBACK_SUB_INDUSTRIES = {
    "Biotechnology",
    "Pharmaceuticals",
    "Health Care Services",
    "Consumer Staples Merchandise Retail",
    "Diversified Banks",
    "Property & Casualty Insurance",
}


@dataclass(frozen=True)
class Settings:
    db_path: Path = DB_PATH
    pages_dir: Path = PAGES_DIR
    universe_csv_path: Path = UNIVERSE_CSV_PATH
    years: int = 5

    @property
    def equity_symbols(self) -> list[str]:
        from .data.universe import load_equity_universe

        rows = load_equity_universe(self.universe_csv_path)
        if rows:
            return sorted({row["symbol"] for row in rows})
        return DEFAULT_EQUITY_UNIVERSE

    @property
    def all_price_symbols(self) -> list[str]:
        return sorted(set(INDEX_SYMBOLS + list(SECTOR_ETFS) + self.equity_symbols))
