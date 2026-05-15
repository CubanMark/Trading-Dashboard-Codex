# Session Handoff - Trading Dashboard

Stand: 2026-05-15, Update nach Extreme-Return-Diagnostik
Phase: 1 MVP
Baseline-Commit: `e9e41bb Create phase 1 MVP baseline`

## Zweck dieser Datei

Diese Datei ist der kompakte Wiedereinstiegspunkt fuer eine neue Codex-Session. Vor jeder neuen Aufgabe weiterhin `PROJECT_BRIEF.md` lesen. Der Ordner `G:\Meine Ablage\05_Projekte\Trading\04_Trading-Dashboard-Claude` bleibt tabu.

## Aktueller Projektstand

Das Projekt hat eine funktionierende Phase-1-MVP-Basis:

- Python-Package unter `src/trading_dashboard/`
- CLI mit `python -m trading_dashboard init-db|fetch|compute|render|update`
- SQLite-Schema fuer Preise, Symbole, Corporate Actions, Marktmetriken, Sektor-/Industry-Returns, Scanner-Hits, Run-Log und Data-Quality-Checks
- yfinance-Fetch mit unadjusted OHLCV und separaten Corporate Actions
- deterministischer Mock-Modus fuer Tests und Offline-Laeufe
- statische HTML-Seiten unter `pages/`
- GitHub-Actions-Workflow fuer Pages-Build
- Tests fuer Indikatoren, Storage, Universe-Loader, Pullback-Scanner, Fetch-Replacement und Mock-Integration
- persistierte Breadth-Historie in `breadth_daily` mit SMA50/SMA200, 52W Highs/Lows, Coverage und Momentum-Breadth-Zaehlungen
- persistierte Extreme-Return-Diagnostik in `extreme_return_events`

Letzte bekannte Verifikation:

```powershell
python -m pytest -q -p no:cacheprovider
# 24 passed
```

Zusaetzliche lokale Verifikation:

```powershell
$env:PYTHONPATH='src'; python -m trading_dashboard update --mock --years 2
# erfolgreich; benoetigte wegen gesperrtem db/-Schreibzugriff eine einmalige Eskalation

$env:PYTHONPATH='src'; python -m trading_dashboard update --years 1
# erfolgreich mit yfinance; Dashboard-Datenstand 2026-05-13
# letzter Lauf meldete ANF und BAC als fehlende yfinance-Downloads
```

## Dashboard-Status

Die Homepage zeigt derzeit:

- Index-Strip fuer SPY, QQQ, IWM, VIX/TLT-Kontext mit kleinen Sparklines
- Market-State-Pills fuer sechs Dimensionen
- Breadth-Pill mit Historien-Sparkline und Kontext zu SMA200 sowie 52W Highs/Lows
- kompakte Sektor-Heatmap fuer 1W und 1M
- Industry Leadership mit Top 10 und Bottom 10
- Research Scanner Hits ueber die volle Breite
- Run Status und Data Quality Log

Die redundante `Dimension Snapshot`-Sektion wurde entfernt, weil sie inhaltlich fast identisch zum Market State war.

Neu gehaertet:

- Mock- und yfinance-Fetches laufen durch dieselbe Data-Quality-Pruefung.
- Dashboard zeigt bei `mock` und `mock-fallback` eine prominente Source-Warnung.
- Data-Quality-Log umfasst jetzt Missing Symbols mit Beispielen, stale Symbols mit Beispielen, nonpositive OHLC, unplausible OHLC-Beziehungen, extreme Tagesrenditen und Universe Coverage.
- Compute loggt zusaetzlich Coverage fuer die tatsaechlich verwendeten Equity-Symbole und Mapping-Luecken fuer Sector/Industry.
- Aktueller Mock-Lauf: 1244 aktive Equities, 1244 geladen, 1244 mit >= 220 Zeilen; 2 Industry-Mapping-Luecken (`PINS`, `ULS`).
- yfinance-Daily-Fetch filtert den laufenden Kalendertag heraus, damit keine intraday/unfertigen Tagesbalken in ein EOD-Dashboard geraten. Das behob eine falsche `invalid_ohlc`-Warnung fuer 2026-05-14.
- Aktueller yfinance-Lauf: Datenstand 2026-05-13, 1244 aktive Equities, 1244 geladen, 0 invalid OHLC, 0 nonpositive OHLC, 0 stale Symbols.
- Manuelle Universe-Klassifikations-Overrides:
  - `ULS`: Commercial Services / Miscellaneous Commercial Services
  - `PINS`: Technology Services / Internet Software / Services
  Nach Recompute/Render: `symbol_mapping_coverage` ist `ok` mit 0 fehlenden Sector/Industry-Werten.
