from pathlib import Path
from uuid import uuid4

from trading_dashboard.cli import main


def test_mock_update_creates_db_and_html():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    db = tmp_dir / f"dashboard-{uuid4().hex}.sqlite3"
    pages = tmp_dir / f"pages-{uuid4().hex}"
    universe = tmp_dir / f"universe-{uuid4().hex}.csv"
    universe.write_text(
        "ticker,security,gics_sector,gics_sub_industry,index_membership,rows,last_close,median_dv_126d,passes\n"
        "AAPL,Apple,Technology,Technology Hardware,S&P 500,300,100,100000000,True\n"
        "MSFT,Microsoft,Technology,Software,S&P 500,300,100,100000000,True\n",
        encoding="utf-8",
    )
    assert main(["--db", str(db), "--pages", str(pages), "--universe", str(universe), "update", "--mock", "--years", "2"]) == 0
    assert db.exists()
    index = pages / "index.html"
    assert index.exists()
    html = index.read_text(encoding="utf-8")
    assert "Market Dashboard" in html
    assert "Industry Leadership" in html
    assert "Dimension Snapshot" not in html
    assert "research scanner only" in html
    assert "Price source: mock" in html
    assert "deterministic mock data" in html
    assert "grid-template-columns: repeat(auto-fill, 118px)" in html
    assert "syncFilterOptions" in html


def test_scanner_filter_markup_is_rendered():
    from trading_dashboard.render.html import render_hits_table

    html = render_hits_table(
        [
            {
                "scanner_label": "Pullback MA10",
                "scanner_id": "pullback_ma10_research",
                "symbol": "AAPL",
                "sector": "Technology",
                "industry": "Technology Hardware",
                "rs_rank": 90,
                "perf_1w": 0.02,
                "perf_1m": 0.05,
                "ma_distance_pct": -0.01,
                "atr_pct": 0.02,
                "distance_to_52w_high": -0.03,
                "also_in": "Pullback MA20",
                "trigger_note": "Close near SMA10 in an uptrend",
            },
            {
                "scanner_label": "Pullback MA20",
                "scanner_id": "pullback_ma20_research",
                "symbol": "MSFT",
                "sector": "Technology",
                "industry": "Software",
                "rs_rank": 85,
                "perf_1w": -0.01,
                "perf_1m": 0.03,
                "ma_distance_pct": 0.01,
                "atr_pct": 0.02,
                "distance_to_52w_high": -0.04,
                "also_in": "Pullback MA10",
                "trigger_note": "Close near SMA20 in an uptrend",
            },
        ]
    )
    assert "data-scanner-filter" in html
    assert "data-filter-key='scanner'" in html
    assert "data-filter-key='sector'" in html
    assert "data-filter-key='industry'" in html
    assert "All sectors" in html
    assert "All industries" in html
    assert "data-scanner='Pullback MA10'" in html
    assert "data-sector='Technology'" in html
    assert "data-industry='Technology Hardware'" in html
    assert "Pullback MA20" in html
    assert "Also In" in html
    assert "Industry" in html
    assert "class='tag tag-ma10'" in html
    assert "class='tag tag-ma20'" in html
    assert "class='tag-list'" in html
    assert "data-sort-key='perf_1w' data-sort-default='descending' title='Sort by 1W'>1W</button>" in html
    assert "data-sort-key='perf_1m' data-sort-default='descending' title='Sort by 1M'>1M</button>" in html
    assert "<th>Trigger</th>" not in html
    assert "data-tooltip='Close near SMA10 in an uptrend'" in html
    assert "data-sort-key='rs'" in html
    assert "data-sort-key='industry'" in html
    assert "data-sort-key='perf_1w'" in html
    assert "data-sort-key='perf_1m'" in html
    assert "data-sort-key='ma_distance'" in html
    assert "data-sort-cell='rs' data-sort-type='number' data-sort-value='90'" in html
    assert "data-sort-cell='industry' data-sort-type='text' data-sort-value='Technology Hardware'" in html
    assert "data-sort-cell='perf_1w' data-sort-type='number' data-sort-value='0.02'" in html


def test_sector_groups_split_positive_and_negative_weekly_returns():
    from trading_dashboard.render.html import render_sector_groups

    html = render_sector_groups(
        [
            {"symbol": "XLK", "sector": "Technology", "return_1w": 0.02, "return_1m": 0.05},
            {"symbol": "XLV", "sector": "Health Care", "return_1w": -0.01, "return_1m": -0.03},
        ]
    )
    assert "Positive 1W" in html
    assert "Negative 1W" in html
    assert html.index("XLK") < html.index("Negative 1W")
    assert html.index("XLV") > html.index("Negative 1W")
