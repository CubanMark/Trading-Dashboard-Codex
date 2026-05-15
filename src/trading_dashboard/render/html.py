from __future__ import annotations

import html
from pathlib import Path

from ..config import Settings
from ..data.storage import connect


PAGES = {
    "breadth": "Breadth",
    "sentiment": "Sentiment",
    "risk": "Risk On/Off",
    "credit-macro": "Credit & Macro",
    "volatility": "Volatility",
    "sectors": "Sectors",
    "scanners": "Scanners",
}

INDEX_SYMBOLS = ("SPY", "QQQ", "IWM", "^VIX", "TLT")


def render_site(settings: Settings) -> None:
    settings.pages_dir.mkdir(parents=True, exist_ok=True)
    data = load_render_data(settings)
    write(settings.pages_dir / "index.html", render_index(data))
    for slug, title in PAGES.items():
        write(settings.pages_dir / f"{slug}.html", render_detail(slug, title, data))


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def load_render_data(settings: Settings) -> dict:
    with connect(settings.db_path) as conn:
        latest_metric = conn.execute("SELECT MAX(date) AS date FROM dimension_metrics").fetchone()["date"]
        metrics = conn.execute("SELECT * FROM dimension_metrics WHERE date = ? ORDER BY metric_id", (latest_metric,)).fetchall() if latest_metric else []
        sectors = conn.execute("SELECT * FROM sector_returns WHERE date = ? ORDER BY return_1w DESC", (latest_metric,)).fetchall() if latest_metric else []
        industries = conn.execute("SELECT * FROM industry_returns WHERE date = ? ORDER BY return_1m DESC", (latest_metric,)).fetchall() if latest_metric else []
        hits = conn.execute(
            "SELECT * FROM scanner_hits WHERE date = ? ORDER BY scanner_id, rs_rank DESC LIMIT 75",
            (latest_metric,),
        ).fetchall() if latest_metric else []
        runs = conn.execute("SELECT * FROM run_log ORDER BY id DESC LIMIT 8").fetchall()
        quality = conn.execute("SELECT * FROM data_quality_checks ORDER BY id DESC LIMIT 12").fetchall()
        extreme_returns = conn.execute(
            """
            SELECT * FROM extreme_return_events
            ORDER BY
              CASE label
                WHEN 'missing_corporate_action' THEN 0
                WHEN 'possible_data_error' THEN 1
                WHEN 'corporate_action' THEN 2
                WHEN 'likely_real_move' THEN 3
                ELSE 4
              END,
              ABS(COALESCE(daily_return, 0)) DESC,
              symbol
            LIMIT 20
            """
        ).fetchall()
        sources = conn.execute("SELECT source, COUNT(*) AS n, MAX(date) AS max_date FROM prices GROUP BY source ORDER BY source").fetchall()
        breadth = conn.execute("SELECT * FROM breadth_daily ORDER BY date DESC").fetchall()
        spy_history = conn.execute(
            """
            SELECT date, close
            FROM prices
            WHERE symbol = 'SPY'
              AND close IS NOT NULL
            ORDER BY date
            """
        ).fetchall()
        active_equities = conn.execute("SELECT COUNT(*) AS n FROM symbols WHERE asset_class = 'equity' AND active = 1").fetchone()["n"]
        priced_equities = conn.execute(
            """
            SELECT COUNT(DISTINCT p.symbol) AS n
            FROM prices p
            JOIN symbols s ON s.symbol = p.symbol
            WHERE s.asset_class = 'equity' AND s.active = 1
            """
        ).fetchone()["n"]
        indexes = conn.execute(
            """
            SELECT p.symbol, p.date, p.close,
                   (p.close / prev.close - 1) AS change_1d
            FROM prices p
            JOIN (
              SELECT symbol, MAX(date) AS date FROM prices GROUP BY symbol
            ) latest ON p.symbol = latest.symbol AND p.date = latest.date
            LEFT JOIN prices prev
              ON prev.symbol = p.symbol
             AND prev.date = (
               SELECT MAX(date) FROM prices p2 WHERE p2.symbol = p.symbol AND p2.date < p.date
             )
            WHERE p.symbol IN ('SPY', 'QQQ', 'IWM', '^VIX', 'TLT')
            ORDER BY p.symbol
            """
        ).fetchall()
        index_history = conn.execute(
            """
            SELECT symbol, date, close
            FROM (
              SELECT symbol, date, close,
                     ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
              FROM prices
              WHERE symbol IN ('SPY', 'QQQ', 'IWM', '^VIX', 'TLT')
            )
            WHERE rn <= 20
            ORDER BY symbol, date
            """
        ).fetchall()
    history_by_symbol: dict[str, list[float]] = {}
    for row in index_history:
        if row["close"] is not None:
            history_by_symbol.setdefault(row["symbol"], []).append(float(row["close"]))
    index_rows = [dict(row) for row in indexes]
    for row in index_rows:
        row["history"] = history_by_symbol.get(row["symbol"], [])
    breadth_rows = [dict(row) for row in reversed(breadth)]
    breadth_composite_chart = breadth_composite_chart_rows(breadth_rows, [dict(row) for row in spy_history])
    return {
        "latest_date": latest_metric or "No data",
        "metrics": [dict(row) for row in metrics],
        "breadth": breadth_rows,
        "breadth_composite_chart": breadth_composite_chart,
        "sectors": [dict(row) for row in sectors],
        "industries": industry_rows_with_hit_counts([dict(row) for row in industries], [dict(row) for row in hits]),
        "hits": [dict(row) for row in hits],
        "runs": [dict(row) for row in runs],
        "quality": [dict(row) for row in quality],
        "extreme_returns": [dict(row) for row in extreme_returns],
        "sources": [dict(row) for row in sources],
        "operation": operation_summary([dict(row) for row in sources], [dict(row) for row in quality], active_equities, priced_equities),
        "indexes": sort_index_rows(index_rows),
    }


def sort_index_rows(rows: list[dict]) -> list[dict]:
    order = {symbol: index for index, symbol in enumerate(INDEX_SYMBOLS)}
    return sorted(rows, key=lambda row: order.get(str(row.get("symbol")), len(order)))


def industry_rows_with_hit_counts(industries: list[dict], hits: list[dict]) -> list[dict]:
    hit_counts: dict[str, int] = {}
    for hit in hits:
        industry = hit.get("industry")
        if industry:
            hit_counts[industry] = hit_counts.get(industry, 0) + 1
    for row in industries:
        row["hit_count"] = hit_counts.get(row.get("industry"), 0)
    return industries


def breadth_composite_chart_rows(breadth_rows: list[dict], spy_rows: list[dict]) -> list[dict]:
    spy_by_date = {row.get("date"): row.get("close") for row in spy_rows if row.get("close") is not None}
    chart_rows = []
    for row in breadth_rows:
        close = spy_by_date.get(row.get("date"))
        if close is None:
            continue
        close = float(close)
        chart_rows.append(
            {
                "date": row.get("date"),
                "spy_close": close,
                "composite": breadth_composite_score(row),
            }
        )
    return chart_rows


def render_index(data: dict) -> str:
    metric_pills = "\n".join(render_metric_card(row, data.get("breadth", [])) for row in data["metrics"])
    index_cards = "\n".join(render_index_card(row) for row in data["indexes"])
    sectors = render_sector_heatmap(data["sectors"])
    industry_leadership = render_industry_leadership(data["industries"])
    hits = render_hits_table(data["hits"])
    logs = render_logs(data)
    source_notice = render_source_notice(data["sources"])
    return page(
        "Market Dashboard",
        f"""
        <header class="topbar">
          <strong>Market Dashboard</strong>
          <nav>{nav_links()}</nav>
          <span class="operation-status">{esc(data["operation"])}</span>
        </header>
        {source_notice}
        <section class="index-strip">{index_cards}</section>
        <section class="market-state">
          <div class="section-heading">
            <h1>Market State</h1>
            <p>Read dimensions individually. No auto-composite.</p>
          </div>
          <div class="metric-grid">{metric_pills}</div>
        </section>
        <main class="dashboard">
          <section class="full-width">
            <h2>Sectors - 1 Week / 1 Month</h2>
            {sectors}
            <a href="sectors.html">Sector detail</a>
          </section>
          <section class="full-width">
            <h2>Industry Leadership</h2>
            {industry_leadership}
          </section>
          <section class="full-width">
            <h2>Research Scanner Hits</h2>
            <p class="warning">Pullback-v2a is a research scanner only, not an accepted tradable edge.</p>
            {hits}
            <a href="scanners.html">All scanner details</a>
          </section>
        </main>
        <section class="logs">
          <h2>Run Status</h2>
          {logs}
        </section>
        """,
    )


