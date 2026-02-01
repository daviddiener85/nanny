
from sqlalchemy import (
	Column, BigInteger, Integer, String, Text, Boolean, ForeignKey, DateTime, Numeric,
	CheckConstraint, UniqueConstraint, Index, and_
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


from app.db import Base


class BookingRequest(Base):
	__tablename__ = "booking_requests"
	id = Column(BigInteger, primary_key=True)
	parent_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
	nanny_id = Column(BigInteger, ForeignKey("nannies.id", ondelete="RESTRICT"), nullable=False)
	status = Column(Text, nullable=False)
	hold_expires_at = Column(DateTime(timezone=True), nullable=True)
	payment_status = Column(Text, nullable=False, default="pending_payment")
	admin_notes = Column(Text)
	client_notes = Column(Text)
	created_by_admin_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
	__table_args__ = (
		CheckConstraint("status IN ('pending','approved','declined','cancelled','completed')", name="booking_requests_status_check"),
		CheckConstraint(
			"payment_status IN ('pending_payment','paid','cancelled')",
			name="booking_requests_payment_status_check",
		),
	)

class BookingRequestSlot(Base):
	__tablename__ = "booking_request_slots"
	id = Column(BigInteger, primary_key=True)
	booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id", ondelete="CASCADE"), nullable=False)
	starts_at = Column(DateTime(timezone=True), nullable=False)
	ends_at = Column(DateTime(timezone=True), nullable=False)
	__table_args__ = (
		CheckConstraint("ends_at > starts_at", name="booking_request_slots_time_check"),
		Index("brs_request_id_idx", "booking_request_id"),
		Index("brs_starts_at_idx", "starts_at"),
	)

class BookingPricingSnapshot(Base):
	__tablename__ = "booking_pricing_snapshot"
	booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id", ondelete="CASCADE"), primary_key=True)
	currency = Column(Text, nullable=False, default="ZAR")
	hourly_rate_cents = Column(Integer, nullable=False)
	fee_pct = Column(Numeric(5,4), nullable=False)
	total_minutes = Column(Integer, nullable=False)
	base_amount_cents = Column(Integer, nullable=False)
	fee_amount_cents = Column(Integer, nullable=False)
	total_amount_cents = Column(Integer, nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	__table_args__ = (
		CheckConstraint("hourly_rate_cents >= 0", name="bps_hourly_rate_check"),
		CheckConstraint("fee_pct >= 0 AND fee_pct <= 1", name="bps_fee_pct_check"),
		CheckConstraint("total_minutes >= 0", name="bps_total_minutes_check"),
		CheckConstraint("base_amount_cents >= 0", name="bps_base_amount_check"),
		CheckConstraint("fee_amount_cents >= 0", name="bps_fee_amount_check"),
		CheckConstraint("total_amount_cents >= 0", name="bps_total_amount_check"),
	)
