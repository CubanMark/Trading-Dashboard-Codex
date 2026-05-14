# Parallel Project Review - Codex vs. Claude

Datum: 2026-05-14
Review-Typ: einmaliger Quarantaene-Vergleich der beiden Parallelprojekte

## Quarantaene-Regeln

- Der Ordner `04_Trading-Dashboard-Claude` wurde fuer diesen Review einmalig gelesen.
- Es wurde kein Code kopiert.
- Es werden keine Imports, keine gemeinsame Library und kein gemeinsamer DB-State eingefuehrt.
- Erkenntnisse duerfen nur als fachliche/architektonische Ideen uebernommen werden.
- Nach diesem Review gilt der Claude-Ordner fuer Codex wieder als tabu, sofern Markus nicht erneut explizit freigibt.

## Review-Ziel

Nicht "wer ist besser", sondern:

- Welche Tradeoffs haben beide Projekte unterschiedlich geloest?
- Welche Unterschiede sind echte Qualitaetsunterschiede?
- Welche Unterschiede sind nur andere Annahmen?
- Welche Ideen sollten bewusst uebernommen oder bewusst nicht uebernommen werden?

## Kurzfazit

Claude ist staerker bei fachlicher Marktbreite und Phase-1-Produktbild: Breadth ist breiter, Sektor-Heatmap nutzt mehrere Zeitraeume, FRED ist vorbereitet, GitHub Actions nutzt DB-Cache und der Build ist klar als Daily-EOD-Job gedacht.

Codex ist staerker bei technischer Robustheit und Betriebstransparenz: installierbares Package mit CLI, deterministischer Mock-Modus, breitere Tests, explizites Data-Quality-Log, Source-/Coverage-Status im Dashboard, klare Quarantaene gegen Schwesterprojekte.

Der wichtigste Unterschied ist kein Gewinner/Verlierer, sondern Annahme: Claude optimiert frueher auf fachlichen Dashboard-Nutzen; Codex optimiert frueher auf verifizierbare Pipeline-Qualitaet.

## Datenmodell / SQLite

### Codex staerker

- Hat eigene Tabellen fuer `dimension_metrics`, `sector_returns`, `industry_returns`, `run_log`, `data_quality_checks`.
- Data-Quality-Ergebnisse sind persistente Daten, nicht nur Log-Ausgaben.
- Scanner-Hits enthalten Varianten, Setup-Label, Trigger-Hinweis, Overlap-Feld und Warning.

### Claude staerker

- Hat ein klareres fachliches Breadth-Modell mit `breadth_daily`: `% > 50DMA`, `% > 200DMA`, New Highs, New Lows, Naehe zum 52W-Hoch.
- Trennt `universe`, `prices`, `corporate_actions`, `macro_series`, `breadth_daily`, `scanner_hits` sehr direkt und lesbar.
- Universe-Schema fuehrt `in_sp500`, `in_sp1500`, `in_watchlist` explizit.

### Warum verschieden

Codex hat die DB frueh als Betriebs- und Quality-System gebaut. Claude hat sie naeher am fachlichen Dashboard-Konzept modelliert.

### Entscheidung

Codex sollte Claudes breitere Breadth-Felder als Idee uebernehmen, aber nicht das Schema kopieren. Naechster sinnvoller Codex-Ausbau: `breadth_daily` oder aequivalente Historisierung fuer `% > 50DMA`, `% > 200DMA`, New Highs/Lows und Naehe zum 52W-Hoch.

## Fetching / yfinance / FRED

### Codex staerker

- Hat Mock-Modus fuer deterministische Offline-Tests.
- Erfasst `mock`, `mock-fallback`, `yfinance` sichtbar in DB und Dashboard.
- Hat EOD-Cutoff nach New-York-Zeit.
- Loggt Missing/Stale/Invalid/Extreme/Coverage als Data-Quality-Zeilen.

### Claude staerker

- Hat Retry-Logik pro Ticker im `yfinance_client`.
- Hat inkrementellen Loader: Bulk fuer neue Ticker, kurzer Re-Fetch fuer stale Ticker.
- Hat FRED-Client fuer HY OAS, 2Y, 10Y, Yield Curve vorbereitet.
- GitHub Actions nutzt DB-Cache, was fuer echte Daily-Pages deutlich praktischer ist.

### Warum verschieden

Codex hat zunaechst auf verifizierbare lokale Runs und Fehlertransparenz gesetzt. Claude hat frueher Richtung automatisierter Daily-Betrieb und externe Datenquellen gebaut.

### Entscheidung

Codex sollte uebernehmen:

- Retry-Logik als fachliche Idee.
- Inkrementelles Update statt Vollersatz als naechster Pipeline-Schritt.
- FRED-Anbindung fuer Credit/Macro, aber optional und ohne erfundene Fallback-Werte.
- GitHub-Actions-DB-Cache-Prinzip pruefen.

Nicht uebernehmen:

- Runtime-Fallback auf Swing-Lab-Artefaktpfade. Codex bleibt entkoppelt.

## Data Quality / Sanity Checks

### Codex staerker

