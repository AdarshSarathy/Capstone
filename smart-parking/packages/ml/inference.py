import math
from typing import Tuple
from packages.domain.admission import ForecastState

class MLPredictor:
    """
    XGBoost Inference Wrapper Class
    """
    @staticmethod
    def predict_non_reserved_demand(
        lot_id: str, 
        eta_minutes: int, 
        current_occupancy_pct: float,
        day_of_week: int,
        hour_of_day: int,
        is_holiday: bool,
        rolling_avg_inflow: float,
        weather_condition: int
    ) -> Tuple[ForecastState, float, float]:
        """
        Returns (ForecastState, predicted_demand, mae_buffer)
        Must execute in sub-10ms latency.
        """
        # For MVP, we provide a deterministic mock of the ML model
        # Normally, we'd load `xgboost.Booster` and call `predict()`
        
        if eta_minutes > 120:
            return ForecastState.UNAVAILABLE, 0.0, 0.0
            
        if current_occupancy_pct < 0 or current_occupancy_pct > 100:
            return ForecastState.FALLBACK, 20.0, 10.0 # historical baseline
            
        # Mock prediction logic simulating a model
        base_demand = 10.0
        time_factor = math.sin(hour_of_day * math.pi / 12) * 15 # Peak at hour 6 and 18 (conceptually)
        weather_factor = 5.0 if weather_condition else 0.0
        
        predicted = base_demand + time_factor + weather_factor + (rolling_avg_inflow * 2)
        predicted = max(0.0, predicted)
        
        mae_buffer = 3.5 # Fixed MAE buffer for the mock
        
        return ForecastState.FORECAST, predicted, mae_buffer

predictor = MLPredictor()
