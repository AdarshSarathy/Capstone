# 🅿️ Smart Parking Reservation & Predictive Capacity Management System

A production-grade, enterprise-ready Smart Parking system that combines **ML-driven demand forecasting**, **deterministic admission control**, and **real-time IoT sensor fusion** to deliver a seamless parking experience for drivers and facility operators.

> **Core Invariant:** A reservation guarantees *capacity* for an arrival window — never a specific physical bay. The physical slot is dynamically assigned at gate ingress using PostgreSQL row-level locks (`SELECT ... FOR UPDATE SKIP LOCKED`) to guarantee zero double-assignments under concurrent load.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENTS                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Guard        │  │ Driver PWA   │  │ Driver       │  │
│  │ Dashboard    │  │ (React/Vite) │  │ Mobile App   │  │
│  │ (React/Vite) │  │              │  │ (Expo/RN)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │ WebSocket       │ REST            │ REST     │
└─────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼──────────┐
│              FastAPI ASGI Server (Async)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Gate     │ │ Forecast │ │ Billing  │ │ Sensors  │  │
│  │ Router   │ │ Router   │ │ Router   │ │ Router   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       │             │            │             │        │
│  ┌────▼─────────────▼────┐ ┌────▼─────┐ ┌────▼─────┐  │
│  │ Admission Engine      │ │ Razorpay │ │ WS Hub   │  │
│  │ (Deterministic Policy)│ │ Webhooks │ │ (<100ms) │  │
│  └────────┬──────────────┘ └──────────┘ └──────────┘  │
│           │                                            │
│  ┌────────▼──────────┐                                 │
│  │ XGBoost ML        │                                 │
│  │ Demand Predictor  │                                 │
│  └───────────────────┘                                 │
└────────────────────────────┬───────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  PostgreSQL 16  │
                    │  (Async via     │
                    │   asyncpg)      │
                    └────────▲────────┘
                             │
                    ┌────────┴────────┐
                    │  ESP32 Sensor   │
                    │  Nodes (IoT)    │
                    └─────────────────┘
```

---

## 📁 Monorepo Structure

```
smart-parking/
├── apps/
│   ├── api/                     # FastAPI ASGI Server (REST + WebSockets)
│   │   ├── main.py              # App entrypoint, CORS, router registration
│   │   └── routers/
│   │       ├── gate.py          # POST /check-in, GET /slots
│   │       ├── billing.py       # POST /checkout, POST /webhook (Razorpay HMAC)
│   │       ├── forecast.py      # GET /occupancy, POST /reserve
│   │       ├── sensors.py       # POST /event (IoT sensor ingress)
│   │       └── ws.py            # WebSocket connection manager & broadcaster
│   ├── guard-dashboard/         # React 18 + Vite + Tailwind — Real-time 2D Bay Grid
│   ├── driver-pwa/              # React 18 + Vite + Tailwind — Web booking & QR
│   ├── driver-mobile/           # React Native + Expo — Mobile booking app
│   └── simulator/               # Async Python load simulator (200 cars / 24hrs)
├── packages/
│   ├── domain/
│   │   └── admission.py         # Deterministic admission formula & policy engine
│   ├── database/
│   │   ├── models.py            # SQLAlchemy 2.0 async declarative models
│   │   └── session.py           # Async engine & session factory
│   └── ml/
│       └── inference.py         # XGBoost inference wrapper (sub-10ms)
├── firmware/
│   └── esp32-sensor-node/       # PlatformIO C++ — HC-SR04 sensor + SG90 servo
├── tests/
│   ├── test_admission.py        # Admission policy boundary tests
│   ├── test_concurrency.py      # 20-concurrent-checkin stress test
│   └── test_webhook.py          # HMAC signature verification tests
├── scripts/
│   └── seed_db.py               # Database seeding (1 lot, 36 slots)
├── migrations/                  # Alembic async migrations
├── docker-compose.yml           # PostgreSQL 16 container
├── pyproject.toml               # Poetry dependency management
└── Justfile                     # Build & run commands
```

---

## 🔑 Key Design Decisions

### 1. Capacity Promise ≠ Physical Slot
Reserving guarantees capacity for an arrival window. The specific physical bay (e.g., `B-04`) is assigned **only at gate check-in** using `SELECT ... FOR UPDATE SKIP LOCKED`, ensuring zero double-assignments even under 20+ concurrent requests.

### 2. ML Predicts. Policy Decides. System Executes.
The XGBoost model forecasts non-reserved walk-in demand. The **deterministic admission engine** makes the final admit/reject decision using the formula:

```
SafeCapacity = C_compatible − U_unavailable − R_committed − D̂_non_reserved − B_walk_in − σ_uncertainty
```

Three forecast modes are supported:
| Mode | Behavior |
|------|----------|
| `FORECAST` | ML prediction with MAE-derived uncertainty buffer |
| `FALLBACK` | Conservative historical baseline (1.5× buffer) |
| `UNAVAILABLE` | Reject all dynamic walk-in allocation |

### 3. Modular Monolith
No Kafka. No Redis. No microservices sprawl. A single FastAPI process with clean package boundaries (`domain/`, `database/`, `ml/`) handles all concerns asynchronously.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker Desktop (for PostgreSQL)
- Poetry (`pip install poetry`)

### 1. Start the Database
```bash
cd smart-parking
docker compose up -d postgres
```

### 2. Install Python Dependencies & Migrate
```bash
poetry install
poetry run alembic upgrade head
poetry run python scripts/seed_db.py
```

### 3. Start the Backend
```bash
poetry run fastapi dev apps/api/main.py
```
The API will be available at `http://localhost:8000`. Swagger docs at `/docs`.

