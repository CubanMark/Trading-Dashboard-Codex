from pathlib import Path
from uuid import uuid4

from trading_dashboard.data.universe import load_equity_universe, normalize_yahoo_symbol


def test_universe_loader_filters_and_normalizes_symbols():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    path = tmp_dir / f"universe-{uuid4().hex}.csv"
    path.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "BRK.B,Berkshire,Financials,Multi-Sector Holdings,S&P 500,300,100,100000000,True\n"
        "XYZ,Example,Technology,Software,S&P 600,300,100,100000000,False\n",
        encoding="utf-8",
    )
    rows = load_equity_universe(path)
    assert [row["symbol"] for row in rows] == ["BRK-B"]
    assert rows[0]["sector"] == "Financials"


def test_normalize_yahoo_symbol_replaces_dot_with_dash():
    assert normalize_yahoo_symbol("BRK.B") == "BRK-B"
