from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import gate, billing, forecast, sensors, ws

app = FastAPI(
    title="Smart Parking API",
    version="0.1.0",
    description="Smart Parking Reservation & Predictive Capacity Management System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gate.router, prefix="/api/v1/gate", tags=["Gate"])
app.include_router(billing.router, prefix="/api/v1/payments", tags=["Billing"])
app.include_router(forecast.router, prefix="/api/v1/forecast", tags=["Forecast"])
app.include_router(sensors.router, prefix="/api/v1/sensors", tags=["Sensors"])
app.include_router(ws.router, prefix="/ws", tags=["WebSockets"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
