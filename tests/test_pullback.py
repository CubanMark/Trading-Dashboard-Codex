import pandas as pd

from trading_dashboard.scanners.pullback import (
    annotate_overlaps,
    is_pullback_candidate,
    ma_distance_atr,
    matching_pullback_variants,
    near_moving_average,
    passes_relative_strength,
    pullback_hits,
)


def test_pullback_candidate_requires_spy_regime():
    frame = make_trending_frame()
    assert not is_pullback_candidate(frame, spy_ok=False)


def test_pullback_candidate_detects_three_down_closes_in_uptrend():
    frame = make_trending_frame()
    assert is_pullback_candidate(frame, spy_ok=True)


def test_ma10_and_ma20_variants_are_detected_separately():
    frame = make_trending_frame()
    variants = {variant[0] for variant in matching_pullback_variants(frame, spy_ok=True)}
    assert "pullback_3d_research" in variants
    assert "pullback_ma10_research" in variants
    assert "pullback_ma20_research" in variants


def test_near_moving_average_rejects_far_pullback():
    frame = make_trending_frame()
    frame.loc[frame.index[-1], "close"] = frame["close"].iloc[-1] * 0.8
    assert not near_moving_average(frame, 10)


def test_near_moving_average_uses_atr_normalized_distance():
    frame = make_trending_frame()
    average = frame["close"].tail(10).mean()
    frame.loc[frame.index[-1], "close"] = average + 0.60 * 2.0
    frame.loc[frame.index[-1], "high"] = frame.loc[frame.index[-1], "close"] + 1
    frame.loc[frame.index[-1], "low"] = frame.loc[frame.index[-1], "close"] - 1

    assert near_moving_average(frame, 10)
    assert ma_distance_atr(frame, 10) is not None


def test_variants_require_liquid_priceable_stock():
    frame = make_trending_frame()
    frame["volume"] = 100_000
    assert matching_pullback_variants(frame, spy_ok=True) == []


def test_variants_require_near_52w_high():
    frame = make_trending_frame()
    frame.loc[frame.index[-1], "close"] = frame["close"].iloc[-1] * 0.65
    assert matching_pullback_variants(frame, spy_ok=True) == []


def test_relative_strength_gate_requires_top_rank():
    assert passes_relative_strength(70)
    assert not passes_relative_strength(69.9)
    assert not passes_relative_strength(None)


def test_annotate_overlaps_lists_other_scanners_for_same_symbol():
    rows = [
        {"symbol": "AAPL", "scanner_label": "Pullback MA10"},
        {"symbol": "AAPL", "scanner_label": "Pullback MA20"},
        {"symbol": "MSFT", "scanner_label": "3D Pullback"},
    ]
    annotated = annotate_overlaps(rows)
    assert annotated[0]["also_in"] == "Pullback MA20"
    assert annotated[1]["also_in"] == "Pullback MA10"
    assert annotated[2]["also_in"] == ""


def test_pullback_hits_excludes_flagged_symbols():
    frame = make_trending_frame()
    price_map = {"SPY": frame, "AAPL": frame}

    rows = pullback_hits(price_map, "2024-12-27", ["AAPL"], {"AAPL": ("Technology", "Software")}, {"AAPL"})

    assert rows == []


def make_trending_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=260)
    close = pd.Series(range(100, 360), dtype=float)
    close.iloc[-20:] = [348] * 16 + [350, 349, 348, 347]
    return pd.DataFrame(
        {
            "symbol": "AAPL",
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000,
        }
    )