- EOD-Cutoff nutzt New-York-Zeit: vor 17:30 ET wird der aktuelle Tagesbalken entfernt, nach 17:30 ET bleibt er erlaubt.
- Dashboard-Topbar zeigt eine kompakte Betriebszeile: Quelle, letztes Daten-Datum, Equity-Coverage, OHLC-Status und Return-Warnungen.
- Extreme Tagesrenditen werden getrennt geloggt als `corporate_action_returns` und `extreme_daily_returns`.
- Extreme Tagesrenditen werden zusaetzlich in `extreme_return_events` gespeichert und auf der Homepage unter `Extreme Return Diagnostics` angezeigt: Symbol, Datum, Return, vorheriger Schlusskurs, Schlusskurs, naechster Schlusskurs, Label und Diagnosehinweis.
- Aktueller yfinance-Lauf vom 2026-05-15: Datenstand 2026-05-14, 1244/1244 Equities, 0 Missing Symbols nach Retry, 14 extreme Returns; davon 4 `missing_corporate_action`, 10 `likely_real_move`, 0 `possible_data_error`.
- Scanner-Coverage wird geloggt: letzter echter Lauf 1150 Symbole gescannt, 93 per Industry ausgeschlossen, 75 Research Hits.
- Breadth-Historie wird bei `compute` aus den gespeicherten Kursen neu aufgebaut und bei `render` auf `/breadth.html` als Tabelle der letzten 30 Handelstage angezeigt. Die Homepage nutzt dieselbe Historie fuer die Breadth-Sparkline.
- `/breadth.html` trennt jetzt `Participation Breadth` und `Momentum Breadth`. Participation zeigt SMA50, SMA200, 52W Highs/Lows und Near-52W-High ohne redundanten `valid symbols`-Text in jeder KPI-Karte. Momentum zeigt die wichtigsten Market-Monitor-inspirierten Werte: 4% Up/Down taeglich, 5D- und 10D-Ratio daraus, 25% Up/Down ueber 3M sowie 50% Up/Down ueber 1M. Die Historientabelle enthaelt dieselben neuen Spalten.

## Scanner-Status

Der Pullback-Research-Scanner ist als Watchlist-/Research-Ausgabe umgesetzt, nicht als akzeptierter handelbarer Edge.

Die fachlichen Regeln sind dokumentiert in `docs/pullback_scanner_rules.md`.

Aktuelle Varianten:

- `3D Pullback`
- `Pullback MA10`
- `Pullback MA20`

Scanner-Tabelle:

- sortierbar nach Setup, Ticker, Sector, Industry, Relative Strength, 1W, 1M, MA Distance, ATR, 52W Distance und Also In
- zeigt jetzt auch das durchschnittliche 50-Tage-Volumen (`Avg Vol`)
- Setup wird als farbiger Chip angezeigt
- Trigger-Hinweis erscheint im Hover-Tooltip des Setup-Chips
- `Also In` zeigt Ueberschneidungen als farbige Chips
- Filter fuer Setup, Sector und Industry sind gekoppelt: die Dropdown-Optionen reagieren auf die jeweils aktiven anderen Filter

Aktive Pullback-Basisfilter:

- SPY ueber SMA200
- Aktie ueber SMA50, SMA50 ueber SMA200
- letzter Schlusskurs mindestens 10 USD
- durchschnittliches 50-Tage-Volumen mindestens 750.000 Aktien
- RS-Rang mindestens 70
- Schlusskurs maximal 30% unter 52W-Hoch

