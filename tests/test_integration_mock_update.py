from pathlib import Path
import sqlite3
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
    assert "mock | data" in html
    assert "<span>Data:" not in html
    assert 'class="operation-status"' in html
    assert ".operation-status { margin-left: auto; text-align: right; font-size: 12px;" in html
    assert "equities 2/2" in html
    assert "OHLC ok" in html
    assert "deterministic mock data" in html
    assert 'class="market-state"' in html
    assert 'class="metric-grid"' in html
    assert "sector-heatmap" in html
    assert "sparkline" in html
    assert "syncFilterOptions" in html
    assert "&gt; SMA200" in html
    breadth = pages / "breadth.html"
    assert breadth.exists()
    breadth_html = breadth.read_text(encoding="utf-8")
    assert "Breadth History" in breadth_html
    assert "SMA50 Breadth" in breadth_html
    assert "SMA200 Breadth" in breadth_html
    assert "52W Highs / Lows" in breadth_html
    assert "Near 52W High" in breadth_html
    assert "Tactical participation" in breadth_html
    assert "Structural trend participation" in breadth_html
    assert "Leadership depth" in breadth_html
    assert "Momentum Breadth" in breadth_html
    assert "4% Up / Down" in breadth_html
    assert "5D 4% Ratio" in breadth_html
    assert "10D 4% Ratio" in breadth_html
    assert "25% Up / Down 3M" in breadth_html
    assert "50% Up / Down 1M" in breadth_html
    assert "Daily momentum thrust" in breadth_html
    assert "Breadth Composite" in breadth_html
    assert "composite-bar" in breadth_html
    assert "composite-score" in breadth_html
    assert "regime-pill" in breadth_html
    assert "composite-readout" in breadth_html
    assert "SPY vs Breadth Composite" in breadth_html
    assert "data-breadth-chart" in breadth_html
    assert "SPY indexed to 100" in breadth_html
    assert "Breadth Composite 5D avg" in breadth_html
    assert "Composite below 0 for 3+ days" in breadth_html
    assert "chart-negative-band" in breadth_html
    assert "info-dot" in breadth_html
    assert "data-breadth-history" in breadth_html
    assert "data-breadth-year-select" in breadth_html
    assert "data-breadth-year-count" in breadth_html
    assert "class='breadth-heatmap'" in breadth_html
    assert "Dashboard Breadth" in breadth_html
    assert "Stockbee-style Momentum" in breadth_html
    assert "group-composite" in breadth_html
    assert "stockbee-head" in breadth_html
    assert "Uncolored cells are normal range" in breadth_html
    assert "50% 1M is colored contrarian" in breadth_html
    assert "heat-light-red" in breadth_html
    assert "heat-neutral" in breadth_html
    assert "<th class='stockbee-head'>5D Ratio</th>" in breadth_html
    assert "10D Ratio" in breadth_html
    assert "50% 1M" in breadth_html
    assert ">Composite</th>" in breadth_html
    assert "valid symbols" not in breadth_html
    assert "&gt; SMA200" in breadth_html
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) AS n FROM breadth_daily").fetchone()["n"]
        latest = conn.execute(
            """
            SELECT
                pct_above_sma50, pct_above_sma200, valid_sma50,
                up_4pct, down_4pct, ratio_4pct_5d, ratio_4pct_10d,
                up_25pct_3m, down_25pct_3m, up_50pct_1m, down_50pct_1m, valid_momentum
            FROM breadth_daily
            ORDER BY date DESC
            LIMIT 1
            """
        ).fetchone()
    assert count > 0
    assert latest["pct_above_sma50"] is not None
    assert latest["pct_above_sma200"] is not None
    assert latest["valid_sma50"] == 2
    assert latest["up_4pct"] is not None
    assert latest["down_4pct"] is not None
    assert latest["up_25pct_3m"] is not None
    assert latest["down_25pct_3m"] is not None
    assert latest["up_50pct_1m"] is not None
    assert latest["down_50pct_1m"] is not None
    assert latest["valid_momentum"] == 2


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
                "ma_distance_atr": -0.42,
                "atr_pct": 0.02,
                "avg_volume_50d": 1_250_000,
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
                "ma_distance_atr": 0.35,
                "atr_pct": 0.02,
                "avg_volume_50d": 850_000,
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
    assert "data-filter-table" in html
    assert "data-sort-table" in html
    assert "data-visible-count data-count-label='hits'" in html
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
    assert "data-sort-key='avg_volume' data-sort-default='descending' title='Sort by Avg Vol'>Avg Vol</button>" in html
    assert "<th>Trigger</th>" not in html
    assert "data-tooltip='Close near SMA10 in an uptrend'" in html
    assert "data-sort-key='rs'" in html
    assert "data-sort-key='industry'" in html
    assert "data-sort-key='perf_1w'" in html
    assert "data-sort-key='perf_1m'" in html
    assert "data-sort-key='ma_distance_atr'" in html
    assert "data-sort-key='avg_volume'" in html
    assert "data-sort-cell='rs' data-sort-type='number' data-sort-value='90'" in html
    assert "data-sort-cell='industry' data-sort-type='text' data-sort-value='Technology Hardware'" in html
    assert "data-sort-cell='perf_1w' data-sort-type='number' data-sort-value='0.02'" in html
    assert "data-sort-cell='ma_distance_atr' data-sort-type='number' data-sort-value='-0.42'" in html
    assert "data-sort-cell='avg_volume' data-sort-type='number' data-sort-value='1250000'" in html
    assert "1.2M" in html


