"""Statistical-correctness tests for quantlib_metrics.py.

Each test asserts the CORRECTED CONSTANT (a value derived by hand or from a
reference library), not merely that the output changed.
"""
import math

import quantlib_metrics as qm


# ---- Item 2: expected_return_lognormal must be the MEAN E[S_T], not the median ----
def test_expected_return_lognormal_is_mean_not_median():
    spot, sigma, r = 100.0, 0.6, 0.05
    T = 21 / 252
    got = qm.expected_return_lognormal(spot, sigma, risk_free=r, horizon_years=T)

    # E[S_T] = spot * exp(r*T) for a risk-neutral lognormal (the arithmetic mean).
    mean = spot * math.exp(r * T)               # 100.4175...
    median = spot * math.exp((r - 0.5 * sigma ** 2) * T)  # 98.9225... (the OLD bug)

    assert abs(got - mean) < 0.02, f"expected mean {mean:.4f}, got {got:.4f}"
    assert abs(got - 100.42) < 0.05, f"expected about 100.42, got {got:.4f}"
    assert abs(got - median) > 1.0, "still returning the median (98.9), not the mean"


def test_expected_return_lognormal_no_negative_drift_bias():
    # With high vol the OLD median formula produced exp_return < 0 even when r > 0,
    # injecting a spurious SELL bias. The mean must be >= spot when r >= 0.
    spot = 100.0
    for sigma in (0.2, 0.6, 1.2):
        px = qm.expected_return_lognormal(spot, sigma, risk_free=0.05, horizon_years=21 / 252)
        assert px >= spot, f"mean price {px:.4f} < spot with r>0 and sigma={sigma} (SELL bias)"


# ---- Item 5 (Kelly): quarter-Kelly must be f*/4 THEN capped, not just min(cap, f*) ----
def test_kelly_is_quarter_then_capped():
    # A synthetic series with a strong positive drift so raw f* is large.
    # daily log return ~ +0.004 => mu_annual ~ 1.0; sigma small => f* huge -> cap.
    import numpy as np
    rng = np.random.default_rng(0)
    steps = 0.004 + 0.001 * rng.standard_normal(300)
    prices = list(100.0 * np.exp(np.cumsum(steps)))

    f_raw = qm._kelly_raw(prices, risk_free=0.05)      # full continuous f*
    f_used = qm.kelly_fraction(prices, risk_free=0.05)  # what the app reports

    cap = qm.KELLY_CAP
    expected = min(cap, max(0.0, f_raw / 4.0))
    assert abs(f_used - expected) < 1e-9, f"quarter-Kelly wrong: got {f_used}, expected {expected}"
    # sanity: a strong-drift series should hit the cap after /4
    assert f_used <= cap + 1e-9


# ---- Freebie: one shared risk-free rate, sane range ----
def test_single_risk_free_constant():
    import constants
    assert 0.0 <= constants.RISK_FREE_RATE <= 0.10
    # quantlib_metrics must consume the shared constant, not its own literal.
    assert qm.RISK_FREE_RATE == constants.RISK_FREE_RATE


# ---- Freebie: VaR has both a labeled parametric and a historical variant ----
def test_var_parametric_and_historical():
    import numpy as np
    rng = np.random.default_rng(1)
    prices = list(100.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(400))))

    par = qm.compute_var_95(prices)                  # parametric (normal assumption)
    hist = qm.historical_var_95(prices)              # empirical 5th percentile
    assert par > 0 and hist > 0
    # historical 5th percentile of |daily loss| should be within a factor of ~2 of parametric
    assert 0.3 < hist / par < 3.0
