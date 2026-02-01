
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    stars: int
    comment: Optional[str] = None
    created_at: datetime


# ...existing code...

class NannyReviewsResponse(BaseModel):
    nanny_id: int
    average_rating_12m: Optional[float] = None
    review_count_12m: int = 0
    reviews: List['ReviewOut']


from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, conint, field_validator
from enum import Enum


# Schema for /nannies/search result
class NannySearchResult(BaseModel):
    nanny_id: int
    approved: bool
    user_id: int
    name: str
    nickname: Optional[str] = None
    last_initial: Optional[str] = None
    profile_photo_url: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    qualifications: Optional[List[dict]] = None
    tags: Optional[List[dict]] = None
    languages: Optional[List[dict]] = None
    average_rating_12m: Optional[float] = None
    review_count_12m: int = 0
    distance_km: Optional[float] = None

class SearchNanniesResponse(BaseModel):
    results: List[NannySearchResult] = []
    code: Optional[str] = None
    message: Optional[str] = None

class BookingSlot(BaseModel):
    starts_at: datetime
    ends_at: datetime

class BulkBookingRequest(BaseModel):
    parent_user_id: int
    nanny_id: int
    slots: List[BookingSlot] = Field(min_items=1)
    client_notes: Optional[str] = None

class UpdateNannyProfileRequest(BaseModel):
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    qualification_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None
    language_ids: Optional[List[int]] = None

class SetNannyAreasRequest(BaseModel):
    area_ids: List[int]

class CreateNannyProfileRequest(BaseModel):
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None

class SetParentAreaRequest(BaseModel):
    user_id: int
    area_id: int


class SetParentDefaultLocationRequest(BaseModel):
    user_id: int
    lat: float
    lng: float
    confirm_version: str = "v1"


class SetLocationRequest(BaseModel):
    lat: float
    lng: float


class SetLocationResponse(BaseModel):
    user_id: int
    lat: float
    lng: float


class ParentLocationResponse(BaseModel):
    user_id: int
    lat: float
    lng: float


class NannyLocationResponse(BaseModel):
    nanny_id: int
    lat: float
    lng: float


class LocationMode(str, Enum):
    default = "default"
    current = "current"


class BookingCreateRequest(BaseModel):
    parent_user_id: int
    nanny_id: int
    starts_at: datetime
    ends_at: datetime
    location_mode: LocationMode = LocationMode.default
    location_label: str = Field(min_length=1, max_length=30)
    lat: Optional[float] = None
    lng: Optional[float] = None

    @field_validator("location_label")
    @classmethod
    def validate_location_label(cls, v: str) -> str:
        label = v.strip()
        if not label:
            raise ValueError("location_label is required")
        return label


class BookingOut(BaseModel):
    booking_id: int
    parent_user_id: int
    nanny_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    location_mode: Optional[str] = None
    location_label: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    results: List[BookingOut] = []


class BookingStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class BookingStatusUpdateRequest(BaseModel):
    status: BookingStatus


class ReviewCreate(BaseModel):
    booking_id: int
    stars: int
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    booking_id: int
    parent_user_id: int
    nanny_id: int
    stars: int
    comment: Optional[str] = None
    approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


