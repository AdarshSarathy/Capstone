import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from apps.api.main import app
from packages.database.models import Base, ParkingLot, ParkingSlot, SlotStatus, SlotType, Reservation, ReservationStatus
from packages.database.session import get_db_session

# This test requires a running PostgreSQL instance because SQLite doesn't support SKIP LOCKED.
# We will use the DATABASE_URL environment variable or a test default.
TEST_DATABASE_URL = "postgresql+asyncpg://smartparking:password@localhost:5432/smartparking_db"

engine = create_async_engine(TEST_DATABASE_URL, pool_size=20, max_overflow=0)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def override_get_db_session():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        # Cleanup
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_concurrency_stress_test():
    """
    Fire 20 simultaneous check-ins against 3 available bays. 
    Verify that exactly 3 succeed, 17 return 503/fail, and zero bays are double-assigned.
    """
    lot_id = uuid.uuid4()
    
    async with TestingSessionLocal() as db:
        # Create 1 lot
        lot = ParkingLot(id=lot_id, name="Test Lot", total_capacity=3, walk_in_reserve_pct=0.0)
        db.add(lot)
        
        # Create exactly 3 available slots
        for i in range(3):
            slot = ParkingSlot(
                id=uuid.uuid4(),
                lot_id=lot_id,
                slot_code=f"A-{i}",
                slot_type=SlotType.REGULAR,
                current_status=SlotStatus.AVAILABLE,
                is_active=True
            )
            db.add(slot)
            
        # Create 20 reservations for this lot
        reservations = []
        now = datetime.now(timezone.utc)
        for i in range(20):
            res = Reservation(
                id=uuid.uuid4(),
                lot_id=lot_id,
                user_id=f"user_{i}",
                vehicle_plate=f"TEST-{i}",
                slot_type=SlotType.REGULAR,
                eta_window_start=now - timedelta(minutes=10),
                eta_window_end=now + timedelta(minutes=10),
                status=ReservationStatus.CONFIRMED,
                qr_token=f"qr_test_{i}"
            )
            db.add(res)
            reservations.append(res)
            
        await db.commit()

    # Now fire 20 simultaneous check-in requests
    async with AsyncClient(app=app, base_url="http://test") as ac:
        tasks = []
        for i in range(20):
            req_data = {
                "lot_id": str(lot_id),
                "qr_token": f"qr_test_{i}"
            }
            tasks.append(ac.post("/api/v1/gate/check-in", json=req_data))
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Analyze results
    success_count = 0
    fail_count = 0
    assigned_slots = set()
    
    for r in responses:
        if isinstance(r, Exception):
            fail_count += 1
            continue
            
        if r.status_code == 200:
            success_count += 1
            data = r.json()
            assigned_slots.add(data["slot_code"])
        else:
            fail_count += 1

    # Verify exactly 3 succeed
    assert success_count == 3
    # Verify 17 fail
    assert fail_count == 17
    # Verify exactly 3 distinct slots were assigned (zero double-assigned)
    assert len(assigned_slots) == 3
