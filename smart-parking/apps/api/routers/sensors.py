from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from packages.database.session import get_db_session
from packages.database.models import SensorEvent, ParkingSlot, SlotStatus
from apps.api.routers.ws import manager

router = APIRouter()

class SensorEventPayload(BaseModel):
    slot_id: str
    distance_cm: float

@router.post("/event")
async def handle_sensor_event(
    payload: SensorEventPayload,
    db: AsyncSession = Depends(get_db_session)
):
    # Retrieve slot
    stmt = select(ParkingSlot).where(ParkingSlot.id == uuid.UUID(payload.slot_id))
    result = await db.execute(stmt)
    slot = result.scalars().first()
    
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
        
    # Firmware has a 15cm debounce filter. We apply logic here as well.
    detected_state = SlotStatus.OCCUPIED if payload.distance_cm < 15.0 else SlotStatus.AVAILABLE
    
    # Store event
    event = SensorEvent(
        slot_id=slot.id,
        distance_cm=payload.distance_cm,
        detected_state=detected_state
    )
    db.add(event)
    
    # Update slot if state changed
    if slot.current_status != detected_state and slot.current_status not in [SlotStatus.RESERVED, SlotStatus.MAINTENANCE]:
        slot.current_status = detected_state
        
        # Broadcast <100ms state update over WebSocket
        await manager.broadcast_state({
            "event": f"SLOT_{detected_state.value}",
            "data": {
                "slot_id": str(slot.id),
                "slot_code": slot.slot_code,
                "status": detected_state.value
            }
        })
        
    await db.commit()
    return {"status": "ok", "detected_state": detected_state.value}
