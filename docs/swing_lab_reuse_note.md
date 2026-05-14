# Swing-Lab Reuse Note

Datum: 2026-05-14

## Gezielte Sichtung

Gesichtet wurde `G:/Meine Ablage/05_Projekte/Trading/02_Swing-Lab`.
Der Ordner `04_Trading-Dashboard-Claude` wurde nicht gelesen.

## Fundstuecke

- `requirements.txt`: pandas, numpy, yfinance, matplotlib/seaborn, scipy, Jupyter-Tooling.
- `data_policy.md`: yfinance fuer Daily OHLCV und Adjusted Close; bekannte Schwaechen bei Survivorship, Index-Mitgliedschaft und Earnings.
- `artifacts/*phase1_universe*.csv`: vorhandene Universums-Snapshots und Qualitaetsreports.
- `artifacts/2026-05-06_sp1500_universe_filtered.csv`: gefiltertes S&P-1500-Naeherungsuniversum mit 1244 liquiden Symbolen.
- `setup_log.md`: dokumentierte Pullback-v1/v2a-Regeln und Diagnose.
- `reviews/2026-05-01_pullback_uptrend_v2a_tradability_filter_review.md`: v2a verbessert v1, bleibt aber kein akzeptierter handelbarer Edge.
- `reviews/2026-05-01_pullback_family_pause.md`: Pullback-Familie pausiert; keine v3 ohne Begruendungsupgrade.

## Entscheidungen

- Keine Imports und keine gemeinsame Library in Phase 1.
- yfinance-Idee und Datenqualitaetsdisziplin werden lokal neu implementiert.
- Pullback-v2a wird nur als Research-/Watchlist-Scanner uebernommen.
- Scanner-Ausgaben muessen sichtbar machen, dass dies kein Handelssignal ist.
- Sektor-/Industry-Mapping wird vorbereitet, aber bei fehlenden Daten nicht erzwungen.
- Das gefilterte S&P-1500-Universum wurde als statischer Input nach `inputs/universe/sp1500_universe_filtered.csv` kopiert. Es bleibt damit entkoppelt und wird nicht aus Swing-Lab importiert.
