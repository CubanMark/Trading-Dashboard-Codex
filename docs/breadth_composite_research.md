# Breadth Composite Research Note

Stand: 2026-05-16

Diese Notiz haelt die erste fachliche Interpretation des internen Breadth Composite fest. Wichtig: Das ist kein globaler Dashboard-Composite und keine automatische Marktampel. Der Wert aggregiert nur die neun Breadth-History-Farbzustaende auf der Breadth-Detailseite.

## Datenbasis

- Dashboard-Historie: eigenes Dashboard-Universum aus der lokalen SQLite-Datenbank, nicht Stockbee direkt.
- Swing-Lab-Research: 2005-01-07 bis 2026-05-05, 5364 Handelstage, ca. 1244 aktuelle S&P-1500-Titel.
- Warmup-Caveat: Die ersten ca. 200 Handelstage sind fuer SMA200/52W-Logik weniger belastbar.
- Universums-Caveat: Die Historie ist nur so gut wie das aktuelle Aktienuniversum und kann Survivorship Bias enthalten.
- Primaeres Swing-Lab-Artefakt: `Trading/02_Swing-Lab/artifacts/2026-05-15_breadth_composite_research.csv`.

## Swing-Lab-Ergebnis vom 2026-05-15

Die laengere Analyse bestaetigt die Arbeitslesart, aber mit einer wichtigen Schaerfung:
Der Composite ist kein simples "negativ schlecht, positiv gut"-Signal. Der robusteste Befund
ist das **Healing-Regime** nach einer beschaedigten Marktphase.

Regime-Definition im Dashboard:

- `Damaged`: 5D-Composite < 0 oder mindestens 3 Tage in Folge Composite < 0.
- `Healing`: 1 bis 10 Handelstage nach Ende von Damaged, sofern der 5D-Composite wieder > 0 liegt.
- `Weakening`: 5D-Composite > 0, aber ueber 5 Handelstage um mindestens 4 Punkte gefallen.
- `Positive`: 5D-Composite > 3.
- `Other`: kein klares Regime.

Research-Lesart:

- `Healing` ist konstruktivster Kontext fuer Pullback-Setups.
- `Weakening` ist ein Vorsichtssignal, kein Verkaufssignal.
- `Damaged` zeigt Mean-Reversion-Potenzial, braucht aber SPY-Trendkontext.
- In echtem Baerenmarkt-Kontext, insbesondere SPY unter SMA200 und Drawdown >= 20%, ist der Composite als Kaufsignal blind.
- Der getestete pauschale Filter B wurde im Holdout verworfen; das Dashboard sollte deshalb keine harte Damaged-Ausschlussregel erzwingen.

## Rueckfluss ins Dashboard

Stand 2026-05-16 ist die Regime-Definition in der Breadth-Detailseite umgesetzt:

- die Composite-Box zeigt neben dem Punktwert ein Regime-Label,
- der Tooltip zeigt den 5D-Composite,
- der kurze Readout erklaert die operative Lesart des aktuellen Regimes,
- die Heatmap-Historie behaelt weiterhin den Tages-Composite als numerische Spalte.

Bewusst nicht umgesetzt wurde ein harter Trading-Filter. Die Research-Erkenntnis wird als Kontext angezeigt, nicht als automatisches Entry-/Exit-Signal.

## Beobachtung

Markus hat die negativen Breadth-Composite-Phasen im SPY-Chart markiert. Die markierten Bereiche passen fachlich gut zu der Interpretation, dass ein negativer Composite weniger ein praezises Timing-Signal ist, sondern eher ein Risk-Off- bzw. Breadth-Damage-Filter.

Arbeitslesart:

- Composite < 0: Marktbreite ist angeschlagen; aggressive Long-Setups sollten kleiner oder selektiver behandelt werden.
- Mehrere negative Tage in Folge sind relevanter als ein einzelner negativer Tag.
- Stark negative Cluster sind eher ein Regime-Hinweis als ein sofortiges Short-Signal.
- Das Ende eines negativen Clusters kann ein Healing-/Rebound-Setup markieren, braucht aber Preisbestaetigung.

## Erste Cluster-Auswertung

Vorlaeufige Auswertung der negativen Composite-Cluster:

| Filter | Cluster | Negative Tage | SPY waehrend Cluster | SPY +10 Tage | SPY +20 Tage |
|---|---:|---:|---:|---:|---:|
| Alle negativen Cluster | 122 | 424 | -0.72% | +1.41% | +2.19% |
| Dauerhaft, mindestens 3 Tage | 42 | 324 | -2.00% | +1.64% | +2.73% |
| Stark, Minimum <= -8 | 39 | 304 | -1.87% | +1.71% | +2.83% |
| Dauerhaft oder stark | 47 | 331 | -1.74% | +1.77% | +2.71% |

Interpretation: Die eigentliche Information liegt nicht im ersten roten Tag, sondern in Tiefe und Dauer. Auffaellig ist, dass SPY waehrend dauerhafter/starker negativer Cluster im Schnitt faellt, danach aber haeufig positive 10- bis 20-Tage-Returns zeigt. Das spricht dafuer, den Composite als Regime- und Healing-Kontext zu nutzen, nicht als isoliertes Entry-Signal.

## Was man zusaetzlich aus den Daten ziehen kann

1. Cluster-Dauer statt Tageswert

Ein einzelner negativer Print ist wahrscheinlich zu noisy. Interessanter waeren Regeln wie "Composite < 0 fuer mindestens 3 Tage" oder "Composite faellt unter -8". Das trennt kleine Luftloecher von echter Breadth-Beschaedigung.

2. Healing-Signal

Der erste Wechsel von negativ auf >= 0 nach einem dauerhaften oder stark negativen Cluster koennte ein eigenes Signal sein. Nicht als blindes Kaufsignal, sondern als Hinweis: Der Markt beginnt intern zu reparieren, Pullback- und Breakout-Setups koennen wieder interessanter werden.

3. Divergenz zum Index

Eine weniger offensichtliche Erkenntnis waere: SPY steht nahe Hochs, aber Composite macht tiefere Hochs oder kippt unter 0. Das waere ein Warnsignal fuer verengte Fuehrung. Umgekehrt kann ein steigender Composite bei seitwaerts laufendem SPY auf Akkumulation unter der Oberflaeche hindeuten.

4. Komponenten-Attribution

Nicht jedes Rot ist gleich. Wir sollten spaeter unterscheiden:

- Trend-Breadth-Schaden: SMA50/SMA200 schwach.
- Leadership-Schaden: 52W High/Low und Near High schwach.
- Momentum-Schock: 4%- und 25%-Werte schwach.
- Spekulations-/Exzess-Signal: 50% 1M contrarian auffaellig.

Das kann erklaeren, ob der Markt strukturell bricht oder nur kurzfristig durchgeschuettelt wird.

5. Scanner-Regime

Der naechste praktische Test waere, Scanner-Hits nach Composite-Buckets auszuwerten:

- Composite negativ: weniger neue Longs, strengere Qualitaetsfilter.
- Composite neutral: normale Positionsgroesse, aber keine Aggressivitaet.
- Composite positiv: Pullbacks in Fuehrungswerten bevorzugen.
- Composite sehr positiv plus spekulative 50% 1M-Hitze: Ueberdehnung nicht ignorieren.

Das waere fuer das Dashboard wahrscheinlich wertvoller als den Composite einfach groesser auf der Seite zu zeigen.

6. Recovery-Qualitaet

Ein Composite, der durch 4%-Momentum wieder positiv wird, aber bei 52W High/Low und Near High schwach bleibt, ist ein anderes Signal als eine breite Fuehrungs-Reparatur. Das koennte helfen, technische Rebounds von echter Marktbreiten-Erholung zu unterscheiden.

## Vorlaeufige Empfehlung

Der Composite sollte vorerst als Kontextwert bleiben:

- Rot/negativ: Risiko reduzieren und Long-Setups haerter filtern.
- Tief/dauerhaft negativ: nicht gegen die Marktbreite kaempfen.
- Rueckkehr auf >= 0: auf Healing achten, aber Preis- und Scanner-Bestaetigung verlangen.
- Sehr positiv: Trendstaerke anerkennen, aber mit 50% 1M auf Ueberhitzung pruefen.

Naechster sinnvoller Schritt waere kein weiteres UI-Element, sondern eine kleine reproduzierbare Analyse: negative Cluster, Healing-Tage, Forward Returns und Scanner-Hit-Qualitaet nach Composite-Buckets.
