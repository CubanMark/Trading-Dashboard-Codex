# Pullback Scanner Rules

Stand: 2026-05-16
Phase: 1 MVP

## Ziel

Der Pullback-Scanner ist eine Research-/Watchlist-Ausgabe. Er ist kein akzeptiertes handelbares Signal und erzeugt keine Entry-Empfehlung. Zweck ist, morgens schnell liquide, relativ starke Aktien zu finden, die in einem intakten Aufwaertstrend zurueck an einen kurzfristigen gleitenden Durchschnitt laufen.

## Universum

Ausgangspunkt ist das aktive Equity-Universum aus `inputs/universe/sp1500_universe_filtered.csv`. Sector und Industry kommen aus dieser Datei und werden beim Fetch in `symbols` persistiert.

Ausgeschlossen bleiben Sub-Industries, die fuer diesen Research-Scanner aktuell zu schwer interpretierbar oder fachlich nicht gewuenscht sind:

- Biotechnology
- Pharmaceuticals
- Health Care Services
- Consumer Staples Merchandise Retail
- Diversified Banks
- Property & Casualty Insurance

## Marktfilter

Der Scanner laeuft nur, wenn SPY oberhalb seiner SMA200 liegt. Das ist ein einfacher Phase-1-Regimefilter und verhindert, dass Pullbacks in einem breiten Baerenmarkt als normale Trendfortsetzung gelesen werden.

## Basisfilter pro Aktie

Eine Aktie muss alle Basisfilter erfuellen:

- mindestens 252 Handelstage Kursgeschichte
- letzter Schlusskurs mindestens 10 USD
- durchschnittliches 50-Tage-Volumen mindestens 750.000 Aktien
- Relative-Strength-Rang mindestens 70, berechnet aus 1M-Performance innerhalb des aktiven Equity-Universums
- Schlusskurs oberhalb SMA50, SMA50 oberhalb SMA200
- Schlusskurs nicht mehr als 30% unter dem 52W-Hoch
- keine offene Data-Quality-Flagge `missing_corporate_action` oder `possible_data_error`

Diese Filter sind bewusst konservativ, aber noch nicht als finaler Edge-Filter zu verstehen.

## Varianten

Die Varianten bleiben sichtbar, weil Ueberschneidungen nuetzlich sind:

- `3D Pullback`: drei tiefere Schlusskurse in Folge innerhalb des Basisfilters
- `Pullback MA10`: Schlusskurs maximal 0.75 ATR14 von SMA10 entfernt und in den letzten 10 Tagen unter dem lokalen Hoch
- `Pullback MA20`: Schlusskurs maximal 0.75 ATR14 von SMA20 entfernt und in den letzten 10 Tagen unter dem lokalen Hoch

`Pullback MA20` ist die fachlich konservativste Variante. `MA10` und `3D Pullback` bleiben Research-Kontext, nicht separate Handelsfreigaben.

## Anzeige

Die Scanner-Tabelle zeigt:

- Setup, Ticker, Sector, Industry
- RS-Rang
- 1W- und 1M-Performance
- MA-Distanz in ATR-Einheiten (`MA ATR`)
- ATR%
- durchschnittliches 50-Tage-Volumen
- Distanz zum 52W-Hoch
- Ueberschneidungen mit anderen Varianten

Filter, Sortierung, Overlap-Chips und Research-Warnung bleiben Teil der Ausgabe.

## Bewusst offen

- Kein Volumenanstieg am Pullback-Tag.
- Kein Earnings-Filter.
- Kein Entry-, Stop- oder Positionsgroessenmodell.
- Keine VCP-/Breakout-Regeln in Phase 1.
- Keine Umstellung auf ein "tradable edge" Label ohne Auswertung in Swing Lab.