def render_detail(slug: str, title: str, data: dict) -> str:
    if slug == "scanners":
        body = f"<h1>{title}</h1><p class='warning'>Pullback-v2a is a research/watchlist scanner only.</p>{render_hits_table(data['hits'])}"
    elif slug == "sectors":
        body = (
            f"<h1>{title}</h1>{render_sector_heatmap(data['sectors'])}"
            f"<h2>Industry Leadership</h2>{render_industry_leadership(data['industries'])}"
        )
    elif slug == "breadth":
        body = (
            f"<h1>{title}</h1>"
            f"{render_breadth_kpis(data.get('breadth', []))}"
            f"{render_breadth_composite_chart(data.get('breadth_composite_chart', []))}"
            f"{render_breadth_history(data.get('breadth', []))}"
        )
    else:
        related = [row for row in data["metrics"] if slug.split("-")[0] in row["metric_id"] or title.lower().split()[0] in row["metric_id"]]
        cards = "".join(render_metric_card(row, data.get("breadth", [])) for row in related) or "<p>No dedicated metric rows available yet.</p>"
        body = f"<h1>{title}</h1><div class='cards'>{cards}</div>"
    return page(title, f"<header class='topbar'><strong>{title}</strong><nav>{nav_links()}</nav></header><main>{body}</main>")


