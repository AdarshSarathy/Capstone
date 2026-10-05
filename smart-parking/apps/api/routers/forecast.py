from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import uuid

from packages.database.session import get_db_session
from packages.database.models import ParkingLot, ParkingSlot, SlotStatus, Reservation, ReservationStatus, SlotType
from packages.domain.admission import AdmissionEngine
from packages.ml.inference import predictor

router = APIRouter()

class ForecastResponse(BaseModel):
    available_spots: int
    safe_capacity: int
    occupancy_pct: float
    message: str

class ReservationRequest(BaseModel):
    lot_id: str
    user_id: str
    vehicle_plate: str
    eta_minutes: int
    slot_type: SlotType = SlotType.REGULAR

class ReservationResponse(BaseModel):
    reservation_id: str
    qr_token: str
    eta_window_start: datetime
    eta_window_end: datetime

@router.get("/occupancy", response_model=ForecastResponse)
async def get_forecast(
    lot_id: str,
    eta_minutes: int,
    db: AsyncSession = Depends(get_db_session)
):
    # 1. Get current lot state
    lot_stmt = select(ParkingLot).where(ParkingLot.id == uuid.UUID(lot_id))
    lot_res = await db.execute(lot_stmt)
    lot = lot_res.scalars().first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    # Count occupied/unavailable
    slots_stmt = select(
        func.count(ParkingSlot.id)
    ).where(
        ParkingSlot.lot_id == lot.id,
        ParkingSlot.current_status != SlotStatus.AVAILABLE
    )
    unavailable = (await db.execute(slots_stmt)).scalar() or 0
    current_occupancy_pct = (unavailable / lot.total_capacity) * 100 if lot.total_capacity else 0

    # Count committed reservations for the window
    now = datetime.now(timezone.utc)
    target_time = now + timedelta(minutes=eta_minutes)
    
    res_stmt = select(
        func.count(Reservation.id)
    ).where(
        Reservation.lot_id == lot.id,
        Reservation.status == ReservationStatus.CONFIRMED,
        Reservation.eta_window_start <= target_time,
        Reservation.eta_window_end >= target_time
    )
    committed = (await db.execute(res_stmt)).scalar() or 0

    # ML Inference
    forecast_state, predicted_demand, mae_buffer = predictor.predict_non_reserved_demand(
        lot_id=lot_id,
        eta_minutes=eta_minutes,
        current_occupancy_pct=current_occupancy_pct,
        day_of_week=target_time.weekday(),
        hour_of_day=target_time.hour,
        is_holiday=False, # Mock
        rolling_avg_inflow=2.0, # Mock
        weather_condition=0 # Mock
    )

    # Policy
    import packages.domain.admission as domain
    state = domain.CapacityState(
        compatible_total=lot.total_capacity,
        unavailable=unavailable,
        committed_reservations=committed,
        predicted_non_reserved=predicted_demand,
        walk_in_reserve=int(lot.total_capacity * lot.walk_in_reserve_pct),
        uncertainty_buffer=mae_buffer
    )
    safe_capacity = AdmissionEngine.calculate_safe_capacity(state)

    return ForecastResponse(
        available_spots=max(0, lot.total_capacity - unavailable),
        safe_capacity=safe_capacity,
        occupancy_pct=current_occupancy_pct,
        message=f"{current_occupancy_pct:.1f}% occupancy — ~{safe_capacity} spots free at ETA"
    )

@router.post("/reserve", response_model=ReservationResponse)
async def reserve_capacity(
    req: ReservationRequest,
    db: AsyncSession = Depends(get_db_session)
):
    # Check forecast to see if admission policy allows reservation
    # For a real system, we'd wrap this in a transaction or use row locks on the lot aggregates
    forecast = await get_forecast(req.lot_id, req.eta_minutes, db)
    
    if forecast.safe_capacity <= 0:
        raise HTTPException(status_code=503, detail="Capacity full for requested window")

    now = datetime.now(timezone.utc)
    eta = now + timedelta(minutes=req.eta_minutes)
    window_start = eta - timedelta(minutes=15)
    window_end = eta + timedelta(minutes=30)
    qr_token = f"qr_{uuid.uuid4().hex}"

    reservation = Reservation(
        lot_id=uuid.UUID(req.lot_id),
        user_id=req.user_id,
        vehicle_plate=req.vehicle_plate,
        slot_type=req.slot_type,
        eta_window_start=window_start,
        eta_window_end=window_end,
        status=ReservationStatus.CONFIRMED,
        qr_token=qr_token
    )
    db.add(reservation)
    await db.commit()

    return ReservationResponse(
        reservation_id=str(reservation.id),
        qr_token=qr_token,
        eta_window_start=window_start,
        eta_window_end=window_end
    )