### 4. Start the Guard Dashboard
```bash
cd apps/guard-dashboard
npm install
npm run dev
```
Opens at `http://localhost:5173` — shows the real-time 2D bay grid backed by live database state and WebSocket updates.

### 5. Start the Driver Web App
```bash
cd apps/driver-pwa
npm install
npm run dev
```
Opens at `http://localhost:5174` — book capacity, get a QR pass, simulate gate scan.

### 6. Start the Driver Mobile App (Expo)
```bash
cd apps/driver-mobile
npx expo start
```
Scan the QR code with **Expo Go** on your phone. Update `API_BASE` in `App.js` to your machine's local IP first.

---

## 🧪 Running Tests

```bash
# Unit tests (admission policy, webhook security)
poetry run pytest tests/test_admission.py tests/test_webhook.py -v

# Concurrency stress test (requires running PostgreSQL)
poetry run pytest tests/test_concurrency.py -v
```

The concurrency test fires **20 simultaneous check-ins** against **3 available bays** and verifies:
- ✅ Exactly 3 succeed
- ✅ Exactly 17 fail with 503
- ✅ Zero double-assignments

---

## 📊 Database Schema

| Table | Purpose |
|-------|---------|
| `parking_lots` | Facility definitions with walk-in reserve percentage |
| `parking_slots` | Physical bays with type (REGULAR/EV/ACCESSIBLE/VIP) and live status |
| `reservations` | Capacity reservations with QR tokens and ETA windows |
| `parking_sessions` | Active/completed parking sessions linking reservations to physical slots |
| `payments` | Razorpay payment records with HMAC-verified webhook processing |
| `sensor_events` | Raw IoT sensor readings for occupancy detection |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/forecast/occupancy` | ML-backed availability forecast for ETA window |
| `POST` | `/api/v1/forecast/reserve` | Create capacity reservation, returns QR token |
| `POST` | `/api/v1/gate/check-in` | Gate ingress — assigns physical bay with row locks |
| `GET` | `/api/v1/gate/slots` | Current state of all parking slots |
| `POST` | `/api/v1/payments/{id}/checkout` | Calculate duration & generate payment link |
| `POST` | `/api/v1/payments/webhook` | Razorpay HMAC-verified payment webhook |
| `POST` | `/api/v1/sensors/event` | IoT sensor state change ingress |
| `WS` | `/ws/sync` | Real-time slot state broadcast (<100ms) |

---

## 🔧 IoT Firmware

The `firmware/esp32-sensor-node/` directory contains PlatformIO C++ code for ESP32 microcontrollers:
- **HC-SR04** ultrasonic sensor with 1500ms debounce filter (< 15cm = occupied)
- **SG90** servo motor for boom barrier control
- JSON payloads dispatched to `POST /api/v1/sensors/event`

---

## 📜 License

This project is part of a Capstone submission. All rights reserved.
