import asyncio
import httpx
import uuid
import random
from datetime import datetime, timedelta, timezone

API_BASE = "http://localhost:8000/api/v1"
LOT_ID = "00000000-0000-0000-0000-000000000001"
TOTAL_CARS = 200
COMPRESSED_HOUR = 2 # 2 seconds of real time = 1 simulated hour
SIM_TIME = datetime.now(timezone.utc)

async def simulate_car(car_id: int, client: httpx.AsyncClient):
    # Random arrival time (offset from start)
    arrival_offset_hours = random.uniform(0, 24)
    await asyncio.sleep(arrival_offset_hours * COMPRESSED_HOUR)

    plate = f"SIM-{car_id:04d}"
    print(f"[{plate}] Arriving at gate...")
    
    # 1. Book reservation right before arrival
    try:
        res = await client.post(f"{API_BASE}/forecast/reserve", json={
            "lot_id": LOT_ID,
            "user_id": f"user_{car_id}",
            "vehicle_plate": plate,
            "eta_minutes": 5,
            "slot_type": "REGULAR"
        })
        if res.status_code != 200:
            print(f"[{plate}] Failed to reserve: {res.text}")
            return
        data = res.json()
        qr_token = data["qr_token"]
        session_id = None
        
        # 2. Check-in (Scan QR)
        checkin_res = await client.post(f"{API_BASE}/gate/check-in", json={
            "lot_id": LOT_ID,
            "qr_token": qr_token
        })
        if checkin_res.status_code == 200:
            checkin_data = checkin_res.json()
            session_id = checkin_data["session_id"]
            print(f"[{plate}] Checked in. Assigned Slot: {checkin_data['slot_code']}")
        else:
            print(f"[{plate}] Check-in failed: {checkin_res.text}")
            return
            
        # 3. Dwell time (30-180 mins)
        dwell_mins = random.uniform(30, 180)
        dwell_sim_time = (dwell_mins / 60) * COMPRESSED_HOUR
        await asyncio.sleep(dwell_sim_time)
        
        # 4. Checkout
        checkout_res = await client.post(f"{API_BASE}/payments/{session_id}/checkout")
        if checkout_res.status_code == 200:
            chk_data = checkout_res.json()
            print(f"[{plate}] Checked out. Amount: {chk_data['amount']}, Payment Link: {chk_data['payment_link']}")
        else:
            print(f"[{plate}] Checkout failed: {checkout_res.text}")

    except Exception as e:
        print(f"[{plate}] Error in simulation: {e}")

async def main():
    print(f"Starting simulation of {TOTAL_CARS} cars over 24 compressed hours...")
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(TOTAL_CARS):
            tasks.append(simulate_car(i, client))
        await asyncio.gather(*tasks)
    print("Simulation complete.")

if __name__ == "__main__":
    asyncio.run(main())
