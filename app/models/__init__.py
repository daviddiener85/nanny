from .availability import NannyAvailability as Availability
from .availability import NannyAvailability
from .bookings import BookingRequest, BookingRequestSlot, BookingPricingSnapshot
from app.db import Base

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Date,
    Table,
    Text,
    Float,
    UniqueConstraint,
    DateTime,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.db import Base
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

# ---------------- USERS ----------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)

    phone = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    nickname = Column(String, nullable=True)
    last_initial = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)

    admin_profile = relationship("AdminProfile", back_populates="user", uselist=False)


# ---------------- CORE ENTITIES ----------------

class Nanny(Base):
    __tablename__ = "nannies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    approved = Column(Boolean, nullable=False, default=False)

    profile = relationship("NannyProfile", back_populates="nanny", uselist=False)





class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    client_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="pending")
    price_cents = Column(Integer, nullable=False)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_mode = Column(String, nullable=True)
    location_label = Column(String, nullable=True)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    stars = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("stars >= 1 AND stars <= 5", name="reviews_stars_check"),
        Index("reviews_nanny_id_idx", "nanny_id"),
        Index("reviews_parent_user_id_idx", "parent_user_id"),
        Index("reviews_approved_idx", "approved"),
        Index("reviews_created_at_idx", "created_at"),
    )


# ---------------- LOOKUP TABLES ----------------

class Qualification(Base):
    __tablename__ = "qualifications"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class NannyTag(Base):
    __tablename__ = "nanny_tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)


class NannyArea(Base):
    __tablename__ = "nanny_areas"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("nanny_id", "area_id", name="uq_nanny_area"),
    )


class ParentProfile(Base):
    __tablename__ = "parent_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_confirmed_at = Column(DateTime, nullable=True)
    location_confirm_version = Column(String, nullable=True)


# ---------------- MANY TO MANY ----------------

nanny_profile_qualifications = Table(
    "nanny_profile_qualifications",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("qualification_id", Integer, ForeignKey("qualifications.id"), primary_key=True),
)

nanny_profile_tags = Table(
    "nanny_profile_tags",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("nanny_tags.id"), primary_key=True),
)

nanny_profile_languages = Table(
    "nanny_profile_languages",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("language_id", Integer, ForeignKey("languages.id"), primary_key=True),
)


# ---------------- MAIN PROFILE ----------------

class NannyProfile(Base):
    __tablename__ = "nanny_profiles"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False, unique=True)

    bio = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)

    ethnicity = Column(String, nullable=True)

    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    nanny = relationship("Nanny", back_populates="profile")

    qualifications = relationship("Qualification", secondary=nanny_profile_qualifications)
    tags = relationship("NannyTag", secondary=nanny_profile_tags)
    languages = relationship("Language", secondary=nanny_profile_languages)


from app.models.admin_profile import AdminProfile
from app.models.audit_log import AuditLog
from . import availability