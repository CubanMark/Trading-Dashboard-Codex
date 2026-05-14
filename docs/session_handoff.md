# Session Handoff - Trading Dashboard

Stand: 2026-05-14
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
# 14 passed
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

- Datenqualitaet ist noch zu grob geprueft. Nach dem frueheren VIX/SPY-Problem muessen Sanity Checks deutlich strenger werden.
- yfinance-Ausfaelle und Teilfehler muessen sichtbarer werden.
- Der aktuelle Run-Status zeigt Quellen, aber noch nicht genug, ob ein Wert echt, Mock, Fallback oder teilweise fehlend ist.
- Universe-Abdeckung sollte explizit geloggt werden: erwartete Symbole, geladene Symbole, fehlende Symbole, valide Historie.

Mittlere Prioritaet:

- Detailseiten sind noch minimal und brauchen echte Historie/Drilldown-Kontext.
- Industry Leadership ist nuetzlich, aber noch keine echte RRG-/Leadership-Analyse.
- Pullback-Regeln sollten fachlich final dokumentiert werden.

## Empfohlene naechste Schritte

1. Datenqualitaetschecks erweitern:
   - fehlende Symbole mit Beispielen loggen
   - stale symbols mit Beispielen loggen
   - extreme Tagesrenditen erkennen
   - unplausible OHLC-Beziehungen erkennen: `high < low`, `close` ausserhalb `low/high`, negative oder Null-Preise
   - Universe Coverage Check: wie viele Equity-Symbole sind aktiv, wie viele haben ausreichende Historie

2. Run-/Source-Status im Dashboard praezisieren:
   - klar anzeigen: `yfinance`, `mock`, `mock-fallback`
   - Warnung bei Mock/Fallback prominenter machen
   - letzter Datenstand je Quelle sichtbar machen

3. Universe-Workflow stabilisieren:
   - `sp1500_universe_filtered.csv` validieren
   - Liquiditaetsfilter dokumentieren
   - Mapping-Luecken fuer Sector/Industry loggen
   - Anzahl verwendeter Werte in Breadth und Scanner transparent anzeigen

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