def test_breadth_history_renders_all_years_with_year_selector():
    from trading_dashboard.render.html import render_breadth_history

    rows = [
        {"date": "2025-12-31", "pct_above_sma50": 20, "pct_above_sma200": 30},
        {"date": "2026-01-02", "pct_above_sma50": 45, "pct_above_sma200": 50},
        {"date": "2026-02-03", "pct_above_sma50": 65, "pct_above_sma200": 60},
    ]

    html = render_breadth_history(rows)

    assert "data-breadth-year-select" in html
    assert "<option value='2026' selected>2026</option>" in html
    assert "<option value='2025'>2025</option>" in html
    assert "data-year='2025'" in html
    assert "12-31" in html
    assert "01-02" in html
    assert "02-03" in html


def test_breadth_composite_scores_heatmap_states():
    from trading_dashboard.render.html import breadth_composite_score

    strong_positive = {
        "pct_above_sma50": 70,
        "pct_above_sma200": 70,
        "new_highs_52w": 40,
        "new_lows_52w": 10,
        "pct_within_5pct_52w_high": 40,
        "up_4pct": 40,
        "down_4pct": 10,
        "ratio_4pct_5d": 2.0,
        "ratio_4pct_10d": 2.0,
        "up_25pct_3m": 200,
        "down_25pct_3m": 50,
        "up_50pct_1m": 0,
        "down_50pct_1m": 30,
    }
    strong_negative = {
        "pct_above_sma50": 20,
        "pct_above_sma200": 20,
        "new_highs_52w": 10,
        "new_lows_52w": 40,
        "pct_within_5pct_52w_high": 5,
        "up_4pct": 10,
        "down_4pct": 40,
        "ratio_4pct_5d": 0.3,
        "ratio_4pct_10d": 0.3,
        "up_25pct_3m": 50,
        "down_25pct_3m": 200,
        "up_50pct_1m": 30,
        "down_50pct_1m": 0,
    }

    assert breadth_composite_score(strong_positive) == 18
    assert breadth_composite_score(strong_negative) == -18


