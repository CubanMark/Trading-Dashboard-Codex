# Swing Lab Handoff: Breadth Composite Research

Stand: 2026-05-15

Ziel dieser Notiz ist eine saubere Uebergabe vom Dashboard-Projekt an `Trading/02_Swing-Lab`. Das Dashboard bleibt Anzeige- und Entscheidungswerkzeug. Swing Lab soll die Research-Frage ueber einen laengeren Zeitraum backtesten und belastbarer beantworten.

## Warum das nach Swing Lab gehoert

Die bisherige Dashboard-Historie deckt nur 2021-02-24 bis 2026-05-14 ab. Das enthaelt den 2022er Drawdown, aber keinen vollstaendigen klassischen Baerenmarkt wie 2000-2002, 2007-2009 oder 2020. Die aktuelle Beobachtung, dass `Damaged` hohe 20-Tage-Forward-Returns zeigt, kann deshalb stark von Mean-Reversion in einem resilienten Marktregime gepraegt sein.

Swing Lab ist der richtige Ort, weil dort:

- laengere historische Daten aufgebaut oder importiert werden koennen,
- Varianten der Composite-Definition getestet werden koennen,
- Forward Returns, Drawdowns, Hit Rates und Regime-Splits reproduzierbar ausgewertet werden koennen,
- Research-Ergebnisse spaeter als klare Regeldefinition zurueck ins Dashboard fliessen koennen.

## Aktueller Dashboard-Stand

Relevante Datei:

- `Trading/05_Trading-Dashboard-Codex/src/trading_dashboard/render/html.py`

Relevante Funktionen:

- `breadth_composite_score(row)`
- `heat_status_from_value(...)`
- `momentum_pair_status(...)`
- `speculative_status(...)`
- `moving_average(values, window)`
- `negative_composite_clusters(rows, min_days=3)`
- `render_breadth_composite_chart(rows)`

Aktuelle Datenquelle im Dashboard:

- SQLite: `Trading/05_Trading-Dashboard-Codex/db/trading_dashboard.sqlite3`
- Tabelle `breadth_daily`
- SPY-Daten aus Tabelle `prices`, Symbol `SPY`

Aktueller Zeitraum:

- 2021-02-24 bis 2026-05-14
- 1312 Handelstage

## Composite-Definition im Dashboard

Der Breadth Composite summiert neun Heatmap-Zustaende:

1. `% > SMA50`
2. `% > SMA200`
3. `52W Highs / 52W Lows`
4. `% within 5% of 52W high`
5. `4% Up / Down daily`
6. `5D 4% Ratio`
7. `10D 4% Ratio`
8. `25% Up / Down 3M`
9. `50% Up / Down 1M`, contrarian bewertet

Scoring:

- strong red: `-2`
- light red: `-1`
- neutral: `0`
- light green: `+1`
- strong green: `+2`

Range:

- Minimum: `-18`
- Maximum: `+18`

Wichtige Besonderheit:

- `50% Up / Down 1M` ist contrarian: viele `+50%`-Werte gelten als Ueberhitzung/bearish, viele `-50%`-Werte als kapitulationsartig/bullish.

## Aktuelle Chart-Logik im Dashboard

Auf `/breadth.html` gibt es den Abschnitt `SPY vs Breadth Composite`.

Darstellung:

- SPY pro ausgewaehltem Zeitraum auf `100` indexiert.
- Composite als 5-Tage-Durchschnitt.
- rote Hintergrundbaender nur, wenn Tages-Composite mindestens 3 Handelstage in Folge unter `0` liegt.
- Zeitraeume: `YTD`, `1Y`, `3Y`, `5Y`.

Diese Logik ist bewusst deskriptiv und nicht als validierte Handelsregel zu verstehen.

## Vorlaeufige Regime-Definition fuer Research

Die folgende Definition wurde fuer eine erste lokale Auswertung verwendet:

- `Damaged`: 5D Composite < 0 oder Tages-Composite mindestens 3 Tage in Folge < 0
- `Healing`: 1 bis 10 Tage nach `Damaged`, wenn 5D Composite wieder > 0
- `Weakening`: 5D Composite > 0, aber ueber 5 Tage um mindestens 4 Punkte gefallen
- `Positive`: 5D Composite > 3
- `Other/Neutral`: Rest

Diese Schwellen sind Arbeitshypothesen, keine validierten Parameter.

## Erste Dashboard-Auswertung

Zeitraum: 2021-02-24 bis 2026-05-14

Forward Returns wurden ab Tagesschluss des Regime-Tages gemessen.

| Regime | Tage | Avg 5D Composite | SPY +1T | SPY +5T | SPY +10T | SPY +20T |
|---|---:|---:|---:|---:|---:|---:|
| Positive | 438 | +9.05 | +0.02% | +0.11% | +0.19% | +0.43% |
| Weakening | 104 | +4.53 | +0.10% | +0.23% | +0.61% | +0.66% |
| Damaged | 432 | -5.85 | +0.08% | +0.40% | +0.72% | +1.75% |
| Healing | 288 | +5.03 | +0.08% | +0.31% | +0.75% | +1.08% |
| Other/Neutral | 50 | +1.32 | -0.05% | +0.49% | +0.88% | +1.10% |

