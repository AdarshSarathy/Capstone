import pytest
from packages.domain.admission import AdmissionEngine, ForecastState, CapacityState

def test_admission_unavailable_mode():
    # C=10, U=2, R=3 -> Safe Capacity = 5 for commitments
    # In UNAVAILABLE mode, walk-in prediction is ignored, but we admit if C - U - R > 0
    res = AdmissionEngine.evaluate_admission(
        forecast_state=ForecastState.UNAVAILABLE,
        compatible_total=10,
        unavailable=2,
        committed_reservations=3,
        predicted_non_reserved=10.0, # should be ignored conceptually, but our policy just checks if C - U - R > 0
        walk_in_reserve_pct=0.15
    )
    assert res is True

def test_admission_unavailable_mode_full():
    res = AdmissionEngine.evaluate_admission(
        forecast_state=ForecastState.UNAVAILABLE,
        compatible_total=10,
        unavailable=5,
        committed_reservations=5,
        predicted_non_reserved=0.0,
        walk_in_reserve_pct=0.15
    )
    assert res is False

def test_admission_fallback_mode():
    # FALLBACK uses 10% of total or 1.5x MAE as buffer.
    # C=100, U=20, R=10, Predicted=30, Walk-in Reserve=15. Buffer = max(0.0 * 1.5, 100*0.1) = 10
    # Safe Capacity = 100 - 20 - 10 - 30 - 15 - 10 = 15 > 0
    res = AdmissionEngine.evaluate_admission(
        forecast_state=ForecastState.FALLBACK,
        compatible_total=100,
        unavailable=20,
        committed_reservations=10,
        predicted_non_reserved=30.0,
        walk_in_reserve_pct=0.15,
        mae_buffer=0.0
    )
    assert res is True

    # High prediction causes rejection
    res2 = AdmissionEngine.evaluate_admission(
        forecast_state=ForecastState.FALLBACK,
        compatible_total=100,
        unavailable=20,
        committed_reservations=10,
        predicted_non_reserved=50.0, # Safe Capacity = 100 - 20 - 10 - 50 - 15 - 10 = -5
        walk_in_reserve_pct=0.15,
        mae_buffer=0.0
    )
    assert res2 is False

def test_admission_forecast_mode():
    # FORECAST uses exact MAE
    # C=100, U=20, R=10, Pred=40, Reserve=15, MAE=5
    # Safe Capacity = 100 - 20 - 10 - 40 - 15 - 5 = 10 > 0
    res = AdmissionEngine.evaluate_admission(
        forecast_state=ForecastState.FORECAST,
        compatible_total=100,
        unavailable=20,
        committed_reservations=10,
        predicted_non_reserved=40.0,
        walk_in_reserve_pct=0.15,
        mae_buffer=5.0
    )
    assert res is True
