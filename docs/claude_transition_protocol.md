# Claude Transition Protocol

Stand: 2026-05-16
Adressat: Claude im Projekt `Trading/05_Trading-Dashboard-Codex`

## Kontext

Markus uebergibt die Weiterentwicklung voruebergehend an Claude, weil das Codex-Tokenbudget fuer die naechsten Tage knapp ist. Dieses Projekt ist jetzt der fuehrende Dashboard-Strang. Das alte Parallelprojekt `Trading/04_Trading-Dashboard-Claude` soll nicht weiter als eigenstaendige Codebasis fortgefuehrt werden.

Wichtig: Vor jeder Aufgabe `PROJECT_BRIEF.md` lesen. Phase bleibt **1 MVP**. Phase-2/3-Features nur bauen, wenn Markus sie explizit priorisiert.

## Was nicht verloren gehen darf

1. **Schichtentrennung**
   - Datenholen: `src/trading_dashboard/data/`
   - Berechnen: `src/trading_dashboard/compute/`
   - Rendern: `src/trading_dashboard/render/`
   - Scanner: `src/trading_dashboard/scanners/`

2. **Keine Cross-Projekt-Kopplung**
   - keine Imports aus Swing Lab
   - keine gemeinsame SQLite-DB
   - keine shared Library in Phase 1
   - Research-Ergebnisse duerfen als dokumentierte Regeln uebernommen werden, aber nicht als Laufzeitabhaengigkeit

3. **Datenqualitaet ist Produktbestandteil**
   - `data_quality_checks` nicht als Nebensache behandeln
   - Source-/Coverage-/OHLC-/Extreme-Return-Status bewusst sichtbar halten
   - Scanner darf fragwuerdige Daten nicht stillschweigend nutzen

4. **Scanner bleibt Research**
   - Pullback-Scanner ist Watchlist/Research, kein akzeptierter Trading Edge
   - keine Entry-/Stop-/Positionsgroessenlogik in Phase 1
   - Research-Warnung im UI behalten

5. **Breadth Composite ist Kontext, keine Auto-Ampel**
   - Composite ist nur Breadth-intern
   - kein globales "Market is green/red" daraus bauen
   - Regime-Texte sind Entscheidungskontext, keine Trading-Signale

## Aktueller technischer Stand

Tests zuletzt gruen:

```powershell
python -m pytest -q -p no:cacheprovider
# 34 passed
```

Lokale Pipeline zuletzt erfolgreich:

```powershell
python -m trading_dashboard compute
python -m trading_dashboard render
```

Noch nicht nach der letzten Aenderung live ausgefuehrt:

```powershell
python -m trading_dashboard update --years 5
```

Grund: Der Fetch wurde gerade auf inkrementelles Laden umgebaut; ein echter yfinance-Lauf sollte kontrolliert erfolgen und danach im Data-Quality-Log geprueft werden.

## Wichtigste aktuelle Aenderung: Inkrementeller Fetch

Dateien:

- `src/trading_dashboard/data/fetch.py`
- `src/trading_dashboard/data/storage.py`
- `tests/test_fetch_replaces_sources.py`

Verhalten:

- vorhandene `yfinance`-Historie pro Symbol wird erkannt
- bestehende Symbole laden nur ab `letztes yfinance-Datum - 10 Tage`
- neue Symbole oder Symbole mit bisher nur Mock-Daten bekommen Full-Fetch ueber `--years`
- yfinance-Daten werden per Upsert gespeichert
- alte Mock-Historie wird beim ersten echten yfinance-Fetch symbolweise ersetzt
- bei yfinance-Ausfall und vorhandener DB-Historie bleibt die Historie erhalten; kein automatisches Mock-Overwrite
- Data-Quality-Pruefung laeuft nach Upsert gegen die gesamte gespeicherte Historie

Bitte beim naechsten echten Run besonders pruefen:

- `incremental_fetch` im Data-Quality-Log
- Anzahl neuer Preiszeilen
- `missing_symbols`
- `stale_symbols`
- `universe_coverage`
- ob keine Mock-Quellen in produktiver yfinance-Historie uebrig bleiben

## Aktueller Breadth-Stand

Dateien:

- `src/trading_dashboard/render/html.py`
- `docs/breadth_composite_research.md`
- `docs/swing_lab_breadth_composite_handoff.md`

Umgesetzt:

- Participation Breadth KPIs
- Momentum Breadth KPIs
- Breadth-History-Heatmap mit Year-Selector
- Composite-Spalte pro Tag
- Composite-Gauge
- `SPY vs Breadth Composite` Chart
- Regime-Label in der Composite-Box

Regime:

- `Damaged`: 5D-Composite < 0 oder mindestens 3 Tages-Composite-Werte in Folge < 0
- `Healing`: 1 bis 10 Handelstage nach Ende von Damaged, wenn 5D-Composite > 0
- `Weakening`: 5D-Composite > 0, aber ueber 5 Handelstage mindestens 4 Punkte gefallen
- `Positive`: 5D-Composite > 3
- `Other`: Rest

