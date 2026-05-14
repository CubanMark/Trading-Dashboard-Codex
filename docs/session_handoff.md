# Session Handoff - Trading Dashboard

Stand: 2026-05-14, Update nach Data-Quality-Haertung
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

Letzte bekannte Verifikation:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q -p no:cacheprovider
# 19 passed
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

- Index-Strip fuer SPY, QQQ, IWM, VIX/TLT-Kontext
- Market-State-Pills fuer sechs Dimensionen
- Sektor-Performance getrennt in `Positive 1W` und `Negative 1W`
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
- Scanner-Coverage wird geloggt: letzter echter Lauf 1150 Symbole gescannt, 93 per Industry ausgeschlossen, 75 Research Hits.

## Scanner-Status

Der Pullback-Research-Scanner ist als Watchlist-/Research-Ausgabe umgesetzt, nicht als akzeptierter handelbarer Edge.

Aktuelle Varianten:

- `3D Pullback`
- `Pullback MA10`
- `Pullback MA20`

Scanner-Tabelle:

- sortierbar nach Setup, Ticker, Sector, Industry, Relative Strength, 1W, 1M, MA Distance, ATR, 52W Distance und Also In
- Setup wird als farbiger Chip angezeigt
- Trigger-Hinweis erscheint im Hover-Tooltip des Setup-Chips
- `Also In` zeigt Ueberschneidungen als farbige Chips
- Filter fuer Setup, Sector und Industry sind gekoppelt: die Dropdown-Optionen reagieren auf die jeweils aktiven anderen Filter

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

- yfinance-Teilfehler treten tatsaechlich auf: letzter Lauf meldete `ANF` und `BAC` fehlend; Coverage zeigt deshalb 1242/1244.
- Extreme Tagesrenditen bleiben fachlich zu klaeren. Letzter yfinance-Lauf: 13 unexplained, 0 corporate-action-related (`AAP`, `APLS`, `ASGN`, `CORT`, `HTZ`, ...).

Mittlere Prioritaet:

- Detailseiten sind noch minimal und brauchen echte Historie/Drilldown-Kontext.
- Industry Leadership ist nuetzlich, aber noch keine echte RRG-/Leadership-Analyse.
- Pullback-Regeln sollten fachlich final dokumentiert werden.

## Empfohlene naechste Schritte

1. Extreme Tagesrenditen einordnen:
   - Beispiele aus `extreme_daily_returns` gegen Corporate Actions/Splits pruefen
   - pruefen, ob yfinance Corporate Actions fuer diese Faelle fehlen oder ob die Rohdaten selbst fehlerhaft sind
   - keine Adjusted-Werte heimlich einmischen; Phase-1-Entscheidung bleibt unadjusted + Corporate Actions separat

2. yfinance-Fehlermeldungen behandeln:
   - `ANF` und `BAC` gegen erneuten Lauf/Einzelticker-Fetch pruefen
   - entscheiden, ob fehlende Symbole retrybar, temporär oder aus dem Universum zu entfernen sind

3. Universe-Workflow stabilisieren:
   - Liquiditaetsfilter dokumentieren
   - Anzahl verwendeter Werte in Breadth und Scanner noch prominenter machen

4. Danach erst Detailseiten ausbauen:
   - Breadth-Historie
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
