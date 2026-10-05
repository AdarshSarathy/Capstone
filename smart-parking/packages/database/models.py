import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Integer,
    BigInteger,
    Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SlotType(enum.Enum):
    REGULAR = "REGULAR"
    EV = "EV"
    ACCESSIBLE = "ACCESSIBLE"
    VIP = "VIP"

class SlotStatus(enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"

class ReservationStatus(enum.Enum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class SessionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    OVERSTAY = "OVERSTAY"

class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    total_capacity = Column(Integer, nullable=False)
    walk_in_reserve_pct = Column(Float, nullable=False, default=0.15)
    
    slots = relationship("ParkingSlot", back_populates="lot")
    reservations = relationship("Reservation", back_populates="lot")
    sessions = relationship("ParkingSession", back_populates="lot")


class ParkingSlot(Base):
    __tablename__ = "parking_slots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id"), nullable=False)
    slot_code = Column(String, unique=True, nullable=False, index=True)
    slot_type = Column(Enum(SlotType), nullable=False, default=SlotType.REGULAR)
    current_status = Column(Enum(SlotStatus), nullable=False, default=SlotStatus.AVAILABLE)
    is_active = Column(Boolean, nullable=False, default=True)
    
    lot = relationship("ParkingLot", back_populates="slots")
    sessions = relationship("ParkingSession", back_populates="slot")
    events = relationship("SensorEvent", back_populates="slot")


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    vehicle_plate = Column(String, nullable=False)
    slot_type = Column(Enum(SlotType), nullable=False, default=SlotType.REGULAR)
    eta_window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    eta_window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(ReservationStatus), nullable=False, default=ReservationStatus.CONFIRMED)
    qr_token = Column(String, unique=True, nullable=False, index=True)
    
    lot = relationship("ParkingLot", back_populates="reservations")
    sessions = relationship("ParkingSession", back_populates="reservation")
    
    __table_args__ = (
        Index("ix_reservations_status_time", "status", "eta_window_start", "eta_window_end"),
    )


class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("reservations.id"), nullable=True)
    slot_id = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=True)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id"), nullable=False)
    vehicle_plate = Column(String, nullable=False, index=True)
    check_in_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    check_out_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    total_amount = Column(Float, nullable=True)
    
    reservation = relationship("Reservation", back_populates="sessions")
    slot = relationship("ParkingSlot", back_populates="sessions")
    lot = relationship("ParkingLot", back_populates="sessions")
    payment = relationship("Payment", back_populates="session", uselist=False)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("parking_sessions.id"), nullable=False, unique=True)
    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    session = relationship("ParkingSession", back_populates="payment")


class SensorEvent(Base):
    __tablename__ = "sensor_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slot_id = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=False, index=True)
    distance_cm = Column(Float, nullable=False)
    detected_state = Column(Enum(SlotStatus), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    slot = relationship("ParkingSlot", back_populates="events")