Letzter lokaler Compute/Render nach Schaerfung: 62 Research Hits.

## Wichtige Entscheidungen

- Keine Imports aus Swing Lab oder anderen Trading-Projekten.
- Keine gemeinsame `shared/`-Library in Phase 1.
- Rohpreise werden als unadjusted OHLCV gespeichert; Corporate Actions separat.
- Fehlende optionale Quellen duerfen keine erfundenen Werte erzeugen.
- Sentiment/Fear & Greed und FRED/HY-OAS bleiben sichtbar als nicht verfuegbar, solange keine robuste Quelle konfiguriert ist.
- Keine Auto-Composite-Ampel. Die Dimensionen bleiben separat interpretierbar.
- Generierte HTML-Seiten und SQLite-Dateien sind bewusst nicht committed.

## Datenstand und Universum

Aktuell existiert eine gefilterte Universe-Datei:

`inputs/universe/sp1500_universe_filtered.csv`

Zielbild ist nicht ein kleines Testuniversum, sondern die 1.500 liquidesten Aktien bzw. ein S&P-1500-naher Workflow mit Liquiditaetsfilter. Die aktuelle Datei ist Teil der Baseline, aber die Datenqualitaets- und Universe-Checks muessen als naechster Schwerpunkt gehaertet werden.

## Offene Risiken

Hohe Prioritaet:

- yfinance-Teilfehler treten tatsaechlich auf. Letzter Lauf meldete `NPO` im Batch als fehlend, der Retry/Endstatus zeigte danach aber 1244/1244 geladene Equities und `missing_symbols - ok`.
- Extreme Tagesrenditen bleiben fachlich zu klaeren. Letzter yfinance-Lauf: 14 unexplained, 0 corporate-action-related; Diagnose-Tabelle nennt u.a. `AAP`, `APLS`, `ASGN`, `CORT`, `HTZ`, `PRIM`.

Mittlere Prioritaet:

- Detailseiten sind noch minimal; Breadth hat jetzt den ersten echten Historien-Drilldown, die uebrigen Dimensionen brauchen noch Verlauf/Kontext.
- Industry Leadership ist nuetzlich, aber noch keine echte RRG-/Leadership-Analyse.
- Pullback-Regeln sollten fachlich final dokumentiert werden.

## Empfohlene naechste Schritte

1. Extreme Tagesrenditen fachlich entscheiden:
   - `missing_corporate_action`-Faelle aus `extreme_return_events` gegen Splits/Corporate Actions pruefen
   - entscheiden, ob man manuelle Corporate-Action-Overrides pflegt oder zunaechst nur sichtbar warnt
   - keine Adjusted-Werte heimlich einmischen; Phase-1-Entscheidung bleibt unadjusted + Corporate Actions separat

2. yfinance-Fehlermeldungen behandeln:
   - `ANF` und `BAC` gegen erneuten Lauf/Einzelticker-Fetch pruefen
   - entscheiden, ob fehlende Symbole retrybar, temporär oder aus dem Universum zu entfernen sind

3. Universe-Workflow stabilisieren:
   - Liquiditaetsfilter dokumentieren
   - Anzahl verwendeter Werte in Breadth und Scanner noch prominenter machen

4. Danach weitere Detailseiten ausbauen:
   - Risk-On/Off-Verlauf
   - Volatility mit VIX/VIX3M-Kontext
   - Credit/Macro-Fallback sauberer darstellen

## Lokale Befehle

Tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q -p no:cacheprovider
```

Mock-Update:

```powershell
python -m trading_dashboard update --mock --years 2
```

Echte Daten aktualisieren:

```powershell
python -m trading_dashboard update --years 1
```

Nur rendern:

```powershell
python -m trading_dashboard render
```

## Git-Hinweis

Die Baseline ist committed. Nach dieser Handoff-Datei ist der naechste sinnvolle kleine Commit:

```text
Add session handoff status document
```

Vor dem Commit pruefen:

```powershell
git status --short
```
