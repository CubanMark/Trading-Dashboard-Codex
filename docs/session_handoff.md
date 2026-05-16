# Session Handoff - Trading Dashboard

Stand: 2026-05-16, Tagesabschluss
Phase: 1 MVP
Remote: `https://github.com/CubanMark/Trading-Dashboard-Codex`
Aktueller Branch: `main`

## Wiedereinstieg

Vor jeder neuen Aufgabe weiterhin `PROJECT_BRIEF.md` lesen.

Der Ordner `G:\Meine Ablage\05_Projekte\Trading\04_Trading-Dashboard-Claude` bleibt tabu, sofern Markus ihn nicht erneut explizit freigibt. Das Claude-Parallelprojekt wird nicht weiter fortgefuehrt; relevante Erkenntnisse wurden bereits in dieses Projekt uebernommen oder dokumentiert.

## Aktueller Stand

Das Projekt ist ein funktionierendes Phase-1-End-of-Day-Dashboard:

- Python-Package unter `src/trading_dashboard/`
- CLI: `python -m trading_dashboard init-db|fetch|compute|render|update`
- SQLite fuer Preise, Corporate Actions, Sentiment, Breadth, Marktdimensionen, Sektor-/Industry-Returns, Scanner-Hits, Run-Log und Data-Quality-Checks
- yfinance als Preisquelle mit unadjusted OHLCV und separaten Corporate Actions
- CNN Fear & Greed als optionale Sentimentquelle
- deterministischer Mock-Modus fuer Tests und Offline-Laeufe
- statische HTML-Seiten unter `pages/`
- GitHub-Actions-Workflow fuer Daily Build und GitHub Pages
- DB-Cache im GitHub-Actions-Workflow
- S&P-1500-nahe Universe-Datei unter `inputs/universe/sp1500_universe_filtered.csv`

## Neue wichtige Aenderungen

### Inkrementeller yfinance-Fetch

Der yfinance-Fetch ist jetzt inkrementell:

- vorhandene `yfinance`-Historie pro Symbol wird erkannt
- bestehende Symbole laden nur ab `letztes yfinance-Datum - 10 Tage`
- neue Symbole oder Symbole mit bisher nur Mock-Historie bekommen weiterhin einen Full-Fetch ueber `--years`
- echte yfinance-Daten werden per Upsert gespeichert
- alte Mock-Historie wird beim ersten echten yfinance-Fetch symbolweise ersetzt
- bei yfinance-Ausfall und vorhandener DB-Historie wird die bestehende Historie behalten; es wird nicht mehr automatisch alles mit Mock-Daten ueberschrieben
- Data-Quality-Pruefung laeuft nach dem Upsert gegen den vollstaendigen gespeicherten Datenbestand, nicht nur gegen das kurze Nachladefenster

Relevante Dateien:

- `src/trading_dashboard/data/fetch.py`
- `src/trading_dashboard/data/storage.py`
- `tests/test_fetch_replaces_sources.py`

### Breadth Composite und Regime

Die Breadth-Seite hat jetzt:

- Breadth-KPIs fuer Participation und Momentum
- Heatmap-Historie mit Year-Selector
- Composite-Spalte in der Historie
- Composite-Gauge
- `SPY vs Breadth Composite` Chart mit YTD/1Y/3Y/5Y
- 5D-Composite-Linie und rote Baender fuer 3+ negative Tages-Composite-Tage
- Regime-Label direkt in der Composite-Box

Aktuelle Regime:

- `Damaged`: 5D-Composite < 0 oder mindestens 3 Tage in Folge Composite < 0
- `Healing`: 1 bis 10 Handelstage nach Ende von Damaged, sofern 5D-Composite wieder > 0
- `Weakening`: 5D-Composite > 0, aber ueber 5 Handelstage um mindestens 4 Punkte gefallen
- `Positive`: 5D-Composite > 3
- `Other`: kein klares Regime

Research-Ergebnis aus Swing Lab:

- `Healing` ist der robusteste positive Befund fuer Pullback-Kontext.
- `Weakening` ist ein Vorsichtssignal, kein Verkaufssignal.
- `Damaged` ist kein blindes Kaufsignal; SPY-Trendkontext ist wichtig.
- Filter B wurde im Holdout verworfen.

Relevante Dateien:

- `docs/breadth_composite_research.md`
- `src/trading_dashboard/render/html.py`
- `tests/test_integration_mock_update.py`

### Scanner

Der Pullback-Research-Scanner bleibt ausdruecklich ein Research-/Watchlist-Werkzeug, kein akzeptierter Trading Edge.

Aktuelle Regeln:

- SPY ueber SMA200
- Aktie ueber SMA50, SMA50 ueber SMA200
- letzter Schlusskurs mindestens 10 USD
- durchschnittliches 50-Tage-Volumen mindestens 750.000 Aktien
- RS-Rang mindestens 70
- Schlusskurs maximal 30% unter 52W-Hoch
- MA10/MA20-Pullbacks verwenden ATR-normalisierte Distanz: maximal `0.75 * ATR14` vom jeweiligen SMA
- Symbole mit `missing_corporate_action` oder `possible_data_error` werden aus dem Scanner ausgeschlossen