def nav_links() -> str:
    links = ['<a href="index.html">Dashboard</a>'] + [f'<a href="{slug}.html">{title}</a>' for slug, title in PAGES.items()]
    return " ".join(links)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #18202a;
      --muted: #687384;
      --line: #d8dee8;
      --green: #15816f;
      --yellow: #b58200;
      --red: #cf5f69;
      --blue: #2368a2;
      --sparkline: #485563;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }}
    a {{ color: var(--blue); text-decoration: none; }}
    .topbar {{ min-height: 44px; display: flex; align-items: center; gap: 18px; padding: 0 22px; border-bottom: 1px solid var(--line); background: var(--panel); flex-wrap: wrap; }}
    .topbar > strong {{ white-space: nowrap; }}
    nav {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 14px; }}
    .operation-status {{ margin-left: auto; text-align: right; font-size: 12px; line-height: 1.35; color: var(--muted); }}
    .index-strip, .market-state, .logs, main {{ max-width: 1180px; margin: 18px auto; padding: 0 18px; }}
    .index-strip {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .index-card, .metric-card, section, .market-state {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .index-card {{ min-height: 118px; display: grid; grid-template-rows: auto auto auto 1fr; gap: 4px; overflow: hidden; }}
    .index-card strong, .metric-card strong {{ display: block; font-size: 12px; color: var(--muted); }}
    .big {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
    .index-card .big {{ font-size: 24px; }}
    .sparkline {{ width: 100%; height: 34px; margin-top: 4px; overflow: visible; }}
    .sparkline path.line {{ fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }}
    .sparkline path.fill {{ opacity: .12; }}
    .metric-card .sparkline {{ height: 28px; margin-top: 2px; }}
    .context {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: 14px; }}
    .delta-up {{ color: var(--green); font-weight: 700; }}
    .delta-down {{ color: var(--red); font-weight: 700; }}
    .delta-flat {{ color: var(--muted); font-weight: 700; }}
    .market-state {{ display: grid; gap: 12px; }}
    .section-heading {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }}
    .section-heading h1 {{ margin: 0; font-size: 22px; }}
    .section-heading p {{ margin: 0; color: var(--muted); font-size: 14px; }}
    .metric-grid, .cards {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }}
    .metric-card {{ min-height: 122px; display: grid; align-content: start; gap: 4px; }}
    .metric-card .big {{ font-size: 20px; line-height: 1.12; overflow-wrap: anywhere; }}
    .metric-card .muted {{ margin: 4px 0 0; font-size: 13px; line-height: 1.35; }}
    .green {{ border-top: 5px solid var(--green); }}
    .yellow {{ border-top: 5px solid var(--yellow); }}
    .red {{ border-top: 5px solid var(--red); }}
    .na {{ border-top: 5px solid var(--muted); }}
    .status-strong-red {{ border-top: 5px solid #cf5f69; }}
    .status-light-red {{ border-top: 5px solid #eda4aa; }}
    .status-neutral {{ border-top: 5px solid #d8dee8; }}
    .status-light-green {{ border-top: 5px solid #87cdbb; }}
    .status-strong-green {{ border-top: 5px solid #15816f; }}
    .dashboard {{ display: grid; gap: 16px; }}
    .full-width {{ width: 100%; }}
    section h2 {{ margin-top: 0; font-size: 18px; }}
    .sector-heatmap {{ display: grid; grid-template-columns: minmax(220px, 260px) repeat(2, minmax(120px, 1fr)); gap: 2px; align-items: stretch; }}
    .sector-head, .sector-label, .sector-cell {{ min-height: 34px; align-items: center; border: 1px solid rgba(24,32,42,.06); padding: 6px 8px; font-size: 13px; }}
    .sector-head, .sector-cell {{ display: flex; }}
    .sector-head {{ color: var(--muted); font-weight: 700; background: #f3f5f8; justify-content: center; }}
    .sector-label {{ display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: 8px; color: var(--text); background: #f9fafb; }}
    .sector-label b {{ font-size: 12px; text-align: right; }}
    .sector-label span {{ min-width: 0; line-height: 1.15; overflow-wrap: normal; }}
    .sector-cell {{ justify-content: center; font-weight: 700; color: #101820; }}
    .breadth-heatmap-wrap {{ overflow-x: auto; padding-bottom: 2px; }}
    .breadth-heatmap {{ min-width: 1100px; border-collapse: separate; border-spacing: 2px; table-layout: fixed; }}
    .breadth-heatmap th, .breadth-heatmap td {{ border: 0; padding: 7px 8px; text-align: center; font-size: 12px; line-height: 1.15; }}
    .breadth-heatmap th {{ color: var(--muted); background: #f3f5f8; font-weight: 700; }}
    .breadth-heatmap .group-head {{ color: #334155; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
    .breadth-heatmap .group-own {{ background: #dbe8f4; color: #264761; }}
    .breadth-heatmap .group-stockbee {{ background: #efdcb9; color: #6f4e1f; }}
    .breadth-heatmap .group-composite {{ background: #f3f5f8; color: #334155; }}
    .breadth-heatmap .date-cell {{ width: 92px; text-align: left; color: var(--muted); background: #f9fafb; font-weight: 700; }}
    .breadth-heatmap .own-head {{ background: #edf4fa; color: #315a78; }}
    .breadth-heatmap .stockbee-head {{ background: #f8f0e2; color: #6f4e1f; }}
    .breadth-cell {{ color: #101820; font-weight: 700; border-radius: 3px; }}
    .breadth-cell small {{ display: block; margin-top: 2px; color: rgba(16,24,32,.7); font-weight: 600; }}
    .heat-strong-red {{ background: #e98b94; }}
    .heat-light-red {{ background: #f7d9dd; }}
    .heat-neutral {{ background: transparent; }}
    .heat-light-green {{ background: #d8f0e9; }}
    .heat-strong-green {{ background: #8fd6c3; }}
    .breadth-na {{ background: #edf0f4; color: #687384; }}
    .breadth-composite {{ display: grid; gap: 14px; padding: 16px; }}
    .composite-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    .composite-head h2 {{ margin: 0; }}
    .composite-title {{ display: inline-flex; align-items: center; gap: 8px; }}
    .info-dot {{ display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; border: 1px solid var(--line); color: var(--muted); font-size: 12px; font-weight: 800; cursor: help; }}
    .composite-score {{ display: inline-grid; place-items: center; min-width: 76px; min-height: 58px; border: 1px solid var(--line); border-radius: 8px; background: #f8fafc; font-size: 30px; font-weight: 850; line-height: 1; box-shadow: inset 0 1px 0 rgba(255,255,255,.8); }}
    .composite-score.positive {{ color: #0f766e; border-color: #b9ddd4; background: #eefaf6; }}
    .composite-score.negative {{ color: #be4f5c; border-color: #efc5ca; background: #fff1f3; }}
    .composite-score.neutral {{ color: #334155; }}
    .composite-bar {{ position: relative; height: 18px; border-radius: 999px; background: linear-gradient(90deg, #e98b94 0%, #f7d9dd 25%, #f7f8fa 45%, #f7f8fa 55%, #d8f0e9 75%, #8fd6c3 100%); border: 1px solid var(--line); }}
    .composite-zero {{ position: absolute; left: 50%; top: -4px; bottom: -4px; width: 1px; background: rgba(24,32,42,.45); }}
    .composite-marker {{ position: absolute; top: -6px; width: 4px; height: 30px; border-radius: 999px; background: #18202a; transform: translateX(-50%); box-shadow: 0 0 0 3px rgba(255,255,255,.85); }}
    .composite-scale {{ display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; font-weight: 700; }}
    .breadth-chart-section {{ display: grid; gap: 12px; }}
    .breadth-chart-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
    .breadth-chart-head h2 {{ margin: 0; }}
    .breadth-chart-controls {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .breadth-chart-controls button {{ border: 1px solid var(--line); border-radius: 6px; background: #f8fafc; color: var(--muted); padding: 6px 10px; font-weight: 700; cursor: pointer; }}
    .breadth-chart-controls button.active {{ background: #18202a; border-color: #18202a; color: #ffffff; }}
    .breadth-chart-frame {{ display: none; }}
    .breadth-chart-frame.active {{ display: block; }}
    .breadth-chart {{ width: 100%; min-height: 360px; overflow: visible; }}
    .chart-axis-label {{ fill: var(--muted); font-size: 12px; font-weight: 700; }}
    .chart-tick {{ fill: var(--muted); font-size: 11px; }}
    .chart-grid {{ stroke: #e6ebf2; stroke-width: 1; }}
    .chart-zero {{ stroke: #a6afbd; stroke-width: 1.4; stroke-dasharray: 5 5; }}
    .chart-spy {{ fill: none; stroke: #2368a2; stroke-width: 2.4; vector-effect: non-scaling-stroke; }}
    .chart-composite {{ fill: none; stroke: #15816f; stroke-width: 2.2; vector-effect: non-scaling-stroke; }}
    .chart-negative-band {{ fill: #f7d9dd; opacity: .72; }}
    .breadth-chart-legend {{ display: flex; gap: 16px; flex-wrap: wrap; color: var(--muted); font-size: 12px; font-weight: 700; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
    .legend-swatch {{ width: 18px; height: 3px; border-radius: 999px; background: var(--muted); }}
    .legend-spy {{ background: #2368a2; }}
    .legend-composite {{ background: #15816f; }}
    .legend-band {{ width: 16px; height: 10px; border-radius: 2px; background: #f7d9dd; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; }}
    th button {{ display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 0; background: transparent; color: inherit; font: inherit; font-weight: 700; cursor: pointer; }}
    th button::after {{ content: ""; width: 0; height: 0; }}
    th button[aria-sort="ascending"]::after {{ content: "^"; color: var(--blue); font-size: 12px; line-height: 1; }}
    th button[aria-sort="descending"]::after {{ content: "v"; color: var(--blue); font-size: 12px; line-height: 1; }}
    .muted {{ color: var(--muted); }}
    .warning {{ color: #8a5a00; font-weight: 600; }}
    .source-notice {{ max-width: 1180px; margin: 18px auto 0; padding: 12px 18px; border: 1px solid #f0c36a; border-left: 5px solid #b58200; border-radius: 8px; background: #fff7e0; color: #583b00; font-weight: 700; }}
    .status-note {{ margin: 0 0 12px; color: var(--muted); font-size: 14px; }}
    .breadth-year-toolbar {{ display: flex; align-items: center; gap: 10px; margin: 10px 0 12px; flex-wrap: wrap; }}
    .breadth-year-toolbar label {{ font-size: 13px; color: var(--muted); font-weight: 700; }}
    .breadth-year-toolbar select {{ border: 1px solid var(--line); border-radius: 6px; background: var(--panel); color: var(--text); padding: 7px 10px; font-size: 14px; }}
    .breadth-year-count {{ color: var(--muted); font-size: 13px; font-weight: 700; }}
    .scanner-toolbar {{ display: flex; align-items: center; gap: 10px; margin: 10px 0 12px; flex-wrap: wrap; }}
    .scanner-toolbar label {{ font-size: 13px; color: var(--muted); font-weight: 700; }}
    .scanner-toolbar select {{ border: 1px solid var(--line); border-radius: 6px; background: var(--panel); color: var(--text); padding: 7px 10px; font-size: 14px; }}
    .industry-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .compact-table td, .compact-table th {{ padding: 7px 8px; }}
    .tag-list {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
    .tag {{ display: inline-flex; align-items: center; min-height: 24px; border-radius: 5px; padding: 4px 8px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
    .tag[data-tooltip] {{ position: relative; cursor: help; }}
    .tag[data-tooltip]:hover::after {{ content: attr(data-tooltip); position: absolute; left: 0; top: calc(100% + 7px); z-index: 10; width: max-content; max-width: 260px; padding: 8px 10px; border-radius: 6px; background: #111827; color: #ffffff; border: 1px solid #1f2937; box-shadow: 0 8px 20px rgba(15, 23, 42, .18); font-size: 12px; font-weight: 600; line-height: 1.35; white-space: normal; }}
    .tag[data-tooltip]:hover::before {{ content: ""; position: absolute; left: 12px; top: calc(100% + 2px); z-index: 11; border: 6px solid transparent; border-bottom-color: #111827; }}
    .tag-ma10 {{ color: #075985; background: #e0f2fe; border: 1px solid #bae6fd; }}
    .tag-ma20 {{ color: #047857; background: #d1fae5; border: 1px solid #a7f3d0; }}
    .tag-3d {{ color: #7c2d12; background: #ffedd5; border: 1px solid #fed7aa; }}
    .tag-neutral {{ color: #475569; background: #f1f5f9; border: 1px solid #e2e8f0; }}
    .loggrid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .quality-detail {{ margin-top: 16px; }}
    .quality-label {{ display: inline-block; padding: 2px 6px; border-radius: 4px; background: #eef2f7; color: #334155; font-size: 12px; font-weight: 700; }}
    .quality-label.missing_corporate_action {{ color: #8a5a00; background: #fff7e0; border: 1px solid #f0c36a; }}
    .quality-label.possible_data_error {{ color: #991b1b; background: #fee2e2; border: 1px solid #fecaca; }}
    .quality-label.corporate_action {{ color: #075985; background: #e0f2fe; border: 1px solid #bae6fd; }}
    .quality-label.likely_real_move {{ color: #334155; background: #f1f5f9; border: 1px solid #e2e8f0; }}
    @media (max-width: 1100px) {{
      .metric-grid, .cards {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 850px) {{
      .index-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .industry-grid {{ grid-template-columns: 1fr; }}
      .section-heading {{ display: block; }}
      .metric-grid, .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .sector-heatmap {{ grid-template-columns: minmax(170px, 210px) repeat(2, minmax(80px, 1fr)); }}
      .sector-head, .sector-label, .sector-cell {{ padding: 5px 6px; font-size: 12px; }}
      .sector-label {{ grid-template-columns: 40px minmax(0, 1fr); gap: 6px; }}
    }}
    @media (max-width: 560px) {{
      .topbar {{ align-items: flex-start; padding: 10px 14px; }}
      .operation-status {{ margin-left: 0; text-align: left; width: 100%; }}
      .index-strip, .market-state, .logs, main {{ padding: 0 12px; }}
      .index-strip, .metric-grid, .cards {{ grid-template-columns: 1fr; }}
      .sector-heatmap {{ grid-template-columns: 64px repeat(2, minmax(64px, 1fr)); }}
      .sector-label span {{ display: none; }}
      .sector-label {{ display: flex; justify-content: center; }}
      .sector-label b {{ text-align: center; }}
    }}
  </style>
</head>
<body>
{body}
<script>
  document.querySelectorAll('[data-breadth-history]').forEach((section) => {{
    const select = section.querySelector('[data-breadth-year-select]');
    const rows = Array.from(section.querySelectorAll('tbody tr[data-year]'));
    const count = section.querySelector('[data-breadth-year-count]');
    if (!select || rows.length === 0) return;
    const update = () => {{
      let visible = 0;
      rows.forEach((row) => {{
        const show = row.dataset.year === select.value;
        row.style.display = show ? '' : 'none';
        if (show) visible += 1;
      }});
      if (count) count.textContent = `${{visible}} days`;
    }};
    select.addEventListener('change', update);
    update();
  }});
  document.querySelectorAll('[data-breadth-chart]').forEach((section) => {{
    const buttons = Array.from(section.querySelectorAll('[data-breadth-chart-range]'));
    const frames = Array.from(section.querySelectorAll('[data-breadth-chart-frame]'));
    const setRange = (range) => {{
      buttons.forEach((button) => button.classList.toggle('active', button.dataset.breadthChartRange === range));
      frames.forEach((frame) => frame.classList.toggle('active', frame.dataset.breadthChartFrame === range));
    }};
    buttons.forEach((button) => button.addEventListener('click', () => setRange(button.dataset.breadthChartRange)));
    const active = buttons.find((button) => button.classList.contains('active')) || buttons[0];
    if (active) setRange(active.dataset.breadthChartRange);
  }});
  document.querySelectorAll('[data-filter-table]').forEach((table) => {{
    const container = table.closest('section') || document;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const count = container.querySelector('[data-visible-count]');
    const countLabel = count ? (count.dataset.countLabel || 'rows') : 'rows';
    const filters = Array.from(container.querySelectorAll('[data-table-filter]'));
    const rowMatches = (row, ignoredFilter) => filters.every((filter) => {{
      if (filter === ignoredFilter) return true;
      const selected = filter.value;
      const key = filter.dataset.filterKey;
      return selected === 'all' || row.dataset[key] === selected;
    }});
    const syncFilterOptions = () => {{
      let changed = false;
      filters.forEach((filter) => {{
        const key = filter.dataset.filterKey;
        const available = new Set(
          rows
            .filter((row) => rowMatches(row, filter))
            .map((row) => row.dataset[key])
            .filter(Boolean)
        );
        Array.from(filter.options).forEach((option) => {{
          const isAll = option.value === 'all';
          const isAvailable = isAll || available.has(option.value);
          option.hidden = !isAvailable;
          option.disabled = !isAvailable;
        }});
        if (filter.value !== 'all' && !available.has(filter.value)) {{
          filter.value = 'all';
          changed = true;
        }}
      }});
      return changed;
    }};
    const update = () => {{
      let guard = 0;
      while (syncFilterOptions() && guard < filters.length) guard += 1;
      let visible = 0;
      rows.forEach((row) => {{
        const show = rowMatches(row);
        row.style.display = show ? '' : 'none';
        if (show) visible += 1;
      }});
      if (count) count.textContent = `${{visible}} ${{countLabel}} shown`;
    }};
    filters.forEach((filter) => filter.addEventListener('change', update));
    update();
  }});
  document.querySelectorAll('[data-sort-table]').forEach((table) => {{
    const tbody = table.querySelector('tbody');
    const buttons = Array.from(table.querySelectorAll('[data-sort-key]'));
    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.forEach((row, index) => row.dataset.originalIndex = String(index));
    buttons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const key = button.dataset.sortKey;
        const current = button.getAttribute('aria-sort');
        const initial = button.dataset.sortDefault || 'ascending';
        const direction = current === 'ascending' ? 'descending' : current === 'descending' ? 'ascending' : initial;
        buttons.forEach((other) => other.removeAttribute('aria-sort'));
        button.setAttribute('aria-sort', direction);
        Array.from(tbody.querySelectorAll('tr'))
          .sort((left, right) => compareRows(left, right, key, direction))
          .forEach((row) => tbody.appendChild(row));
      }});
    }});
  }});

  function compareRows(left, right, key, direction) {{
    const leftCell = left.querySelector(`[data-sort-cell="${{key}}"]`);
    const rightCell = right.querySelector(`[data-sort-cell="${{key}}"]`);
    const leftMissing = !leftCell || leftCell.dataset.sortMissing === 'true';
    const rightMissing = !rightCell || rightCell.dataset.sortMissing === 'true';
    if (leftMissing && rightMissing) return Number(left.dataset.originalIndex) - Number(right.dataset.originalIndex);
    if (leftMissing) return 1;
    if (rightMissing) return -1;
    const type = leftCell.dataset.sortType || 'text';
    let result = 0;
    if (type === 'number') {{
      result = Number(leftCell.dataset.sortValue) - Number(rightCell.dataset.sortValue);
    }} else {{
      result = leftCell.dataset.sortValue.localeCompare(rightCell.dataset.sortValue);
    }}
    if (result === 0) return Number(left.dataset.originalIndex) - Number(right.dataset.originalIndex);
    return direction === 'ascending' ? result : -result;
  }}
</script>
</body>
</html>"""


def render_metric_card(row: dict, breadth_rows: list[dict] | None = None) -> str:
    sparkline = ""
    if row.get("metric_id") == "breadth_sp500_above_sma50" and breadth_rows:
        sparkline = render_sparkline([item.get("pct_above_sma50") for item in breadth_rows[-120:]], "var(--sparkline)")
    return f"""
    <article class="metric-card {esc(row['status'])}">
      <strong>{esc(metric_title(row['metric_id']))}</strong>
      <div class="big">{esc(row['label'] or 'N/A')}</div>
      {sparkline}
      {render_metric_delta(row)}
      <p class="muted">{esc(row['note'] or '')}</p>
    </article>"""


def render_index_card(row: dict) -> str:
    change = row["change_1d"]
    change_text = "N/A" if change is None else f"{change:.2%}"
    change_class = delta_class(change)
    spark_color = "var(--green)" if change is not None and change >= 0 else "var(--red)"
    return (
        "<article class='index-card'>"
        f"<strong>{esc(row['symbol'])}</strong>"
        f"<div class='big'>{row['close']:.2f}</div>"
        f"<span class='{change_class}'>{esc(change_text)}</span>"
        f"{render_sparkline(row.get('history') or [], spark_color)}"
        "</article>"
    )


def delta_class(value: float | None) -> str:
    if value is None:
        return "delta-flat"
    if value > 0:
        return "delta-up"
    if value < 0:
        return "delta-down"
    return "delta-flat"


def render_sector_heatmap(rows: list[dict]) -> str:
    if not rows:
        return "<p>No sector performance data available yet.</p>"
    ordered = sorted(rows, key=lambda row: none_last(row.get("return_1w")), reverse=True)
    body = [
        "<div class='sector-head'></div><div class='sector-head'>1W</div><div class='sector-head'>1M</div>"
    ]
    for row in ordered:
        body.append(
            f"<div class='sector-label'><b>{esc(row['symbol'])}</b><span>{esc(row['sector'])}</span></div>"
            f"{render_sector_cell(row.get('return_1w'))}"
            f"{render_sector_cell(row.get('return_1m'))}"
        )
    return "<div class='sector-heatmap'>" + "".join(body) + "</div>"


def render_sector_cell(value: float | None) -> str:
    if value is None:
        return "<div class='sector-cell' style='background:#edf0f4'>N/A</div>"
    return f"<div class='sector-cell' style='background:{return_color(float(value))}'>{value:.1%}</div>"


def render_breadth_history(rows: list[dict]) -> str:
    if not rows:
        return "<section><h2>Breadth History</h2><p>No breadth history available yet.</p></section>"
    years = sorted({str(row.get("date", ""))[:4] for row in rows if str(row.get("date", ""))[:4]}, reverse=True)
    selected_year = years[0]
    year_options = "".join(
        f"<option value='{esc(year)}'{' selected' if year == selected_year else ''}>{esc(year)}</option>"
        for year in years
    )
    latest_rows = list(reversed(rows))
    body = "".join(
        f"<tr data-year='{esc(str(row.get('date', ''))[:4])}'>"
        f"<td class='date-cell'>{esc(short_date(row['date']))}</td>"
        f"{render_sma_heat_cell(row.get('pct_above_sma50'))}"
        f"{render_sma_heat_cell(row.get('pct_above_sma200'))}"
        f"{render_momentum_pair_heat_cell(row.get('new_highs_52w'), row.get('new_lows_52w'))}"
        f"{render_near_high_heat_cell(row.get('pct_within_5pct_52w_high'))}"
        f"{render_momentum_pair_heat_cell(row.get('up_4pct'), row.get('down_4pct'))}"
        f"{render_ratio_heat_cell(row.get('ratio_4pct_5d'))}"
        f"{render_ratio_heat_cell(row.get('ratio_4pct_10d'))}"
        f"{render_momentum_pair_heat_cell(row.get('up_25pct_3m'), row.get('down_25pct_3m'), strong_red=0.70, light_red=0.90, light_green=1.20, strong_green=1.80)}"
        f"{render_speculative_heat_cell(row.get('up_50pct_1m'), row.get('down_50pct_1m'))}"
        f"{render_composite_heat_cell(row)}"
        "</tr>"
        for row in latest_rows
    )
    return (
        "<section data-breadth-history><h2>Breadth History</h2>"
        "<p class='status-note'>Compact color view of the key participation and momentum signals. Uncolored cells are normal range; 50% 1M is colored contrarian and deliberately subtle.</p>"
        "<div class='breadth-year-toolbar'>"
        "<label for='breadth-history-year'>Year</label>"
        f"<select id='breadth-history-year' data-breadth-year-select>{year_options}</select>"
        "<span class='breadth-year-count' data-breadth-year-count></span>"
        "</div>"
        "<div class='breadth-heatmap-wrap'><table class='breadth-heatmap'><thead>"
        "<tr><th class='group-head' rowspan='2'>Date</th>"
        "<th class='group-head group-own' colspan='4'>Dashboard Breadth</th>"
        "<th class='group-head group-stockbee' colspan='5'>Stockbee-style Momentum</th>"
        "<th class='group-head group-composite' rowspan='2'>Composite</th></tr>"
        "<tr><th class='own-head'>&gt; SMA50</th><th class='own-head'>&gt; SMA200</th>"
        "<th class='own-head'>52W H/L</th><th class='own-head'>Near High</th>"
        "<th class='stockbee-head'>4% U/D</th><th class='stockbee-head'>5D Ratio</th>"
        "<th class='stockbee-head'>10D Ratio</th>"
        "<th class='stockbee-head'>25% 3M</th><th class='stockbee-head'>50% 1M</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div></section>"
    )


def short_date(value: str) -> str:
    return value[5:] if len(value) == 10 else value


def render_sma_heat_cell(value: float | None) -> str:
    return render_heat_cell(format_percent_value(value), heat_status_from_value(value, 35, 45, 55, 65))


def render_near_high_heat_cell(value: float | None) -> str:
    return render_heat_cell(format_percent_value(value), heat_status_from_value(value, 12, 18, 30, 36))


def render_ratio_heat_cell(value: float | None) -> str:
    return render_heat_cell(format_ratio_value(value), heat_status_from_value(value, 0.60, 0.85, 1.25, 1.75))


def render_momentum_pair_heat_cell(
    up_value: int | None,
    down_value: int | None,
    strong_red: float = 0.50,
    light_red: float = 0.80,
    light_green: float = 1.25,
    strong_green: float = 2.00,
) -> str:
    up_count = int(up_value or 0)
    down_count = int(down_value or 0)
    status = momentum_pair_status(up_count, down_count, strong_red, light_red, light_green, strong_green)
    return render_heat_cell(f"{up_count} / {down_count}", status)


def render_speculative_heat_cell(up_value: int | None, down_value: int | None) -> str:
    up_count = int(up_value or 0)
    down_count = int(down_value or 0)
    status = speculative_status(up_count, down_count)
    return render_heat_cell(f"{up_count} / {down_count}", status)


def render_composite_heat_cell(row: dict) -> str:
    score = breadth_composite_score(row)
    label = f"+{score}" if score > 0 else str(score)
    return render_heat_cell(label, composite_score_status(score))


def momentum_pair_status(
    up_value: int | None,
    down_value: int | None,
    strong_red: float = 0.50,
    light_red: float = 0.80,
    light_green: float = 1.25,
    strong_green: float = 2.00,
) -> str:
    up_count = int(up_value or 0)
    down_count = int(down_value or 0)
    ratio = count_ratio(up_count, down_count)
    return heat_status_from_value(ratio, strong_red, light_red, light_green, strong_green)


def speculative_status(up_value: int | None, down_value: int | None) -> str:
    up_count = int(up_value or 0)
    down_count = int(down_value or 0)
    light_signal_count = 15
    strong_signal_count = 30
    if up_count == 0 and down_count == 0:
        return "neutral"
    if down_count >= strong_signal_count and down_count >= up_count * 2:
        return "strong-green"
    if up_count >= strong_signal_count and up_count >= down_count * 2:
        return "strong-red"
    if down_count >= light_signal_count and down_count >= up_count * 2:
        return "light-green"
    if up_count >= light_signal_count and up_count >= down_count * 2:
        return "light-red"
    return "neutral"


def count_ratio(up_count: int, down_count: int) -> float | None:
    if up_count == 0 and down_count == 0:
        return 1.0
    if down_count == 0:
        return None if up_count == 0 else float("inf")
    return up_count / down_count


def heat_status_from_value(
    value: float | None,
    strong_red: float,
    light_red: float,
    light_green: float,
    strong_green: float,
) -> str:
    if value is None:
        return "na"
    if value < strong_red:
        return "strong-red"
    if value < light_red:
        return "light-red"
    if value <= light_green:
        return "neutral"
    if value <= strong_green:
        return "light-green"
    return "strong-green"


def render_heat_cell(label: str, status: str) -> str:
    class_name = {
        "strong-red": "heat-strong-red",
        "light-red": "heat-light-red",
        "neutral": "heat-neutral",
        "light-green": "heat-light-green",
        "strong-green": "heat-strong-green",
        "na": "breadth-na",
    }.get(status, "breadth-na")
    return f"<td class='breadth-cell {class_name}'>{esc(label)}</td>"


def metric_status_from_heat(status: str) -> str:
    if status == "na":
        return "na"
    return f"status-{status}"


def metric_status_from_pair(
    up_count: int,
    down_count: int,
    strong_red: float = 0.50,
    light_red: float = 0.80,
    light_green: float = 1.25,
    strong_green: float = 2.00,
) -> str:
    status = momentum_pair_status(up_count, down_count, strong_red, light_red, light_green, strong_green)
    return metric_status_from_heat(status)


def metric_status_from_speculative(up_count: int, down_count: int) -> str:
    return metric_status_from_heat(speculative_status(up_count, down_count))


def render_breadth_kpis(rows: list[dict]) -> str:
    if not rows:
        return "<p>No breadth KPI data available yet.</p>"
    latest = rows[-1]
    spark_rows = rows[-120:]
    high_count = int(latest.get("new_highs_52w") or 0)
    low_count = int(latest.get("new_lows_52w") or 0)
    cards = [
        render_breadth_kpi_card(
            "SMA50 Breadth",
            f"{format_percent_value(latest.get('pct_above_sma50'))} > SMA50",
            metric_status_from_heat(heat_status_from_value(latest.get("pct_above_sma50"), 35, 45, 55, 65)),
            "Tactical participation",
            render_sparkline([item.get("pct_above_sma50") for item in spark_rows], "var(--sparkline)"),
        ),
        render_breadth_kpi_card(
            "SMA200 Breadth",
            f"{format_percent_value(latest.get('pct_above_sma200'))} > SMA200",
            metric_status_from_heat(heat_status_from_value(latest.get("pct_above_sma200"), 35, 45, 55, 65)),
            "Structural trend participation",
            render_sparkline([item.get("pct_above_sma200") for item in spark_rows], "var(--sparkline)"),
        ),
        render_breadth_kpi_card(
            "52W Highs / Lows",
            f"{high_count} / {low_count}",
            metric_status_from_pair(high_count, low_count),
            highs_lows_note(high_count, low_count),
            "",
        ),
        render_breadth_kpi_card(
            "Near 52W High",
            f"{format_percent_value(latest.get('pct_within_5pct_52w_high'))}",
            metric_status_from_heat(heat_status_from_value(latest.get("pct_within_5pct_52w_high"), 12, 18, 30, 36)),
            "Leadership depth",
            render_sparkline([item.get("pct_within_5pct_52w_high") for item in spark_rows], "var(--sparkline)"),
        ),
    ]
    return (
        "<h2>Participation Breadth</h2>"
        "<div class='cards breadth-kpis'>"
        + "".join(cards)
        + "</div>"
        "<h2>Momentum Breadth</h2>"
        + render_momentum_kpis(rows)
        + render_breadth_composite(latest)
    )


def render_momentum_kpis(rows: list[dict]) -> str:
    latest = rows[-1]
    spark_rows = rows[-120:]
    up_4pct = int(latest.get("up_4pct") or 0)
    down_4pct = int(latest.get("down_4pct") or 0)
    up_25pct_3m = int(latest.get("up_25pct_3m") or 0)
    down_25pct_3m = int(latest.get("down_25pct_3m") or 0)
    up_50pct_1m = int(latest.get("up_50pct_1m") or 0)
    down_50pct_1m = int(latest.get("down_50pct_1m") or 0)
    cards = [
        render_breadth_kpi_card(
            "4% Up / Down",
            f"{up_4pct} / {down_4pct}",
            metric_status_from_pair(up_4pct, down_4pct),
            "Daily momentum thrust",
            "",
        ),
        render_breadth_kpi_card(
            "5D 4% Ratio",
            format_ratio_value(latest.get("ratio_4pct_5d")),
            metric_status_from_heat(heat_status_from_value(latest.get("ratio_4pct_5d"), 0.60, 0.85, 1.25, 1.75)),
            "Short-term burst balance",
            render_sparkline([item.get("ratio_4pct_5d") for item in spark_rows], "var(--sparkline)"),
        ),
        render_breadth_kpi_card(
            "10D 4% Ratio",
            format_ratio_value(latest.get("ratio_4pct_10d")),
            metric_status_from_heat(heat_status_from_value(latest.get("ratio_4pct_10d"), 0.60, 0.85, 1.25, 1.75)),
            "Two-week burst balance",
            render_sparkline([item.get("ratio_4pct_10d") for item in spark_rows], "var(--sparkline)"),
        ),
        render_breadth_kpi_card(
            "25% Up / Down 3M",
            f"{up_25pct_3m} / {down_25pct_3m}",
            metric_status_from_pair(up_25pct_3m, down_25pct_3m, strong_red=0.70, light_red=0.90, light_green=1.20, strong_green=1.80),
            "Quarter momentum extremes",
            "",
        ),
        render_breadth_kpi_card(
            "50% Up / Down 1M",
            f"{up_50pct_1m} / {down_50pct_1m}",
            metric_status_from_speculative(up_50pct_1m, down_50pct_1m),
            "One-month speculative heat",
            "",
        ),
    ]
    return "<div class='cards breadth-kpis momentum-kpis'>" + "".join(cards) + "</div>"


def render_breadth_composite(row: dict) -> str:
    score = breadth_composite_score(row)
    marker_left = (score + 18) / 36 * 100
    label = f"+{score}" if score > 0 else str(score)
    tone = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    return (
        "<section class='breadth-composite'>"
        "<div class='composite-head'><h2 class='composite-title'>Breadth Composite"
        "<span class='info-dot' title='Sum of the nine Breadth History color states: light +/-1, strong +/-2, neutral 0. 50% 1M is scored contrarian.'>i</span>"
        "</h2>"
        f"<div class='composite-score {tone}'>{esc(label)}</div></div>"
        "<div class='composite-bar' role='img' aria-label='Breadth Composite range from minus 18 to plus 18'>"
        "<div class='composite-zero'></div>"
        f"<div class='composite-marker' style='left:{marker_left:.1f}%'></div>"
        "</div>"
        "<div class='composite-scale'><span>-18</span><span>0</span><span>+18</span></div>"
        "</section>"
    )


def render_breadth_composite_chart(rows: list[dict]) -> str:
    if not rows:
        return "<section><h2>SPY vs Breadth Composite</h2><p>No SPY/composite history available yet.</p></section>"
    ranges = [
        ("ytd", "YTD", filter_chart_rows(rows, "ytd")),
        ("1y", "1Y", filter_chart_rows(rows, "1y")),
        ("3y", "3Y", filter_chart_rows(rows, "3y")),
        ("5y", "5Y", filter_chart_rows(rows, "5y")),
    ]
    ranges = [(key, label, period_rows) for key, label, period_rows in ranges if len(period_rows) >= 2]
    if not ranges:
        return "<section><h2>SPY vs Breadth Composite</h2><p>Not enough SPY/composite history available yet.</p></section>"
    default_range = "1y" if any(key == "1y" for key, _, _ in ranges) else ranges[0][0]
    buttons = "".join(
        f"<button type='button' data-breadth-chart-range='{esc(key)}' class='{'active' if key == default_range else ''}'>{esc(label)}</button>"
        for key, label, _ in ranges
    )
    frames = "".join(
        f"<div class='breadth-chart-frame {'active' if key == default_range else ''}' data-breadth-chart-frame='{esc(key)}'>"
        f"{render_breadth_composite_svg(period_rows)}"
        "</div>"
        for key, _, period_rows in ranges
    )
    return (
        "<section class='breadth-chart-section' data-breadth-chart>"
        "<div class='breadth-chart-head'>"
        "<h2>SPY vs Breadth Composite</h2>"
        f"<div class='breadth-chart-controls' aria-label='Chart range'>{buttons}</div>"
        "</div>"
        "<div class='breadth-chart-legend'>"
        "<span class='legend-item'><span class='legend-swatch legend-spy'></span>SPY indexed to 100</span>"
        "<span class='legend-item'><span class='legend-swatch legend-composite'></span>Breadth Composite 5D avg</span>"
        "<span class='legend-item'><span class='legend-band'></span>Composite below 0 for 3+ days</span>"
        "</div>"
        f"{frames}"
        "</section>"
    )


def filter_chart_rows(rows: list[dict], range_key: str) -> list[dict]:
    if not rows:
        return []
    latest_date = str(rows[-1].get("date", ""))
    latest_year = latest_date[:4]
    if range_key == "ytd":
        return [row for row in rows if str(row.get("date", "")).startswith(latest_year)]
    days = {"1y": 252, "3y": 756, "5y": 1260}.get(range_key, len(rows))
    return rows[-days:]


def render_breadth_composite_svg(rows: list[dict]) -> str:
    width = 1080
    height = 360
    left = 58
    right = 58
    top = 24
    bottom = 44
    plot_width = width - left - right
    plot_height = height - top - bottom
    first_spy_close = float(rows[0].get("spy_close") or 0)
    if not first_spy_close:
        return "<p class='status-note'>Not enough chart data.</p>"
    spy_values = [float(row["spy_close"]) / first_spy_close * 100 for row in rows if row.get("spy_close") is not None]
    if len(spy_values) < 2:
        return "<p class='status-note'>Not enough chart data.</p>"
    spy_min = min(spy_values)
    spy_max = max(spy_values)
    spy_pad = max((spy_max - spy_min) * 0.08, 2.0)
    spy_min -= spy_pad
    spy_max += spy_pad
    if spy_max == spy_min:
        spy_max = spy_min + 1

    def x_at(index: int) -> float:
        if len(rows) == 1:
            return left + plot_width / 2
        return left + index / (len(rows) - 1) * plot_width

    def y_spy(value: float) -> float:
        return top + (spy_max - value) / (spy_max - spy_min) * plot_height

    def y_composite(value: float) -> float:
        return top + (18 - value) / 36 * plot_height

    spy_points = " ".join(f"{x_at(index):.1f},{y_spy(float(row['spy_close']) / first_spy_close * 100):.1f}" for index, row in enumerate(rows))
    smoothed_composite = moving_average([float(row["composite"]) for row in rows], 5)
    composite_points = " ".join(f"{x_at(index):.1f},{y_composite(value):.1f}" for index, value in enumerate(smoothed_composite))
    bands = "".join(render_negative_band(rows, start, end, x_at, top, plot_height) for start, end in negative_composite_clusters(rows, min_days=3))
    grid = "".join(
        f"<line class='chart-grid' x1='{left}' y1='{top + plot_height * step / 4:.1f}' x2='{left + plot_width}' y2='{top + plot_height * step / 4:.1f}'></line>"
        for step in range(5)
    )
    spy_ticks = "".join(
        f"<text class='chart-tick' x='{left - 8}' y='{y_spy(value) + 4:.1f}' text-anchor='end'>{value:.0f}</text>"
        for value in evenly_spaced(spy_min, spy_max, 5)
    )
    composite_ticks = "".join(
        f"<text class='chart-tick' x='{left + plot_width + 8}' y='{y_composite(value) + 4:.1f}'>{int(value):+d}</text>"
        for value in (-18, -9, 0, 9, 18)
    )
    first_date = chart_date_label(str(rows[0].get("date", "")))
    last_date = chart_date_label(str(rows[-1].get("date", "")))
    return (
        "<svg class='breadth-chart' viewBox='0 0 1080 360' preserveAspectRatio='none' role='img' "
        f"aria-label='SPY indexed versus 5 day average Breadth Composite from {esc(first_date)} to {esc(last_date)}'>"
        f"{bands}"
        f"{grid}"
        f"<line class='chart-zero' x1='{left}' y1='{y_composite(0):.1f}' x2='{left + plot_width}' y2='{y_composite(0):.1f}'></line>"
        f"<polyline class='chart-spy' points='{spy_points}'></polyline>"
        f"<polyline class='chart-composite' points='{composite_points}'></polyline>"
        f"{spy_ticks}{composite_ticks}"
        f"<text class='chart-axis-label' x='{left}' y='14'>SPY Indexed</text>"
        f"<text class='chart-axis-label' x='{left + plot_width}' y='14' text-anchor='end'>Composite</text>"
        f"<text class='chart-tick' x='{left}' y='{height - 14}'>{esc(first_date)}</text>"
        f"<text class='chart-tick' x='{left + plot_width}' y='{height - 14}' text-anchor='end'>{esc(last_date)}</text>"
        "</svg>"
    )


def render_negative_band(rows: list[dict], start: int, end: int, x_at, top: int, plot_height: int) -> str:
    start_x = x_at(max(start - 0.5, 0))
    end_x = x_at(min(end + 0.5, len(rows) - 1))
    return f"<rect class='chart-negative-band' x='{start_x:.1f}' y='{top}' width='{max(end_x - start_x, 2):.1f}' height='{plot_height}'></rect>"


def chart_date_label(value: str) -> str:
    return value if len(value) == 10 else short_date(value)


def negative_composite_clusters(rows: list[dict], min_days: int = 1) -> list[tuple[int, int]]:
    clusters = []
    start = None
    for index, row in enumerate(rows):
        if int(row.get("composite") or 0) < 0:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_days:
                clusters.append((start, index - 1))
            start = None
    if start is not None:
        if len(rows) - start >= min_days:
            clusters.append((start, len(rows) - 1))
    return clusters


def moving_average(values: list[float], window: int) -> list[float]:
    averaged = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        period = values[start : index + 1]
        averaged.append(sum(period) / len(period))
    return averaged


def evenly_spaced(start: float, end: float, count: int) -> list[float]:
    if count <= 1:
        return [start]
    return [start + (end - start) * index / (count - 1) for index in range(count)]


def breadth_composite_score(row: dict) -> int:
    statuses = [
        heat_status_from_value(row.get("pct_above_sma50"), 35, 45, 55, 65),
        heat_status_from_value(row.get("pct_above_sma200"), 35, 45, 55, 65),
        momentum_pair_status(row.get("new_highs_52w"), row.get("new_lows_52w")),
        heat_status_from_value(row.get("pct_within_5pct_52w_high"), 12, 18, 30, 36),
        momentum_pair_status(row.get("up_4pct"), row.get("down_4pct")),
        heat_status_from_value(row.get("ratio_4pct_5d"), 0.60, 0.85, 1.25, 1.75),
        heat_status_from_value(row.get("ratio_4pct_10d"), 0.60, 0.85, 1.25, 1.75),
        momentum_pair_status(row.get("up_25pct_3m"), row.get("down_25pct_3m"), 0.70, 0.90, 1.20, 1.80),
        speculative_status(row.get("up_50pct_1m"), row.get("down_50pct_1m")),
    ]
    return sum(heat_score(status) for status in statuses)


def composite_score_status(score: int) -> str:
    if score <= -8:
        return "strong-red"
    if score <= -3:
        return "light-red"
    if score < 3:
        return "neutral"
    if score < 8:
        return "light-green"
    return "strong-green"


def heat_score(status: str) -> int:
    return {
        "strong-red": -2,
        "light-red": -1,
        "neutral": 0,
        "light-green": 1,
        "strong-green": 2,
    }.get(status, 0)


def render_breadth_kpi_card(title: str, label: str, status: str, note: str, sparkline: str) -> str:
    return (
        f"<article class='metric-card {esc(status)}'>"
        f"<strong>{esc(title)}</strong>"
        f"<div class='big'>{esc(label)}</div>"
        f"{sparkline}"
        f"<p class='muted'>{esc(note)}</p>"
        "</article>"
    )


def percent_status(value: float | None) -> str:
    if value is None:
        return "na"
    if value > 60:
        return "green"
    if value >= 40:
        return "yellow"
    return "red"


def highs_lows_status(highs: int, lows: int) -> str:
    if highs > lows:
        return "green"
    if highs == lows:
        return "yellow"
    return "red"


def highs_lows_note(highs: int, lows: int) -> str:
    if highs > lows:
        return "Expansion leads breakdowns"
    if highs == lows:
        return "Balanced leadership and stress"
    return "Breakdowns exceed leadership"


def ratio_status(value: float | None) -> str:
    if value is None:
        return "na"
    if value > 1.5:
        return "green"
    if value >= 0.75:
        return "yellow"
    return "red"


def format_percent_value(value: float | None) -> str:
    return "N/A" if value is None else f"{float(value):.0f}%"


def format_ratio_value(value: float | None) -> str:
    return "N/A" if value is None else f"{float(value):.2f}"


def none_last(value: float | None) -> float:
    return -999 if value is None else float(value)


def render_sparkline(values: list[float], color: str) -> str:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return "<svg class='sparkline' viewBox='0 0 120 34' role='img' aria-label='No sparkline data'></svg>"
    min_value = min(clean)
    max_value = max(clean)
    span = max_value - min_value
    if span == 0:
        span = 1
    points = []
    for index, value in enumerate(clean):
        x = index / (len(clean) - 1) * 118 + 1
        y = 31 - ((value - min_value) / span * 26)
        points.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    fill = f"1,33 {line} 119,33"
    return (
        "<svg class='sparkline' viewBox='0 0 120 34' preserveAspectRatio='none' role='img' aria-label='20-day close sparkline'>"
        f"<path class='fill' d='M {fill} Z' fill='{esc(color)}'></path>"
        f"<path class='line' d='M {line}' stroke='{esc(color)}'></path>"
        "</svg>"
    )


def render_industry_leadership(rows: list[dict]) -> str:
    valid = [row for row in rows if row.get("return_1m") is not None]
    if not valid:
        return "<p>No industry performance data available yet.</p>"
    leaders = sorted(valid, key=lambda row: row["return_1m"], reverse=True)[:10]
    laggards = sorted(valid, key=lambda row: row["return_1m"])[:10]
    return (
        "<div class='industry-grid'>"
        f"<div><h3>Top 10 Industries</h3>{render_industry_table(leaders)}</div>"
        f"<div><h3>Bottom 10 Industries</h3>{render_industry_table(laggards)}</div>"
        "</div>"
    )


def render_industry_table(rows: list[dict]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{esc(row['industry'])}</td>"
        f"<td>{esc(row.get('sector') or '')}</td>"
        f"<td>{fmt(row.get('return_1w'), '{:.1%}')}</td>"
        f"<td>{fmt(row.get('return_1m'), '{:.1%}')}</td>"
        f"<td>{int(row.get('hit_count') or 0)}</td>"
        "</tr>"
        for row in rows
    )
    return (
        "<table class='compact-table'><thead><tr><th>Industry</th><th>Sector</th><th>1W</th><th>1M</th><th>Hits</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def render_hits_table(hits: list[dict]) -> str:
    if not hits:
        return "<p>No current research scanner hits.</p>"
    setup_options = render_filter_options(hits, "scanner_label", "All setups")
    sector_options = render_filter_options(hits, "sector", "All sectors")
    industry_options = render_filter_options(hits, "industry", "All industries")
    rows = []
    for hit in hits:
        scanner_label = hit.get("scanner_label") or hit.get("scanner_id") or ""
        sector = hit.get("sector") or ""
        industry = hit.get("industry") or ""
        rows.append(
            f"<tr data-scanner='{esc(scanner_label)}' data-sector='{esc(sector)}' data-industry='{esc(industry)}'>"
            f"{sort_cell('setup', scanner_label, render_scanner_tag(scanner_label, hit.get('trigger_note') or ''))}"
            f"{sort_cell('ticker', hit['symbol'], esc(hit['symbol']))}"
            f"{sort_cell('sector', sector, esc(sector))}"
            f"{sort_cell('industry', industry, esc(industry))}"
            f"{sort_cell('rs', hit['rs_rank'], fmt(hit['rs_rank'], '{:.0f}'), 'number')}"
            f"{sort_cell('perf_1w', hit.get('perf_1w'), fmt(hit.get('perf_1w'), '{:.1%}'), 'number')}"
            f"{sort_cell('perf_1m', hit['perf_1m'], fmt(hit['perf_1m'], '{:.1%}'), 'number')}"
            f"{sort_cell('ma_distance_atr', hit.get('ma_distance_atr'), fmt(hit.get('ma_distance_atr'), '{:.2f}'), 'number')}"
            f"{sort_cell('atr', hit['atr_pct'], fmt(hit['atr_pct'], '{:.1%}'), 'number')}"
            f"{sort_cell('avg_volume', hit.get('avg_volume_50d'), fmt_volume(hit.get('avg_volume_50d')), 'number')}"
            f"{sort_cell('distance_52w', hit['distance_to_52w_high'], fmt(hit['distance_to_52w_high'], '{:.1%}'), 'number')}"
            f"{sort_cell('also_in', hit.get('also_in') or '', render_scanner_tags(hit.get('also_in') or ''))}"
            "</tr>"
        )
    return (
        f"<p class='status-note'>{len(hits)} research hits displayed. Scanner coverage is tracked in Data Quality.</p>"
        "<div class='scanner-toolbar'>"
        "<label for='scanner-filter-setup'>Setup</label>"
        f"<select id='scanner-filter-setup' data-table-filter data-scanner-filter data-filter-key='scanner'>{setup_options}</select>"
        "<label for='scanner-filter-sector'>Sector</label>"
        f"<select id='scanner-filter-sector' data-table-filter data-filter-key='sector'>{sector_options}</select>"
        "<label for='scanner-filter-industry'>Industry</label>"
        f"<select id='scanner-filter-industry' data-table-filter data-filter-key='industry'>{industry_options}</select>"
        f"<span class='muted' data-visible-count data-count-label='hits'>{len(hits)} hits shown</span>"
        "</div>"
        "<table data-filter-table data-sort-table><thead><tr>"
        f"{sort_header('Setup', 'setup', 'ascending')}"
        f"{sort_header('Ticker', 'ticker', 'ascending')}"
        f"{sort_header('Sector', 'sector', 'ascending')}"
        f"{sort_header('Industry', 'industry', 'ascending')}"
        f"{sort_header('RS', 'rs', 'descending')}"
        f"{sort_header('1W', 'perf_1w', 'descending')}"
        f"{sort_header('1M', 'perf_1m', 'descending')}"
        f"{sort_header('MA ATR', 'ma_distance_atr', 'ascending')}"
        f"{sort_header('ATR%', 'atr', 'descending')}"
        f"{sort_header('Avg Vol', 'avg_volume', 'descending')}"
        f"{sort_header('52W Dist', 'distance_52w', 'descending')}"
        f"{sort_header('Also In', 'also_in', 'ascending')}"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def sort_header(label: str, key: str, default_direction: str) -> str:
    return (
        f"<th><button type='button' data-sort-key='{esc(key)}' "
        f"data-sort-default='{esc(default_direction)}' title='Sort by {esc(label)}'>{esc(label)}</button></th>"
    )


def sort_cell(key: str, value: object, display: str, sort_type: str = "text") -> str:
    missing = value is None or value == ""
    sort_value = "" if missing else value
    if sort_type == "number" and not missing:
        sort_value = f"{float(value):.12g}"
    return (
        f"<td data-sort-cell='{esc(key)}' data-sort-type='{esc(sort_type)}' "
        f"data-sort-value='{esc(sort_value)}' data-sort-missing='{str(missing).lower()}'>{display}</td>"
    )


def render_filter_options(hits: list[dict], key: str, all_label: str) -> str:
    values = sorted({str(hit.get(key) or "") for hit in hits if hit.get(key)})
    options = [f"<option value='all'>{esc(all_label)}</option>"]
    options.extend(f"<option value='{esc(value)}'>{esc(value)}</option>" for value in values)
    return "".join(options)


def render_scanner_tags(labels: str) -> str:
    parts = [part.strip() for part in labels.split(",") if part.strip()]
    if not parts:
        return ""
    return "<div class='tag-list'>" + "".join(render_scanner_tag(part) for part in parts) + "</div>"


def render_scanner_tag(label: str, tooltip: str = "") -> str:
    classes = {
        "Pullback MA10": "tag-ma10",
        "Pullback MA20": "tag-ma20",
        "3D Pullback": "tag-3d",
    }
    tag_class = classes.get(label, "tag-neutral")
    tooltip_attr = f" data-tooltip='{esc(tooltip)}' title='{esc(tooltip)}'" if tooltip else ""
    return f"<span class='tag {tag_class}'{tooltip_attr}>{esc(label)}</span>"


def render_logs(data: dict) -> str:
    run_items = "".join(f"<li>{esc(row['run_at'])}: {esc(row['step'])} - {esc(row['status'])}</li>" for row in data["runs"])
    quality_items = "".join(f"<li>{esc(row['checked_at'])}: {esc(row['check_name'])} - {esc(row['status'])}: {esc(row['message'])}</li>" for row in data["quality"])
    return (
        f"<div class='loggrid'><section><h2>Runs</h2><ul>{run_items}</ul></section>"
        f"<section><h2>Data Quality</h2><ul>{quality_items}</ul></section></div>"
        f"{render_extreme_return_events(data.get('extreme_returns', []))}"
    )


def render_extreme_return_events(rows: list[dict]) -> str:
    if not rows:
        return ""
    label_options = render_quality_label_options(rows)
    counts = quality_label_counts(rows)
    count_text = ", ".join(f"{label}: {count}" for label, count in counts.items())
    body = "".join(
        f"<tr data-label='{esc(row['label'])}'>"
        f"{sort_cell('symbol', row['symbol'], esc(row['symbol']))}"
        f"{sort_cell('date', row['date'], esc(row['date']))}"
        f"{sort_cell('return', row.get('daily_return'), fmt(row.get('daily_return'), '{:.1%}'), 'number')}"
        f"{sort_cell('previous_close', row.get('previous_close'), fmt(row.get('previous_close'), '{:.2f}'), 'number')}"
        f"{sort_cell('close', row.get('close'), fmt(row.get('close'), '{:.2f}'), 'number')}"
        f"{sort_cell('next_close', row.get('next_close'), fmt(row.get('next_close'), '{:.2f}'), 'number')}"
        f"{sort_cell('label', quality_label_rank(str(row['label'])), render_quality_label(str(row['label'])), 'number')}"
        f"{sort_cell('note', row['note'], esc(row['note']))}"
        "</tr>"
        for row in rows
    )
    return (
        "<section class='quality-detail'><h2>Extreme Return Diagnostics</h2>"
        f"<p class='status-note'>{len(rows)} extreme return events. {esc(count_text)}</p>"
        "<div class='scanner-toolbar'>"
        "<label for='quality-filter-label'>Label</label>"
        f"<select id='quality-filter-label' data-table-filter data-filter-key='label'>{label_options}</select>"
        f"<span class='muted' data-visible-count data-count-label='events'>{len(rows)} events shown</span>"
        "</div>"
        "<table class='compact-table' data-filter-table data-sort-table><thead><tr>"
        f"{sort_header('Symbol', 'symbol', 'ascending')}"
        f"{sort_header('Date', 'date', 'descending')}"
        f"{sort_header('Return', 'return', 'descending')}"
        f"{sort_header('Prev Close', 'previous_close', 'descending')}"
        f"{sort_header('Close', 'close', 'descending')}"
        f"{sort_header('Next Close', 'next_close', 'descending')}"
        f"{sort_header('Label', 'label', 'ascending')}"
        f"{sort_header('Note', 'note', 'ascending')}"
        "</tr></thead>"
        f"<tbody>{body}</tbody></table></section>"
    )


def render_quality_label_options(rows: list[dict]) -> str:
    labels = {str(row.get("label") or "") for row in rows if row.get("label")}
    ordered = sorted(labels, key=quality_label_rank)
    options = ["<option value='all'>All labels</option>"]
    options.extend(f"<option value='{esc(label)}'>{esc(label)}</option>" for label in ordered)
    return "".join(options)


def quality_label_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: quality_label_rank(str(item.get("label") or ""))):
        label = str(row.get("label") or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def quality_label_rank(label: str) -> int:
    order = {
        "missing_corporate_action": 0,
        "possible_data_error": 1,
        "corporate_action": 2,
        "likely_real_move": 3,
    }
    return order.get(label, 99)


def render_quality_label(label: str) -> str:
    return f"<span class='quality-label {esc(label)}'>{esc(label)}</span>"


def render_source_notice(sources: list[dict]) -> str:
    names = {str(row["source"]) for row in sources}
    if "mock-fallback" in names:
        return "<div class='source-notice'>Warning: yfinance failed and this build used mock-fallback data. Do not read scanner hits as current market output.</div>"
    if "mock" in names and "yfinance" not in names:
        return "<div class='source-notice'>Warning: this build uses deterministic mock data. Values are for pipeline validation only.</div>"
    return ""


def source_summary(sources: list[dict]) -> str:
    if not sources:
        return "Price source: none"
    parts = [f"{row['source']} ({row['n']})" for row in sources]
    return "Price source: " + ", ".join(parts)


def operation_summary(sources: list[dict], quality: list[dict], active_equities: int, priced_equities: int) -> str:
    source_names = ", ".join(str(row["source"]) for row in sources) or "none"
    max_date = max((str(row["max_date"]) for row in sources if row.get("max_date")), default="N/A")
    checks = latest_checks_by_name(quality)
    ohlc = checks.get("invalid_ohlc", {}).get("status", "na")
    returns = checks.get("extreme_daily_returns", {})
    corp = checks.get("corporate_action_returns", {})
    return_warnings = warning_count_from_message(str(returns.get("message", "")))
    corporate_warnings = warning_count_from_message(str(corp.get("message", "")))
    return (
        f"{source_names} | data {max_date} | equities {priced_equities}/{active_equities} | "
        f"OHLC {ohlc} | returns {return_warnings} unexplained / {corporate_warnings} corporate-action"
    )


def latest_checks_by_name(quality: list[dict]) -> dict[str, dict]:
    checks: dict[str, dict] = {}
    for row in quality:
        checks.setdefault(str(row["check_name"]), row)
    return checks


def warning_count_from_message(message: str) -> int:
    for token in message.split():
        if token.isdigit():
            return int(token)
    return 0


def render_metric_delta(row: dict) -> str:
    value = row.get("value")
    change = row.get("change_1w")
    if value is None or change is None:
        return "<div class='context muted'>1W change N/A</div>"
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    arrow = "&uarr;" if direction == "up" else "&darr;" if direction == "down" else "&rarr;"
    return f"<div class='context'><span class='delta-{direction}'>{arrow} {format_metric_change(row['metric_id'], change)}</span><span class='muted'>vs 1W ago</span></div>"


def format_metric_change(metric_id: str, change: float) -> str:
    if metric_id == "breadth_sp500_above_sma50":
        return f"{change:+.0f} pp"
    if metric_id in {"risk_xly_xlp_trend", "obos_spy_sma50_atr"}:
        return f"{change:+.2f}"
    if metric_id == "volatility_vix":
        return f"{change:+.1f}"
    return f"{change:+.1f}"


def metric_title(metric_id: str) -> str:
    titles = {
        "breadth_sp500_above_sma50": "Breadth",
        "sentiment_fear_greed": "Sentiment",
        "risk_xly_xlp_trend": "Risk On/Off",
        "credit_hy_oas": "Credit",
        "volatility_vix": "Volatility",
        "obos_spy_sma50_atr": "OB/OS",
    }
    return titles.get(metric_id, metric_id)


def return_color(value: float) -> str:
    if value >= 0.04:
        return "#39b99f"
    if value >= 0:
        return "#bfe9df"
    if value >= -0.03:
        return "#f4c7cb"
    return "#df7882"


def fmt(value: float | None, pattern: str) -> str:
    return "N/A" if value is None else pattern.format(value)


def fmt_volume(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)
