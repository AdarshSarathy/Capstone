import asyncio
import uuid
from packages.database.session import async_session_maker
from packages.database.models import ParkingLot, ParkingSlot, SlotType, SlotStatus

async def seed_database():
    print("Starting database seed...")
    async with async_session_maker() as db:
        # Create Main ParkingLot
        # Hardcoding the UUID so the simulator and frontends can easily reference it
        # as defined in the frontend/simulator code: "00000000-0000-0000-0000-000000000001"
        lot_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        
        lot = ParkingLot(
            id=lot_id,
            name="VIT Main Campus Level 1",
            total_capacity=36,
            walk_in_reserve_pct=0.15
        )
        db.add(lot)
        
        # Create 36 ParkingSlots: Rows A, B, C; Cols 01-12
        # C-11 and C-12 will be EV, A-01 and A-02 Accessible
        slots = []
        for row_idx, row_letter in enumerate(['A', 'B', 'C']):
            for col_idx in range(1, 13):
                slot_code = f"{row_letter}-{col_idx:02d}"
                slot_type = SlotType.REGULAR
                
                if row_letter == 'C' and col_idx >= 11:
                    slot_type = SlotType.EV
                elif row_letter == 'A' and col_idx <= 2:
                    slot_type = SlotType.ACCESSIBLE
                    
                # Make a few of them occupied/reserved for initial state realism
                status = SlotStatus.AVAILABLE
                if row_letter == 'B' and col_idx % 3 == 0:
                    status = SlotStatus.OCCUPIED
                if row_letter == 'A' and col_idx == 10:
                    status = SlotStatus.RESERVED
                    
                slot = ParkingSlot(
                    id=uuid.uuid4(),
                    lot_id=lot_id,
                    slot_code=slot_code,
                    slot_type=slot_type,
                    current_status=status,
                    is_active=True
                )
                slots.append(slot)
                
        db.add_all(slots)
        
        try:
            await db.commit()
            print(f"Successfully seeded ParkingLot '{lot.name}' and {len(slots)} ParkingSlots.")
        except Exception as e:
            await db.rollback()
            print(f"Seed failed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_database())