Scanner-Tabelle:

- Setup, Ticker, Sector, Industry
- RS, 1W, 1M
- `MA ATR`
- ATR%
- Avg Volume
- 52W Distance
- Overlap-Chips in `Also In`
- gekoppelte Filter fuer Setup/Sector/Industry

Regeln dokumentiert in `docs/pullback_scanner_rules.md`.

### Neue Detailseiten

Neben Breadth existieren jetzt echte Minimal-Detailseiten:

- `sentiment.html`: CNN Fear & Greed
- `risk.html`: XLY/XLP
- `volatility.html`: VIX und VIX/VIX3M-Kontext
- `credit-macro.html`: TLT/HYG/LQD als Proxy, HY OAS noch nicht angebunden
- `sectors.html`
- `scanners.html`

## Letzte Verifikation

Zuletzt erfolgreich:

```powershell
python -m pytest tests/test_fetch_replaces_sources.py tests/test_storage.py -q -p no:cacheprovider
# 9 passed

python -m pytest -q -p no:cacheprovider
# 34 passed

python -m trading_dashboard compute
# erfolgreich

python -m trading_dashboard render
# erfolgreich
```

Ein echter Live-`update --years 5` gegen yfinance wurde nach der inkrementellen Umstellung bewusst nicht mehr gestartet, um keinen unnoetigen Provider-/Rate-Limit-Lauf am Tagesende auszuloesen. Code-seitig gilt `--years 5` jetzt nur noch fuer Bootstrap-Symbole ohne vorhandene yfinance-Historie; bestehende Symbole laden inkrementell.

## Git-Status zum Tagesabschluss

Bekannte lokale Aenderungen:

- `docs/breadth_composite_research.md`
- `src/trading_dashboard/data/fetch.py`
- `src/trading_dashboard/data/storage.py`
- `src/trading_dashboard/render/html.py`
- `tests/test_fetch_replaces_sources.py`
- `tests/test_integration_mock_update.py`
- `docs/session_handoff.md`

Untracked:

- `.claude/settings.local.json`

Empfehlung: `.claude/` nicht committen. Das ist lokale Claude-Konfiguration mit breiten lokalen Berechtigungen.

## Offene Risiken

Hohe Prioritaet:

- GitHub Pages/Actions live verifizieren: Workflow ist vorhanden, DB-Cache ist eingebaut, aber der aktuelle Live-Run/Pages-Status muss noch in GitHub geprueft werden.
- Ersten echten Daily-Run mit inkrementellem Fetch beobachten: besonders Anzahl geladener Zeilen, `incremental_fetch`-Quality-Log, missing/stale symbols und Pages-Output.
- Extreme-Return-Diagnostik fachlich weiter beobachten; `missing_corporate_action` und `possible_data_error` bleiben Scanner-Ausschlussgruende.

Mittlere Prioritaet:

- HY OAS/FRED noch nicht angebunden; Credit-Seite nutzt HYG/LQD/TLT als Proxy.
- Breadth-Research nutzt aktuelles Universum und enthaelt Survivorship Bias.
- `new_highs_52w`-Abweichung zwischen Dashboard und Swing-Lab-Research klaeren: wahrscheinlich Lookback-/Randbehandlung.
- Detailseiten sind brauchbare MVP-Seiten, aber noch kein voller fachlicher Drilldown.
- Sektor-Heatmap hat noch keinen Zeitraum-Toggle.

## Empfohlene naechste Schritte

1. GitHub Actions/Pages pruefen:
   - letzten Workflow-Lauf anschauen
   - Pages-URL oeffnen
   - DB-Cache-Verhalten im zweiten Run kontrollieren

2. Einen echten inkrementellen Update-Lauf kontrolliert ausfuehren:
   - `python -m trading_dashboard update --years 5`
   - danach Data-Quality-Log und `incremental_fetch` pruefen
   - sicherstellen, dass keine Mock-Historie in yfinance-Historie stehen bleibt

3. Pipeline-Dokumentation aktualisieren:
   - README um inkrementelles Fetch-Verhalten erweitern
   - ggf. kurze Notiz zu GitHub-Actions-Betrieb und DB-Cache

4. Danach fachlich:
   - SPY-Trendkontext fuer Breadth-Regime in der UI sichtbarer machen
   - HY OAS/FRED optional anbinden
   - Sektor-Heatmap-Zeitraeume pruefen

## Lokale Befehle

Tests:

```powershell
python -m pytest -q -p no:cacheprovider
```

Mock-Update:

```powershell
python -m trading_dashboard update --mock --years 2
```

Echte Daten aktualisieren:

```powershell
python -m trading_dashboard update --years 5
```

Nur berechnen/rendern:

```powershell
python -m trading_dashboard compute
python -m trading_dashboard render
```

Status:

```powershell
git status --short
```
