from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ForecastState(Enum):
    FORECAST = "FORECAST"
    FALLBACK = "FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"

@dataclass
class CapacityState:
    compatible_total: int
    unavailable: int
    committed_reservations: int
    predicted_non_reserved: float
    walk_in_reserve: int
    uncertainty_buffer: float

class AdmissionEngine:
    """
    Deterministic Admission Engine
    ML predicts demand. Policy decides admission. System executes.
    """
    
    @staticmethod
    def calculate_safe_capacity(state: CapacityState) -> int:
        """
        SafeCapacity = C_comp - U_unavail - R_committed - D_non_reserved - B_walk_in - sigma_uncertainty
        """
        safe_capacity = (
            state.compatible_total
            - state.unavailable
            - state.committed_reservations
            - state.predicted_non_reserved
            - state.walk_in_reserve
            - state.uncertainty_buffer
        )
        return max(0, int(safe_capacity))

    @staticmethod
    def evaluate_admission(
        forecast_state: ForecastState,
        compatible_total: int,
        unavailable: int,
        committed_reservations: int,
        predicted_non_reserved: float,
        walk_in_reserve_pct: float,
        mae_buffer: float = 0.0
    ) -> bool:
        """
        Evaluates whether a new reservation or walk-in can be admitted based on current forecast state.
        Returns True if a spot can be allocated safely, False otherwise.
        """
        walk_in_reserve = int(compatible_total * walk_in_reserve_pct)
        
        if forecast_state == ForecastState.UNAVAILABLE:
            # Complete rejection of dynamic walk-in allocation if no forecast is available,
            # unless we have strict capacity for commitments only.
            # Here we just admit if C - U - R > 0
            safe_capacity = compatible_total - unavailable - committed_reservations
            return safe_capacity > 0
            
        elif forecast_state == ForecastState.FALLBACK:
            # Conservative historical baseline with higher uncertainty buffer
            uncertainty_buffer = max(mae_buffer * 1.5, compatible_total * 0.1) # 10% or 1.5x MAE
            state = CapacityState(
                compatible_total=compatible_total,
                unavailable=unavailable,
                committed_reservations=committed_reservations,
                predicted_non_reserved=predicted_non_reserved,
                walk_in_reserve=walk_in_reserve,
                uncertainty_buffer=uncertainty_buffer
            )
            return AdmissionEngine.calculate_safe_capacity(state) > 0
            
        elif forecast_state == ForecastState.FORECAST:
            # Usable ML prediction with dynamic uncertainty buffer derived from MAE.
            uncertainty_buffer = mae_buffer
            state = CapacityState(
                compatible_total=compatible_total,
                unavailable=unavailable,
                committed_reservations=committed_reservations,
                predicted_non_reserved=predicted_non_reserved,
                walk_in_reserve=walk_in_reserve,
                uncertainty_buffer=uncertainty_buffer
            )
            return AdmissionEngine.calculate_safe_capacity(state) > 0
        
        return False