- Persistente Quality-Checks: missing symbols, stale symbols, nonpositive OHLC, invalid OHLC, unexplained extreme returns, corporate-action-related returns, universe coverage, scanner coverage.
- Dashboard zeigt kompakte Betriebszeile mit Quelle, Datenstand, Equity-Coverage, OHLC-Status und Return-Warnungen.
- Unterscheidet ungeklÃ¤rte Extremrenditen von Corporate-Action-Naehe.

### Claude staerker

- Hat einfache Sanity-Warnings direkt am Fetch-Punkt.
- Erkennt grosse Tagesbewegungen als moegliche Splits.
- Loader ist auf Re-Run-Sicherheit per `INSERT OR IGNORE` ausgelegt.

### Warum verschieden

Codex behandelt Datenqualitaet als eigenes Produktfeature. Claude behandelt Datenqualitaet eher als Pipeline-Warnung.

### Entscheidung

Codex sollte Data-Quality-Ansatz behalten. Von Claude sinnvoll: Re-Run-Sicherheit und inkrementelle Updates staerker machen.

## Universe / Mapping / Liquiditaet

### Codex staerker

- Nutzt eine gefilterte Universe-CSV ohne Runtime-Zugriff auf Swing Lab.
- Hat manuelle Overrides fuer PINS/ULS und prueft Mapping-Coverage.
- Dashboard macht Equity-Coverage sichtbar.

### Claude staerker

- Unterscheidet `in_sp500`, `in_sp1500`, Watchlist.
- Kann S&P 400/600 von Wikipedia nachseeded.
- Dokumentiert Liquiditaetsparameter aus Swing Lab klarer: Preis, Median Dollar Volume, Mindesthistorie.

### Warum verschieden

Codex hat bewusst statischen, entkoppelten Input gewaehlt. Claude wollte das S&P-1500-Zielbild schneller auffuellen und operationalisieren.

### Entscheidung

Codex sollte Liquiditaetsfilter und Universe-Herkunft besser dokumentieren. Wikipedia-Nachseeding ist Phase-1-nah, aber nur uebernehmen, wenn es nicht neue Instabilitaet in den Daily-Build bringt.

## Scanner

### Codex staerker

- Scanner zeigt mehrere Research-Varianten: `3D Pullback`, `Pullback MA10`, `Pullback MA20`.
- UI zeigt Trigger-Hinweis, Overlaps, gekoppelte Filter, Sortierung und explizite Research-Warnung.
- Scanner-Coverage wird geloggt.

### Claude staerker

- Pullback-Regel ist fachlich klarer und konservativer: MA20, +/-3%, Close > SMA50 > SMA200, Mindestpreis, Mindestvolumen.
- Scanner ist enger an Swing-Lab-Review und PROJECT_BRIEF-Entscheidung gekoppelt.

### Warum verschieden

Codex behandelt Pullback als Research-Familie und Transparenz-/Explorationsausgabe. Claude behandelt Pullback frueher als konkrete, aus Swing Lab abgeleitete Phase-1-Regel.

### Entscheidung

Codex sollte Claudes explizite Volumen-/Preisfilter als Idee pruefen. Gleichzeitig sollte Codex die Research-Transparenz behalten. Kein Wechsel zu einem "handelbaren Signal".

## Rendering / UI

### Codex staerker

- Homepage ist funktionsreicher bei Scanner-Tabelle, Filtern, Sortierung und Statuskommunikation.
- Zeigt positive/negative Sektoren, Industry Leadership Top/Bottom, Data Quality Log und Run Status.
- Hat Detailseiten als Platzhalter-Struktur.

### Claude staerker

- Visuell kompakter und dashboard-artiger.
- Nutzt Plotly-Sparklines und eine echte Sektor-Heatmap mit 1W/1M/3M/6M.
- Breadth-Kachel ist fachlich reichhaltiger mit Sparkline, 200DMA, New Highs/Lows.

### Warum verschieden

Codex ist operativer/diagnostischer. Claude ist visueller/produktnaeher am Mockup.

### Entscheidung

Codex sollte aus Claude uebernehmen:

- Breadth-Kachel mit mehr echter Historie.
- Sektor-Heatmap mit mehreren Zeitraeumen, aber Zeitraum-Toggle bleibt als bewusste Phase-1/2-Entscheidung zu pruefen.

Codex sollte behalten:

- Statuszeile, Quality Log, Scanner-Filter und Research-Warnungen.

## Tests / Verifikation

### Codex staerker

- Breitere Testabdeckung: Storage, Universe, Fetch-Replacement, Data Quality, Pullback, Mock-Integration.
- Deterministischer Mock-Update-Lauf testet die komplette CLI-Pipeline.
- Installierbares Package macht Imports stabiler.

### Claude staerker

- Viele Smoke-Tests decken Schema, Universe-Seeding, Indikatoren, Loader, Sektor- und Industry-Rendering ab.
- Tests sind nah an der flachen Projektstruktur und leicht lesbar.

### Warum verschieden

Codex hat staerker auf automatisierbare Software-Qualitaet gesetzt. Claude hat schneller End-to-End-Produktteile mit Smoke-Tests abgesichert.

### Entscheidung

