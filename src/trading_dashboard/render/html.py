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
        sources = conn.execute("SELECT source, COUNT(*) AS n, MAX(date) AS max_date FROM prices GROUP BY source ORDER BY source").fetchall()
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
    return {
        "latest_date": latest_metric or "No data",
        "metrics": [dict(row) for row in metrics],
        "sectors": [dict(row) for row in sectors],
        "industries": industry_rows_with_hit_counts([dict(row) for row in industries], [dict(row) for row in hits]),
        "hits": [dict(row) for row in hits],
        "runs": [dict(row) for row in runs],
        "quality": [dict(row) for row in quality],
        "sources": [dict(row) for row in sources],
        "operation": operation_summary([dict(row) for row in sources], [dict(row) for row in quality], active_equities, priced_equities),
        "indexes": [dict(row) for row in indexes],
    }


def industry_rows_with_hit_counts(industries: list[dict], hits: list[dict]) -> list[dict]:
    hit_counts: dict[str, int] = {}
    for hit in hits:
        industry = hit.get("industry")
        if industry:
            hit_counts[industry] = hit_counts.get(industry, 0) + 1
    for row in industries:
        row["hit_count"] = hit_counts.get(row.get("industry"), 0)
    return industries


def render_index(data: dict) -> str:
    metric_pills = "\n".join(render_metric_pill(row) for row in data["metrics"])
    index_cards = "\n".join(render_index_card(row) for row in data["indexes"])
    sectors = render_sector_groups(data["sectors"])
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
        <section class="state-strip">
          <h1>Market State</h1>
          <div class="pills">{metric_pills}</div>
          <p>Read dimensions individually. No auto-composite.</p>
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
            f"<h1>{title}</h1>{render_sector_groups(data['sectors'])}"
            f"<h2>Industry Leadership</h2>{render_industry_leadership(data['industries'])}"
        )
    else:
        related = [row for row in data["metrics"] if slug.split("-")[0] in row["metric_id"] or title.lower().split()[0] in row["metric_id"]]
        cards = "".join(render_metric_card(row) for row in related) or "<p>No dedicated metric rows available yet.</p>"
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
      --green: #248a4b;
      --yellow: #b58200;
      --red: #c74444;
      --blue: #2368a2;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }}
    a {{ color: var(--blue); text-decoration: none; }}
    .topbar {{ min-height: 58px; display: flex; align-items: center; gap: 20px; padding: 0 24px; border-bottom: 1px solid var(--line); background: var(--panel); flex-wrap: wrap; }}
    nav {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 14px; }}
    .operation-status {{ margin-left: auto; text-align: right; font-size: 12px; line-height: 1.35; color: var(--muted); }}
    .index-strip, .state-strip, .logs, main {{ max-width: 1180px; margin: 18px auto; padding: 0 18px; }}
    .index-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
    .index-card, .metric-card, section, .state-strip {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .index-card strong, .metric-card strong {{ display: block; font-size: 13px; color: var(--muted); }}
    .big {{ font-size: 32px; font-weight: 700; margin: 8px 0; }}
    .context {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: 14px; }}
    .delta-up {{ color: var(--green); font-weight: 700; }}
    .delta-down {{ color: var(--red); font-weight: 700; }}
    .delta-flat {{ color: var(--muted); font-weight: 700; }}
    .state-strip {{ display: flex; align-items: center; gap: 22px; }}
    .state-strip h1 {{ margin: 0; font-size: 28px; }}
    .pills, .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; flex: 1; }}
    .pill {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--panel); }}
    .green {{ border-top: 5px solid var(--green); }}
    .yellow {{ border-top: 5px solid var(--yellow); }}
    .red {{ border-top: 5px solid var(--red); }}
    .na {{ border-top: 5px solid var(--muted); }}
    .dashboard {{ display: grid; gap: 16px; }}
    .full-width {{ width: 100%; }}
    section h2 {{ margin-top: 0; font-size: 18px; }}
    .heatmap {{ display: grid; grid-template-columns: repeat(auto-fill, 118px); gap: 8px; justify-content: start; }}
    .sector-groups {{ display: grid; gap: 12px; }}
    .sector-group h3 {{ margin: 0 0 8px; font-size: 14px; color: var(--muted); }}
    .sector {{ min-height: 92px; border-radius: 6px; padding: 10px; color: #101820; border: 1px solid rgba(0,0,0,.08); }}
    .sector b {{ font-size: 18px; }}
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
    @media (max-width: 850px) {{
      .industry-grid {{ grid-template-columns: 1fr; }}
      .state-strip {{ align-items: stretch; flex-direction: column; }}
    }}
  </style>
</head>
<body>
{body}
<script>
  document.querySelectorAll('[data-scanner-table]').forEach((table) => {{
    const container = table.closest('section') || document;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const count = container.querySelector('[data-scanner-count]');
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
      if (count) count.textContent = `${{visible}} hits shown`;
    }};
    filters.forEach((filter) => filter.addEventListener('change', update));
    update();
  }});
  document.querySelectorAll('[data-scanner-table]').forEach((table) => {{
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


def render_metric_card(row: dict) -> str:
    return f"""
    <article class="metric-card {esc(row['status'])}">
      <strong>{esc(metric_title(row['metric_id']))}</strong>
      <div class="big">{esc(row['label'] or 'N/A')}</div>
      {render_metric_delta(row)}
      <p class="muted">{esc(row['note'] or '')}</p>
    </article>"""


def render_metric_pill(row: dict) -> str:
    return f"<div class='pill {esc(row['status'])}'><strong>{esc(metric_title(row['metric_id']))}</strong><br>{esc(row['label'] or 'N/A')}{render_metric_delta(row)}</div>"


def render_index_card(row: dict) -> str:
    change = row["change_1d"]
    change_text = "N/A" if change is None else f"{change:.2%}"
    return f"<article class='index-card'><strong>{esc(row['symbol'])}</strong><div class='big'>{row['close']:.2f}</div><span>{esc(change_text)}</span></article>"


def render_sector_tile(row: dict) -> str:
    ret_1w = row["return_1w"]
    ret_1m = row["return_1m"]
    if ret_1w is None:
        color = "#edf0f4"
        text_1w = "N/A"
    else:
        color = return_color(float(ret_1w))
        text_1w = f"{ret_1w:.1%}"
    text_1m = "N/A" if ret_1m is None else f"{ret_1m:.1%}"
    return (
        f"<div class='sector' style='background:{color}'>"
        f"<strong>{esc(row['symbol'])}</strong><br>{esc(row['sector'])}<br>"
        f"<b>{text_1w}</b><br><span class='muted'>1M {text_1m}</span></div>"
    )


def render_sector_groups(rows: list[dict]) -> str:
    positive = [row for row in rows if row.get("return_1w") is not None and row["return_1w"] >= 0]
    negative = [row for row in rows if row.get("return_1w") is None or row["return_1w"] < 0]
    positive_tiles = "".join(render_sector_tile(row) for row in positive) or '<p class="muted">No positive sectors.</p>'
    negative_tiles = "".join(render_sector_tile(row) for row in negative) or '<p class="muted">No negative sectors.</p>'
    return (
        "<div class='sector-groups'>"
        f"<div class='sector-group sector-positive'><h3>Positive 1W</h3><div class='heatmap'>{positive_tiles}</div></div>"
        f"<div class='sector-group sector-negative'><h3>Negative 1W</h3><div class='heatmap'>{negative_tiles}</div></div>"
        "</div>"
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
            f"{sort_cell('ma_distance', hit.get('ma_distance_pct'), fmt(hit.get('ma_distance_pct'), '{:.1%}'), 'number')}"
            f"{sort_cell('atr', hit['atr_pct'], fmt(hit['atr_pct'], '{:.1%}'), 'number')}"
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
        f"<span class='muted' data-scanner-count>{len(hits)} hits shown</span>"
        "</div>"
        "<table data-scanner-table><thead><tr>"
        f"{sort_header('Setup', 'setup', 'ascending')}"
        f"{sort_header('Ticker', 'ticker', 'ascending')}"
        f"{sort_header('Sector', 'sector', 'ascending')}"
        f"{sort_header('Industry', 'industry', 'ascending')}"
        f"{sort_header('RS', 'rs', 'descending')}"
        f"{sort_header('1W', 'perf_1w', 'descending')}"
        f"{sort_header('1M', 'perf_1m', 'descending')}"
        f"{sort_header('MA Dist', 'ma_distance', 'ascending')}"
        f"{sort_header('ATR%', 'atr', 'descending')}"
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
    return f"<div class='loggrid'><section><h2>Runs</h2><ul>{run_items}</ul></section><section><h2>Data Quality</h2><ul>{quality_items}</ul></section></div>"


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
        return "#5dbb6a"
    if value >= 0:
        return "#b8d98c"
    if value >= -0.03:
        return "#f0c66f"
    return "#e46f61"


def fmt(value: float | None, pattern: str) -> str:
    return "N/A" if value is None else pattern.format(value)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)
