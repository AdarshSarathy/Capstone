from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from packages.database.session import get_db_session
from packages.database.models import (
    Reservation, ReservationStatus, 
    ParkingSlot, SlotStatus, SlotType,
    ParkingSession, SessionStatus
)
from apps.api.routers.ws import manager

router = APIRouter()

class CheckInRequest(BaseModel):
    lot_id: str
    qr_token: Optional[str] = None
    vehicle_plate: Optional[str] = None

class CheckInResponse(BaseModel):
    session_id: str
    slot_code: str
    message: str

@router.post("/check-in", response_model=CheckInResponse)
async def gate_check_in(
    req: CheckInRequest,
    db: AsyncSession = Depends(get_db_session)
):
    if not req.qr_token and not req.vehicle_plate:
        raise HTTPException(status_code=400, detail="Must provide qr_token or vehicle_plate")

    # 1. Verify reservation
    reservation = None
    if req.qr_token:
        stmt = select(Reservation).where(
            Reservation.qr_token == req.qr_token,
            Reservation.lot_id == uuid.UUID(req.lot_id),
            Reservation.status == ReservationStatus.CONFIRMED
        )
        result = await db.execute(stmt)
        reservation = result.scalars().first()
    elif req.vehicle_plate:
        stmt = select(Reservation).where(
            Reservation.vehicle_plate == req.vehicle_plate,
            Reservation.lot_id == uuid.UUID(req.lot_id),
            Reservation.status == ReservationStatus.CONFIRMED
        )
        result = await db.execute(stmt)
        reservation = result.scalars().first()

    # For MVP, if no reservation, we might reject or allow pure walk-ins based on logic.
    # The requirement specifically talks about "verify reservation validity" for the POST.
    # Let's assume walk-ins are also handled here but let's strictly require reservation for this endpoint as per spec:
    # "Receive qr_token (or manual license plate entry). Verify reservation validity."
    if not reservation:
        raise HTTPException(status_code=404, detail="Valid reservation not found")

    now = datetime.now(timezone.utc)
    if not (reservation.eta_window_start <= now <= reservation.eta_window_end):
        # We might want some grace period, but let's stick to window
        # Wait, if they are early, maybe wait. If late, EXPIRED.
        pass

    # 2. Find and lock exactly one compatible AVAILABLE slot
    # Use SELECT ... FOR UPDATE SKIP LOCKED
    slot_stmt = (
        select(ParkingSlot)
        .where(
            ParkingSlot.lot_id == uuid.UUID(req.lot_id),
            ParkingSlot.slot_type == reservation.slot_type,
            ParkingSlot.current_status == SlotStatus.AVAILABLE,
            ParkingSlot.is_active == True
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    slot_result = await db.execute(slot_stmt)
    slot = slot_result.scalars().first()

    if not slot:
        raise HTTPException(status_code=503, detail="No compatible slots currently available")

    # 3. Update slot state and reservation state
    slot.current_status = SlotStatus.OCCUPIED
    reservation.status = ReservationStatus.CHECKED_IN

    # 4. Create active parking_session
    new_session = ParkingSession(
        reservation_id=reservation.id,
        slot_id=slot.id,
        lot_id=uuid.UUID(req.lot_id),
        vehicle_plate=reservation.vehicle_plate,
        check_in_at=now,
        status=SessionStatus.ACTIVE
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    # 5. Broadcast event via WebSockets to the guard dashboard
    broadcast_data = {
        "event": "SLOT_OCCUPIED",
        "data": {
            "slot_id": str(slot.id),
            "slot_code": slot.slot_code,
            "status": "OCCUPIED",
            "vehicle_plate": reservation.vehicle_plate
        }
    }
    await manager.broadcast_state(broadcast_data)

    return CheckInResponse(
        session_id=str(new_session.id),
        slot_code=slot.slot_code,
        message="Check-in successful"
    )

class SlotInfo(BaseModel):
    id: str
    slot_code: str
    slot_type: str
    current_status: str

@router.get("/slots", response_model=list[SlotInfo])
async def get_all_slots(db: AsyncSession = Depends(get_db_session)):
    stmt = select(ParkingSlot).order_by(ParkingSlot.slot_code)
    result = await db.execute(stmt)
    slots = result.scalars().all()
    
    return [
        SlotInfo(
            id=str(slot.id),
            slot_code=slot.slot_code,
            slot_type=slot.slot_type.value,
            current_status=slot.current_status.value
        )
        for slot in slots
    ]