Wichtigste Research-Erkenntnis:

- `Healing` ist der robusteste positive Kontext fuer Pullback-Setups.
- `Weakening` ist Vorsicht, nicht Verkauf.
- `Damaged` ist kein blindes Buy-the-Dip-Signal.
- SPY-Trendkontext ist entscheidend.

Naechster sinnvoller Breadth-Schritt:

- SPY-Kontext in die Regime-Anzeige integrieren:
  - SPY ueber/unter SMA200
  - SPY Drawdown vom 52W-Hoch
  - besonders: SPY unter SMA200 und Drawdown >= 20% als "keine neuen Longs"-Kontext

## Aktueller Scanner-Stand

Dateien:

- `src/trading_dashboard/scanners/pullback.py`
- `src/trading_dashboard/compute/metrics.py`
- `docs/pullback_scanner_rules.md`

Regeln:

- SPY ueber SMA200
- Aktie ueber SMA50, SMA50 ueber SMA200
- Close mindestens 10 USD
- Avg Volume 50D mindestens 750.000 Aktien
- RS-Rang mindestens 70
- Close maximal 30% unter 52W-Hoch
- MA10/MA20-Pullback: maximal `0.75 * ATR14` vom SMA entfernt
- Symbole mit `missing_corporate_action` oder `possible_data_error` werden ausgeschlossen

UI:

- Spalte `MA ATR`, nicht mehr prozentuale MA-Distanz
- Setup-/Sector-/Industry-Filter
- Overlap-Chips
- Research-Warnung

Bitte nicht:

- Scanner in ein Handelssignal umbenennen
- VCP/Breakout jetzt nebenbei bauen
- Position Sizing oder Entry/Stop in Phase 1 einbauen

## Neue Detailseiten

Claude hatte bereits sinnvolle Detailseiten ergaenzt:

- `sentiment.html`: CNN Fear & Greed
- `risk.html`: XLY/XLP
- `volatility.html`: VIX und VIX/VIX3M
- `credit-macro.html`: TLT/HYG/LQD als Proxy, HY OAS noch offen

Wichtig:

- HY OAS ist noch nicht angebunden.
- Credit-Seite darf nicht so wirken, als sei echter FRED HY OAS bereits vorhanden.

## Git-/Dateistatus

Bekannte lokale Aenderungen beim Schreiben dieses Protokolls:

- `README.md`
- `docs/breadth_composite_research.md`
- `docs/pullback_scanner_rules.md`
- `docs/session_handoff.md`
- `docs/claude_transition_protocol.md`
- `src/trading_dashboard/data/fetch.py`
- `src/trading_dashboard/data/storage.py`
- `tests/test_fetch_replaces_sources.py`
- `tests/test_integration_mock_update.py`

Untracked:

- `.claude/settings.local.json`

Empfehlung:

- `.claude/` nicht committen.
- Entweder ignorieren oder explizit aus Staging heraushalten.

## Priorisierte naechste Schritte

1. **GitHub Actions / Pages verifizieren**
   - letzten Workflow-Lauf ansehen
   - Pages-URL oeffnen
   - DB-Cache im Folge-Run pruefen

2. **Echten inkrementellen Update-Lauf kontrolliert ausfuehren**
   ```powershell
   python -m trading_dashboard update --years 5
   ```
   Danach Data-Quality-Log und gerenderte Seiten pruefen.

3. **Falls stabil: Commit vorbereiten**
   - `.claude/` nicht stagen
   - Tests laufen lassen
   - Commit inhaltlich etwa: `Add incremental fetch and breadth regime context`

4. **Danach fachlich weiter**
   - SPY-Trendkontext in Breadth-Regime
   - HY OAS/FRED optional anbinden
   - Sektor-Heatmap-Zeitraeume pruefen

## Technische Pruefbefehle

```powershell
git status --short
python -m pytest -q -p no:cacheprovider
python -m trading_dashboard compute
python -m trading_dashboard render
```

Bei echtem Datenlauf:

```powershell
python -m trading_dashboard update --years 5
```

Danach insbesondere `data_quality_checks` im Dashboard und in SQLite pruefen.

## Was ich Claude ausdruecklich mitgeben wuerde

Das Projekt ist jetzt nicht mehr in der "erstmal irgendwas bauen"-Phase. Es hat eine klare Richtung:

- robuste EOD-Datenpipeline,
- eigene Historie,
- sichtbare Datenqualitaet,
- Breadth als zentrale Marktbreiten-Dimension,
- Pullback-Scanner als Research-Watchlist.

Bitte eher kleine, verifizierbare Schritte machen als grosse Feature-Spruenge. Der naechste echte Engpass ist nicht ein weiteres UI-Element, sondern operativer Betrieb: Daily Update, Cache, Pages, Data Quality.