Vorlaeufige Interpretation:

- `Damaged` ist waehrend der Phase selbst kein gutes Long-Umfeld.
- Die positiven Forward Returns nach `Damaged` koennen Mean-Reversion nach Stress abbilden.
- Ohne echte Baerenmarktphasen ist diese Aussage wahrscheinlich zu optimistisch.
- `Healing` ist fachlich interessanter als `Damaged` selbst, weil es eine beginnende Reparatur der Marktbreite beschreibt.

## Forschungsfragen fuer Swing Lab

1. Haelt die `Damaged -> positive forward returns`-Beobachtung auch in echten Baerenmaerkten?

Zu pruefen ueber lange Historie inklusive:

- 2000-2002
- 2007-2009
- 2011
- 2015/2016
- 2018
- 2020
- 2022

2. Wirkt der Composite anders je nach SPY-Trendregime?

Mindest-Splits:

- SPY ueber SMA200
- SPY unter SMA200
- SMA200 steigend
- SMA200 fallend
- SPY Drawdown vom 52W-Hoch, z. B. `0 bis -5%`, `-5 bis -10%`, `-10 bis -20%`, `< -20%`

3. Ist `Healing` ein besseres Signal als `Damaged`?

Zu testen:

- erster Tag 5D Composite wieder > 0 nach `Damaged`
- erster Tag Tages-Composite wieder > 0 nach 3+ negativen Tagen
- 3 Tage nach Ende eines negativen Clusters
- 5D Composite kreuzt von unten nach oben ueber `0`

4. Welche Parameter sind robust?

Varianten:

- Composite-Glattung: 3D, 5D, 10D
- negative Cluster-Mindestdauer: 2, 3, 5 Handelstage
- Damaged-Schwelle: `< 0`, `<= -3`, `<= -5`, `<= -8`
- Positive-Schwelle: `> 3`, `> 5`, `> 8`
- Healing-Fenster: 5, 10, 15, 20 Handelstage

5. Gibt es Divergenzen mit Vorlauf?

Beispiele:

- SPY macht 20D/50D Hoch, Composite macht kein neues Hoch.
- SPY nahe 52W-Hoch, Composite faellt unter 0.
- Composite macht hoeheres Tief, SPY macht tieferes Tief.
- Composite dreht vor SPY nach oben.

6. Welche Komponente erklaert das Signal?

Komponenten getrennt testen:

- Trend Participation: SMA50/SMA200
- Leadership: 52W High/Low und Near High
- Momentum Thrust: 4%-Werte und 25% 3M
- Speculative Heat/Kapitulation: 50% 1M contrarian

## Gewuenschte Swing-Lab-Outputs

Minimaler Research-Output:

- Notebook oder Skript mit reproduzierbarer Datenerstellung.
- CSV/Parquet mit taeglichem Composite, Regime, SPY Close und Forward Returns.
- Tabellen fuer 1D, 5D, 10D, 20D, 40D und 60D Forward Returns.
- Splits nach SPY-Trendregime.
- Cluster-Auswertung fuer negative Composite-Phasen.
- Kurze Ergebnisnotiz: Was soll ins Dashboard zurueck?

Nuetzliche Kennzahlen:

- Durchschnitt und Median Forward Return
- Win Rate
- Best/Worst Forward Return
- Max adverse excursion nach Signal
- Max favorable excursion nach Signal
- Anzahl Signale/Tage
- Anteil ueberlappender Signale
- Ergebnisse getrennt nach Bullenmarkt/Baerenmarkt

## Datenanforderung

Ideal waere ein historisches Aktienuniversum. Falls das nicht verfuegbar ist, sind zwei Stufen sinnvoll:

1. pragmatischer Start mit aktuellem Universum und yfinance-Historie, Survivorship Bias klar markieren,
2. spaeter besseres historisches Universum oder externe Breadth-Datenquelle pruefen.

Fuer SPY reichen EOD-Daten mit Adjusted Close oder konsistentem Close. Fuer Breadth muss die Adjustierung konsistent sein, weil SMA-/52W-Signale sonst verzerrt werden koennen.

## Rueckfluss ins Dashboard

Nur validierte und einfache Erkenntnisse sollten zurueck ins Dashboard.

Moegliche Rueckgaben:

- finale Regime-Definition fuer `Positive`, `Weakening`, `Damaged`, `Healing`
- robuste Schwellenwerte
- kurzer Regime-Text auf `/breadth.html`
- optionale Tabelle mit historischer Erwartung pro Regime
- keine komplexe Strategie-Engine im Dashboard

## Offene Entscheidung

Soll Swing Lab den Dashboard-Composite exakt replizieren oder eine Research-Version bauen?

Empfehlung:

Zuerst exakt replizieren, um die heutige Dashboard-Beobachtung zu validieren. Danach Varianten testen. Sonst ist unklar, ob bessere Ergebnisse vom Signal oder nur von veraenderter Definition kommen.
