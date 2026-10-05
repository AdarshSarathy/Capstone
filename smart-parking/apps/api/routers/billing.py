from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
import hmac
import hashlib
import os

from packages.database.session import get_db_session
from packages.database.models import (
    ParkingSession, SessionStatus,
    ParkingSlot, SlotStatus,
    Payment, PaymentStatus
)
from apps.api.routers.ws import manager

router = APIRouter()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "rzp_test_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret")
HOURLY_RATE = 50.0 # INR 50 per hour

class CheckoutResponse(BaseModel):
    payment_link: str
    order_id: str
    amount: float
    duration_minutes: int

@router.post("/{session_id}/checkout", response_model=CheckoutResponse)
async def checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(ParkingSession).where(ParkingSession.id == uuid.UUID(session_id))
    result = await db.execute(stmt)
    session = result.scalars().first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == SessionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Session already completed")

    now = datetime.now(timezone.utc)
    duration = now - session.check_in_at
    duration_minutes = max(1, int(duration.total_seconds() / 60))
    
    # Calculate amount: 50 INR per hour, min 1 hour
    hours = max(1, (duration_minutes + 59) // 60)
    amount = hours * HOURLY_RATE

    # Update session checkout time and total amount
    session.check_out_at = now
    session.total_amount = amount

    # Mock Razorpay Order Creation
    order_id = f"order_{uuid.uuid4().hex[:10]}"
    payment_link = f"https://mock-razorpay.com/pay/{order_id}"

    # Create Payment record
    payment = Payment(
        session_id=session.id,
        razorpay_order_id=order_id,
        amount=amount,
        status=PaymentStatus.PENDING
    )
    db.add(payment)
    await db.commit()

    return CheckoutResponse(
        payment_link=payment_link,
        order_id=order_id,
        amount=amount,
        duration_minutes=duration_minutes
    )

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
    db: AsyncSession = Depends(get_db_session)
):
    payload = await request.body()
    
    # Verify HMAC SHA-256 signature
    expected_signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()
    event = data.get("event")
    
    if event == "payment.captured":
        # Process payment
        payment_entity = data["payload"]["payment"]["entity"]
        order_id = payment_entity.get("order_id")
        
        stmt = select(Payment).where(Payment.razorpay_order_id == order_id)
        res = await db.execute(stmt)
        payment = res.scalars().first()
        
        if payment:
            payment.status = PaymentStatus.PAID
            payment.razorpay_payment_id = payment_entity.get("id")
            
            # Get associated session and slot
            session_stmt = select(ParkingSession).where(ParkingSession.id == payment.session_id)
            session_res = await db.execute(session_stmt)
            session = session_res.scalars().first()
            
            if session and session.slot_id:
                session.status = SessionStatus.COMPLETED
                
                slot_stmt = select(ParkingSlot).where(ParkingSlot.id == session.slot_id)
                slot_res = await db.execute(slot_stmt)
                slot = slot_res.scalars().first()
                
                if slot:
                    slot.current_status = SlotStatus.AVAILABLE
                    
                    # Broadcast <100ms state update over WebSocket
                    await manager.broadcast_state({
                        "event": "SLOT_AVAILABLE",
                        "data": {
                            "slot_id": str(slot.id),
                            "slot_code": slot.slot_code,
                            "status": "AVAILABLE"
                        }
                    })
            await db.commit()
    
    return {"status": "ok"}