def test_breadth_composite_regime_annotation_identifies_healing_and_weakening():
    from trading_dashboard.render.html import annotate_breadth_regimes

    def row(date: str, score_shape: str) -> dict:
        if score_shape == "positive":
            return {
                "date": date,
                "pct_above_sma50": 70,
                "pct_above_sma200": 70,
                "new_highs_52w": 40,
                "new_lows_52w": 10,
                "pct_within_5pct_52w_high": 40,
                "up_4pct": 40,
                "down_4pct": 10,
                "ratio_4pct_5d": 2.0,
                "ratio_4pct_10d": 2.0,
                "up_25pct_3m": 200,
                "down_25pct_3m": 50,
                "up_50pct_1m": 0,
                "down_50pct_1m": 30,
            }
        if score_shape == "negative":
            return {
                "date": date,
                "pct_above_sma50": 20,
                "pct_above_sma200": 20,
                "new_highs_52w": 10,
                "new_lows_52w": 40,
                "pct_within_5pct_52w_high": 5,
                "up_4pct": 10,
                "down_4pct": 40,
                "ratio_4pct_5d": 0.3,
                "ratio_4pct_10d": 0.3,
                "up_25pct_3m": 50,
                "down_25pct_3m": 200,
                "up_50pct_1m": 30,
                "down_50pct_1m": 0,
            }
        return {
            "date": date,
            "pct_above_sma50": 50,
            "pct_above_sma200": 50,
            "new_highs_52w": 10,
            "new_lows_52w": 10,
            "pct_within_5pct_52w_high": 24,
            "up_4pct": 10,
            "down_4pct": 10,
            "ratio_4pct_5d": 1.0,
            "ratio_4pct_10d": 1.0,
            "up_25pct_3m": 100,
            "down_25pct_3m": 100,
            "up_50pct_1m": 0,
            "down_50pct_1m": 0,
        }

    healing_rows = [
        row("2026-01-01", "negative"),
        row("2026-01-02", "negative"),
        row("2026-01-03", "negative"),
        row("2026-01-04", "positive"),
        row("2026-01-05", "positive"),
        row("2026-01-06", "positive"),
        row("2026-01-07", "positive"),
        row("2026-01-08", "positive"),
    ]
    weakening_rows = [
        row("2026-02-01", "positive"),
        row("2026-02-02", "positive"),
        row("2026-02-03", "positive"),
        row("2026-02-04", "positive"),
        row("2026-02-05", "positive"),
        row("2026-02-06", "positive"),
        row("2026-02-07", "neutral"),
        row("2026-02-08", "neutral"),
        row("2026-01-09", "neutral"),
        row("2026-01-10", "neutral"),
        row("2026-01-11", "neutral"),
    ]

    healing = annotate_breadth_regimes(healing_rows)
    weakening = annotate_breadth_regimes(weakening_rows)

    assert healing[2]["composite_regime"] == "Damaged"
    assert healing[-1]["composite_regime"] == "Healing"
    assert weakening[7]["composite_regime"] == "Weakening"


def test_extreme_return_diagnostics_are_filterable_and_sortable():
    from trading_dashboard.render.html import render_extreme_return_events

    html = render_extreme_return_events(
        [
            {
                "symbol": "AAP",
                "date": "2026-01-05",
                "daily_return": 0.57,
                "previous_close": 31.31,
                "close": 49.17,
                "next_close": 48.67,
                "label": "likely_real_move",
                "note": "No split-like ratio or one-day reversal pattern detected",
            },
            {
                "symbol": "PRIM",
                "date": "2026-01-06",
                "daily_return": -0.501,
                "previous_close": 202.92,
                "close": 101.23,
                "next_close": 107.98,
                "label": "missing_corporate_action",
                "note": "Close/previous close ratio resembles a common split ratio",
            },
        ]
    )
    assert "quality-filter-label" in html
    assert "data-filter-key='label'" in html
    assert "data-filter-table" in html
    assert "data-sort-table" in html
    assert "data-visible-count data-count-label='events'" in html
    assert "missing_corporate_action: 1" in html
    assert "likely_real_move: 1" in html
    assert "class='quality-label missing_corporate_action'" in html
    assert "<tr data-label='missing_corporate_action'>" in html
    assert "<tr> data-label" not in html
    assert html.index("missing_corporate_action") < html.index("likely_real_move")
    assert "data-sort-key='return'" in html
    assert "data-sort-cell='label' data-sort-type='number' data-sort-value='0'" in html


def test_sector_heatmap_orders_by_weekly_returns_and_shows_two_periods():
    from trading_dashboard.render.html import render_sector_heatmap

    html = render_sector_heatmap(
        [
            {"symbol": "XLK", "sector": "Technology", "return_1w": 0.02, "return_1m": 0.05},
            {"symbol": "XLV", "sector": "Health Care", "return_1w": -0.01, "return_1m": -0.03},
        ]
    )
    assert "sector-heatmap" in html
    assert ">1W<" in html
    assert ">1M<" in html
    assert html.index("XLK") < html.index("XLV")
    assert "2.0%" in html
    assert "-3.0%" in html
