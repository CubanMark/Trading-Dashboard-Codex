# Trading Dashboard

Phase-1-MVP fuer ein persoenliches End-of-Day Trading Dashboard fuer US-Maerkte.

## Was Phase 1 liefert

- SQLite-Historie fuer Preise, Corporate Actions, Marktdimensionen, Sektor-Returns und Scanner-Hits.
- Datenpipeline mit yfinance als primaerer Quelle und Mock-Modus fuer Tests/offline Builds.
- Statisches HTML-Dashboard unter `pages/index.html`.
- Minimale Drilldown-Seiten fuer Breadth, Sentiment, Risk, Credit/Macro, Volatility, Sectors und Scanners.
- Pullback-v2a als Research-/Watchlist-Scanner, ausdruecklich nicht als akzeptierter Trading Edge.
- GitHub Actions Workflow fuer Daily Build und GitHub Pages.
- S&P-1500-Naeherungsuniversum aus `inputs/universe/sp1500_universe_filtered.csv`.

## Schnellstart

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -e .
.\.venv\Scripts\python -m trading_dashboard update --mock
```

Danach `pages/index.html` im Browser oeffnen.

Der Standardlauf nutzt ein 1-Jahres-Fenster. Das reicht fuer SMA50, SMA200, ATR und den Research-Scanner und haelt den yfinance-Build fuer das grosse Universum handhabbar.

## CLI

```powershell
python -m trading_dashboard init-db
python -m trading_dashboard fetch --mock
python -m trading_dashboard compute
python -m trading_dashboard render
python -m trading_dashboard update --mock
python -m trading_dashboard update --years 1
```

Ohne `--mock` nutzt die Pipeline yfinance, falls das Paket installiert ist und Netzwerk verfuegbar ist.

## Wichtige fachliche Grenzen

- Keine Realtime-Daten.
- Keine TradingView-Konkurrenz mit Einzelchart-Analyse oder Drawing.
- Keine Phase-2/3-Features wie VCP, Breakout, RRG oder Journal.
- Kein Import aus Schwesterprojekten. Swing-Lab-Regeln werden dokumentiert und lokal neu implementiert.