Codex sollte Rendering-Tests fuer Breadth/Sector/Industry ausbauen, wenn diese Komponenten fachlich erweitert werden.

## Actions / Deployment

### Codex staerker

- Package-/CLI-Struktur ist fuer lokale und CI-Kommandos sauber.

### Claude staerker

- GitHub Action ist produktnaeher: Tests, DB-Cache, Build, Upload Pages, Deploy Pages.
- Cron-Zeit ist explizit nach US-Marktschluss gewaehlt.

### Warum verschieden

Claude hat Deployment frueher ernst genommen. Codex hat zuerst lokale Reproduzierbarkeit und Data-Quality-Sichtbarkeit gehaertet.

### Entscheidung

Codex sollte Claudes DB-Cache- und Pages-Deploy-Struktur als Idee pruefen.

## Dokumentation / Handoff

### Codex staerker

- Handoff ist laufend aktualisiert und beschreibt aktuellen Datenstand, offene Risiken und konkrete Befehle.
- Entscheidungen zu Mock/Fallback/Quality sind gut nachvollziehbar.

### Claude staerker

- Swing-Lab-Reuse-Entscheidungen sind detaillierter und konkreter nach Fundstuecken dokumentiert.
- PROJECT_BRIEF wurde bei offenen Entscheidungen bereits teilweise aktualisiert.

### Warum verschieden

Codex dokumentiert Session- und Betriebsstand. Claude dokumentiert Wiederverwendungsentscheidungen und fachliche Quellen staerker.

### Entscheidung

Codex sollte Pullback-Regeln und Swing-Lab-Bezug fachlich finaler dokumentieren, sobald die Scanner-Regeln konsolidiert werden.

## Bewusst uebernehmen

1. Breadth erweitern: `% > 200DMA`, New Highs/Lows, Naehe zu 52W-Hoch, Historie/Sparkline.
2. Inkrementelles Update und Retry-Logik fuer yfinance.
3. FRED-Client fuer Credit/Macro, optional und transparent.
4. GitHub-Actions-DB-Cache und klarer EOD-Cron.
5. Liquiditaetsfilter dokumentieren und ggf. scannerseitig nutzen.
6. Sektor-Heatmap mit mehreren Zeitraeumen pruefen.

## Bewusst nicht uebernehmen

1. Runtime-Zugriff auf Swing-Lab-Artefakte.
2. Flache Projektstruktur ohne installierbares Package.
3. Nur Log-Warnings statt persistenter Data-Quality-Tabelle.
4. Einen einzelnen Pullback-Scanner als scheinbar akzeptiertes Signal darstellen.
5. FRED- oder Wikipedia-Abhaengigkeiten als harte Build-Voraussetzung.

## Unterschiedlicher Tradeoff, kein klarer Gewinner

- Codex `replace_prices` pro Lauf vs. Claude `INSERT OR IGNORE` inkrementell:
  - Codex ist einfacher und vermeidet gemischte Quellen pro Symbol.
  - Claude ist effizienter und besser fuer Daily-Betrieb.
  - Zielbild: Codex sollte inkrementell werden, aber mit expliziter Source-/Quality-Transparenz.

- Codex Research-Scanner-Familie vs. Claude enger MA20-Scanner:
  - Codex ist explorativer.
  - Claude ist fachlich fokussierter.
  - Zielbild: Research-Familie behalten, aber Regeln/Filter fachlich schaerfen.

- Codex Diagnose-UI vs. Claude visuelles Dashboard:
  - Codex macht Vertrauen und Ursachen sichtbar.
  - Claude liest sich eher wie ein Markt-Dashboard.
  - Zielbild: Codex sollte Diagnostik behalten und visuelle Markt-Kacheln verbessern.

## Muss getrennt bleiben

- Keine gemeinsame Library.
- Keine Imports zwischen Projekten.
- Keine gemeinsame SQLite-DB.
- Keine automatische Synchronisierung von Universe/Scanner-Code.
- Vergleichsdokument ist erlaubt; Implementierung bleibt eigenstaendig.

## Offene Entscheidungen fuer Markus

1. Soll Codex als naechstes Breadth-Historie und Breadth-Detailseite ausbauen?
2. Soll Codex den yfinance-Loader inkrementell umbauen oder erst Extreme-Returns/ANF/BAC klaeren?
3. Soll der Pullback-Scanner auf eine engere MA20-Regel mit Preis-/Volumenfilter reduziert werden, oder bleiben mehrere Research-Varianten sichtbar?
4. Soll FRED/HY-OAS jetzt in Phase 1 aktiviert werden, wenn API-Key vorhanden ist?
5. Soll GitHub Pages Deployment mit DB-Cache jetzt priorisiert werden?

## Empfohlene naechste 3 Codex-Schritte

1. Extreme Returns und yfinance-Teilfehler klaeren (`ANF`, `BAC`, `AAP`, `APLS`, `ASGN`, `CORT`, `HTZ`, ...).
2. Breadth ausbauen: Historie plus `% > 200DMA`, New Highs/Lows, 52W-Naehe.
3. yfinance-Update inkrementell und retry-faehig machen, mit bestehendem Data-Quality-Logging.
