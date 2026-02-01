
import math
from typing import Optional, List
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, text, distinct
from app.db import SessionLocal
from app import models, schemas
from app.schemas import NannyReviewsResponse, SetParentAreaRequest, SetParentDefaultLocationRequest, ParentLocationResponse, NannyLocationResponse, ReviewOut, ReviewCreate, SetNannyAreasRequest, CreateNannyProfileRequest, UpdateNannyProfileRequest, BulkBookingRequest, SearchNanniesResponse
from app.utils.email import send_email, get_admin_emails

router = APIRouter()

def get_rating_12m_for_nanny(db: Session, nanny_id: int):
    """
    Returns (average_rating_12m, review_count_12m) for a nanny over the last 12 months, using only approved reviews.
    """
    window_start = datetime.utcnow() - timedelta(days=365)
    q = (
        db.query(
            func.avg(models.Review.stars).label("avg_stars"),
            func.count(models.Review.id).label("count")
        )
        .filter(
            models.Review.nanny_id == nanny_id,
            models.Review.approved == True,
            models.Review.created_at >= window_start
        )
    )
    result = q.one()
    avg = float(result.avg_stars) if result.avg_stars is not None else None
    count = int(result.count)
    return avg, count

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _fmt_booking_lines(b):
    return "\n".join(
        [
            f"Booking ID: {b.id}",
            f"Parent user_id: {b.client_user_id}",
            f"Nanny ID: {b.nanny_id}",
            f"Starts: {b.starts_at}",
            f"Ends: {b.ends_at}",
            f"Status: {b.status}",
            f"Location mode: {getattr(b, 'location_mode', None)}",
            f"Location label: {getattr(b, 'location_label', None)}",
            f"Lat: {getattr(b, 'lat', None)}",
            f"Lng: {getattr(b, 'lng', None)}",
        ]
    )


def _safe_send(to_email: str, subject: str, body: str):
    try:
        if to_email:
            send_email(to_email, subject, body)
    except Exception as e:
        print(f"email failed to={to_email} subject={subject} err={e}")


def notify_booking_created(db, booking):
    parent = db.query(models.User).filter(models.User.id == booking.client_user_id).first()
    nanny = (
        db.query(models.Nanny)
        .filter(models.Nanny.id == booking.nanny_id)
        .first()
    )
    nanny_user = None
    if nanny:
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()

    subject_nanny = "New booking request"
    subject_parent = "Booking submitted"
    subject_admin = "Booking pending"

    body_common = _fmt_booking_lines(booking)

    if nanny_user and nanny_user.email:
        _safe_send(
            nanny_user.email,
            subject_nanny,
            "A new booking request is pending.\n\n" + body_common,
        )

    if parent and parent.email:
        _safe_send(
            parent.email,
            subject_parent,
            "Your booking has been submitted and is pending.\n"
            "You will be billed based on the location you confirmed.\n\n"
            + body_common,
        )

    for admin_email in get_admin_emails():
        _safe_send(
            admin_email,
            subject_admin,
            "A booking is pending.\n\n" + body_common,
        )


@router.get("/qualifications")
def list_qualifications(db: Session = Depends(get_db)):
    rows = db.query(models.Qualification).order_by(models.Qualification.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/nanny-tags")
def list_nanny_tags(db: Session = Depends(get_db)):
    rows = db.query(models.NannyTag).order_by(models.NannyTag.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/languages")
def list_languages(db: Session = Depends(get_db)):
    rows = db.query(models.Language).order_by(models.Language.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    # auth enabled if any route starts with /auth
    auth_enabled = any(getattr(r, "path", "").startswith("/auth") for r in request.app.routes)

    # db ping
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # basic counts
    counts = {
        "users": db.query(models.User).count(),
        "nannies": db.query(models.NannyProfile).count(),
        "reviews": db.query(models.Review).count(),
    }

    return {
        "ok": bool(db_ok),
        "auth_enabled": auth_enabled,
        "db_ok": db_ok,
        "counts": counts,
    }


# ...existing code...

from datetime import datetime, timedelta

@router.get("/nannies/{nanny_id}/reviews", response_model=NannyReviewsResponse)
def get_nanny_reviews(nanny_id: int, db: Session = Depends(get_db)):
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    window_start = datetime.utcnow() - timedelta(days=365)
    reviews_query = (
        db.query(models.Review)
        .filter(
            models.Review.nanny_id == nanny_id,
            models.Review.approved == True,
            models.Review.created_at >= window_start
        )
        .order_by(models.Review.created_at.desc())
    )
    reviews = reviews_query.all()

    review_count_12m = len(reviews)
    if review_count_12m == 0:
        average_rating_12m = None
    else:
        average_rating_12m = float(sum(r.stars for r in reviews) / review_count_12m)

    return {
        "nanny_id": nanny_id,
        "average_rating_12m": average_rating_12m,
        "review_count_12m": review_count_12m,
        "reviews": [ReviewOut.model_validate(r, from_attributes=True) for r in reviews],
    }

def compute_age(dob: Optional[date]) -> Optional[int]:
    if dob is None:
        return None
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years

# /nannies/search route must be defined immediately after router = APIRouter()
@router.get("/nannies/search", response_model=SearchNanniesResponse)
def search_nannies(
    parent_user_id: int,
    max_distance_km: Optional[float] = Query(default=None),
    min_rating: Optional[float] = Query(default=None),
    tag_ids: Optional[List[int]] = Query(default=None),
    qualification_ids: Optional[List[int]] = Query(default=None),
    language_ids: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
):

    parent = (
        db.query(models.ParentProfile)
        .filter(models.ParentProfile.user_id == parent_user_id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404, detail="Parent profile not found")

    if parent.lat is None or parent.lng is None:
        return {
            "results": [],
            "code": "PARENT_LOCATION_REQUIRED",
            "message": "Set your default location first",
        }

    parent_area_id = parent.area_id
    parent_lat = getattr(parent, "lat", None)
    parent_lng = getattr(parent, "lng", None)

    q = (
        db.query(models.NannyProfile)
        .join(models.NannyArea, models.NannyArea.nanny_id == models.NannyProfile.nanny_id)
        .filter(models.NannyArea.area_id == parent_area_id)
    )

    if qualification_ids:
        q = (
            q.join(models.nanny_profile_qualifications)
             .filter(models.nanny_profile_qualifications.c.qualification_id.in_(qualification_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_qualifications.c.qualification_id))
                 == len(set(qualification_ids))
             )
        )

    if tag_ids:
        q = (
            q.join(models.nanny_profile_tags)
             .filter(models.nanny_profile_tags.c.tag_id.in_(tag_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_tags.c.tag_id))
                 == len(set(tag_ids))
             )
        )

    if language_ids:
        q = (
            q.join(models.nanny_profile_languages)
             .filter(models.nanny_profile_languages.c.language_id.in_(language_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_languages.c.language_id))
                 == len(set(language_ids))
             )
        )

    profiles = q.all()

    def simple_list(items):
        return [{"id": x.id, "name": x.name} for x in (items or [])]

    results = []
    for p in profiles:
        nanny = db.query(models.Nanny).filter(models.Nanny.id == p.nanny_id).first()
        if not nanny:
            continue
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        if not nanny_user:
            continue

        avg, cnt = get_rating_12m_for_nanny(db, p.nanny_id)
        distance_km = None
        if parent.lat is not None and parent.lng is not None and p.lat is not None and p.lng is not None:
            distance_km = round(haversine_km(parent.lat, parent.lng, p.lat, p.lng), 2)

        if min_rating is not None:
            if avg is None or avg < min_rating:
                continue

        if max_distance_km is not None:
            if distance_km is None or distance_km > max_distance_km:
                continue

        results.append(
            {
                "nanny_id": p.nanny_id,
                "approved": nanny.approved,
                "user_id": nanny_user.id,
                "name": nanny_user.name,
                "nickname": getattr(nanny_user, "nickname", None),
                "last_initial": getattr(nanny_user, "last_initial", None),
                "profile_photo_url": getattr(nanny_user, "profile_photo_url", None),
                "bio": getattr(p, "bio", None),
                "date_of_birth": getattr(p, "date_of_birth", None),
                "age": compute_age(getattr(p, "date_of_birth", None)),
                "nationality": getattr(p, "nationality", None),
                "ethnicity": getattr(p, "ethnicity", None),
                "qualifications": simple_list(getattr(p, "qualifications", None)),
                "tags": simple_list(getattr(p, "tags", None)),
                "languages": simple_list(getattr(p, "languages", None)),
                "average_rating_12m": avg,
                "review_count_12m": cnt or 0,
                "distance_km": distance_km,
            }
        )

    def sort_key(x: dict):
        dist = x.get("distance_km")
        rating = x.get("average_rating_12m")
        rc = x.get("review_count_12m")

        # distance: nulls last
        dist_is_null = dist is None
        dist_val = dist if dist is not None else 10**9

        # rating: nulls last, higher first
        rating_is_null = rating is None
        rating_val = rating if rating is not None else -1

        # review_count: higher first, null treated as 0
        rc_val = rc if rc is not None else 0

        return (
            dist_is_null,
            dist_val,
            rating_is_null,
            -rating_val,
            -rc_val,
            x.get("nanny_id", 0),
        )

    results.sort(key=sort_key)

    return {"results": results, "code": None, "message": None}


@router.post("/parents/default-location")
def set_parent_default_location(payload: SetParentDefaultLocationRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(models.ParentProfile).filter_by(user_id=payload.user_id).first()
    if not existing:
        existing = models.ParentProfile(user_id=payload.user_id)
        db.add(existing)
    existing.lat = payload.lat
    existing.lng = payload.lng
    existing.location_confirmed_at = datetime.utcnow().isoformat()
    existing.location_confirm_version = payload.confirm_version
    db.commit()
    return {"ok": True}


@router.get("/parents/location-status")
def get_parent_location_status(user_id: int, db: Session = Depends(get_db)):
    parent = db.query(models.ParentProfile).filter_by(user_id=user_id).first()
    lat = getattr(parent, "lat", None) if parent else None
    lng = getattr(parent, "lng", None) if parent else None
    return {
        "has_default_location": lat is not None and lng is not None,
        "lat": lat,
        "lng": lng,
    }


@router.patch("/parents/{user_id}/location", response_model=schemas.SetLocationResponse)
def set_parent_location(user_id: int, payload: schemas.SetLocationRequest, db: Session = Depends(get_db)):
    parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user_id).first()
    if not parent:
        raise HTTPException(status_code=400, detail="Parent area not set")
    if parent.area_id is None:
        raise HTTPException(status_code=400, detail="Parent area not set")
    parent.lat = payload.lat
    parent.lng = payload.lng
    db.commit()
    db.refresh(parent)
    return {"user_id": parent.user_id, "lat": parent.lat, "lng": parent.lng}


@router.patch("/nannies/{nanny_id}/location", response_model=NannyLocationResponse)
def set_nanny_location(nanny_id: int, payload: schemas.SetLocationRequest, db: Session = Depends(get_db)):
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    profile.lat = payload.lat
    profile.lng = payload.lng
    db.commit()
    db.refresh(profile)
    return {"nanny_id": profile.nanny_id, "lat": profile.lat, "lng": profile.lng}

@router.post("/parents/area")
def set_parent_area(payload: SetParentAreaRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(models.ParentProfile).filter_by(user_id=payload.user_id).first()
    if existing:
        existing.area_id = payload.area_id
    else:
        db.add(models.ParentProfile(user_id=payload.user_id, area_id=payload.area_id))
    db.commit()
    return {"user_id": payload.user_id, "area_id": payload.area_id}

@router.post("/reviews", response_model=ReviewOut)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter_by(id=payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Booking is not completed")

    existing = db.query(models.Review).filter_by(booking_id=payload.booking_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Review already exists for this booking")

    review = models.Review(
        booking_id=payload.booking_id,
        parent_user_id=booking.client_user_id,
        nanny_id=booking.nanny_id,
        stars=payload.stars,
        comment=payload.comment,
        approved=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@router.post("/nannies/{nanny_id}/areas")
def set_nanny_areas(nanny_id: int, payload: SetNannyAreasRequest, db: Session = Depends(get_db)):
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    db.query(models.NannyArea).filter_by(nanny_id=nanny_id).delete()
    for area_id in payload.area_ids:
        db.add(models.NannyArea(nanny_id=nanny_id, area_id=area_id))
    db.commit()
    return {"nanny_id": nanny_id, "area_ids": payload.area_ids}

@router.post("/nanny-profiles")
def create_nanny_profile(
    nanny_id: int,
    payload: Optional[CreateNannyProfileRequest] = None,
    db: Session = Depends(get_db),
):
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    existing = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if existing:
        return {
            "id": existing.id,
            "nanny_id": existing.nanny_id,
            "bio": existing.bio,
            "date_of_birth": existing.date_of_birth,
            "age": compute_age(existing.date_of_birth),
            "nationality": existing.nationality,
            "ethnicity": existing.ethnicity,
            "qualifications": [{"id": q.id, "name": q.name} for q in existing.qualifications],
            "tags": [{"id": t.id, "name": t.name} for t in existing.tags],
            "languages": [{"id": l.id, "name": l.name} for l in existing.languages],
        }
    if payload is None:
        payload = CreateNannyProfileRequest()
    profile = models.NannyProfile(
        nanny_id=nanny_id,
        bio=payload.bio.strip() if payload.bio else None,
        date_of_birth=payload.date_of_birth,
        nationality=payload.nationality.strip() if payload.nationality else None,
        ethnicity=payload.ethnicity.strip() if payload.ethnicity else None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "id": profile.id,
        "nanny_id": profile.nanny_id,
        "bio": profile.bio,
        "date_of_birth": profile.date_of_birth,
        "age": compute_age(profile.date_of_birth),
        "nationality": profile.nationality,
        "ethnicity": profile.ethnicity,
        "qualifications": [],
        "tags": [],
        "languages": [],
    }

@router.put("/nanny-profiles/{nanny_id}")
def update_nanny_profile(nanny_id: int, payload: UpdateNannyProfileRequest, db: Session = Depends(get_db)):
    profile = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    if payload.bio is not None:
        profile.bio = payload.bio.strip() if payload.bio else None
    if payload.date_of_birth is not None:
        profile.date_of_birth = payload.date_of_birth
    if payload.nationality is not None:
        profile.nationality = payload.nationality.strip() if payload.nationality else None
    if payload.ethnicity is not None:
        profile.ethnicity = payload.ethnicity.strip() if payload.ethnicity else None
    if payload.qualification_ids is not None:
        profile.qualifications = (
            db.query(models.Qualification)
            .filter(models.Qualification.id.in_(payload.qualification_ids))
            .all()
        )
    if payload.tag_ids is not None:
        profile.tags = (
            db.query(models.NannyTag)
            .filter(models.NannyTag.id.in_(payload.tag_ids))
            .all()
        )
    if payload.language_ids is not None:
        profile.languages = (
            db.query(models.Language)
            .filter(models.Language.id.in_(payload.language_ids))
            .all()
        )
    db.commit()
    return {"ok": True, "nanny_id": nanny_id}


@router.post("/bookings", response_model=schemas.BookingOut)
def create_booking(payload: schemas.BookingCreateRequest, db: Session = Depends(get_db)):
    lat = payload.lat
    lng = payload.lng
    location_label = payload.location_label.strip() if payload.location_label is not None else None
    if not location_label:
        raise HTTPException(status_code=400, detail="location_label is required")

    if payload.location_mode == schemas.LocationMode.default:
        parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == payload.parent_user_id).first()
        if not parent or parent.lat is None or parent.lng is None:
            raise HTTPException(status_code=400, detail="Parent default location not set")
        lat = parent.lat
        lng = parent.lng
    else:
        if lat is None or lng is None:
            raise HTTPException(status_code=400, detail="Current location requires lat and lng")

    booking = models.Booking(
        nanny_id=payload.nanny_id,
        client_user_id=payload.parent_user_id,
        day=payload.starts_at.date(),
        status="pending",
        price_cents=0,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        lat=lat,
        lng=lng,
        location_mode=payload.location_mode.value,
        location_label=location_label,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    notify_booking_created(db, booking)

    return {
        "booking_id": booking.id,
        "parent_user_id": booking.client_user_id,
        "nanny_id": booking.nanny_id,
        "starts_at": booking.starts_at,
        "ends_at": booking.ends_at,
        "status": booking.status,
        "location_mode": booking.location_mode,
        "location_label": booking.location_label,
        "lat": booking.lat,
        "lng": booking.lng,
    }


_ALLOWED = {
    schemas.BookingStatus.pending: {schemas.BookingStatus.accepted, schemas.BookingStatus.rejected},
    schemas.BookingStatus.accepted: {schemas.BookingStatus.completed, schemas.BookingStatus.cancelled},
    schemas.BookingStatus.rejected: set(),
    schemas.BookingStatus.cancelled: set(),
    schemas.BookingStatus.completed: set(),
}


@router.patch("/bookings/{booking_id}/status")
def update_booking_status(booking_id: int, payload: schemas.BookingStatusUpdateRequest, db: Session = Depends(get_db)):
    b = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    current = schemas.BookingStatus(b.status)
    target = payload.status

    if current == schemas.BookingStatus.pending and target == schemas.BookingStatus.accepted:
        if b.starts_at is None or b.ends_at is None:
            raise HTTPException(status_code=400, detail="Booking time window is missing")
        overlap = (
            db.query(models.Booking.id)
            .filter(
                models.Booking.nanny_id == b.nanny_id,
                models.Booking.status == schemas.BookingStatus.accepted.value,
                models.Booking.id != b.id,
                models.Booking.starts_at < b.ends_at,
                models.Booking.ends_at > b.starts_at,
            )
            .first()
        )
        if overlap:
            raise HTTPException(
                status_code=409,
                detail="Nanny already has an accepted booking that overlaps this time window",
            )

    if target not in _ALLOWED[current]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current.value} -> {target.value}"
        )

    b.status = target.value
    db.commit()
    db.refresh(b)

    return {
        "booking_id": b.id,
        "status": b.status
    }


@router.get("/parents/{user_id}/bookings", response_model=schemas.BookingListResponse)
def list_parent_bookings(
    user_id: int,
    status: Optional[schemas.BookingStatus] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    nanny_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Booking).filter(models.Booking.client_user_id == user_id)

    if status is not None:
        q = q.filter(models.Booking.status == status.value)
    if nanny_id is not None:
        q = q.filter(models.Booking.nanny_id == nanny_id)
    if from_ is not None:
        q = q.filter(models.Booking.ends_at >= from_)
    if to is not None:
        q = q.filter(models.Booking.starts_at <= to)

    rows = q.order_by(models.Booking.starts_at.desc()).all()

    return {
        "results": [
            {
                "booking_id": b.id,
                "parent_user_id": b.client_user_id,
                "nanny_id": b.nanny_id,
                "starts_at": b.starts_at,
                "ends_at": b.ends_at,
                "status": b.status,
                "lat": b.lat,
                "lng": b.lng,
            }
            for b in rows
        ]
    }


@router.get("/nannies/{nanny_id}/bookings", response_model=schemas.BookingListResponse)
def list_nanny_bookings(
    nanny_id: int,
    status: Optional[schemas.BookingStatus] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    parent_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Booking).filter(models.Booking.nanny_id == nanny_id)

    if status is not None:
        q = q.filter(models.Booking.status == status.value)
    if parent_user_id is not None:
        q = q.filter(models.Booking.client_user_id == parent_user_id)
    if from_ is not None:
        q = q.filter(models.Booking.ends_at >= from_)
    if to is not None:
        q = q.filter(models.Booking.starts_at <= to)

    rows = q.order_by(models.Booking.starts_at.desc()).all()

    return {
        "results": [
            {
                "booking_id": b.id,
                "parent_user_id": b.client_user_id,
                "nanny_id": b.nanny_id,
                "starts_at": b.starts_at,
                "ends_at": b.ends_at,
                "status": b.status,
                "lat": b.lat,
                "lng": b.lng,
            }
            for b in rows
        ]
    }

@router.post("/bookings/bulk")
def create_bulk_booking_request(payload: BulkBookingRequest, db: Session = Depends(get_db)):
    created_slots = []
    errors = []
    req = models.BookingRequest(
        parent_user_id=payload.parent_user_id,
        nanny_id=payload.nanny_id,
        status="pending",
        payment_status="pending_payment",
        client_notes=payload.client_notes,
    )
    db.add(req)
    db.flush()
    for i, slot in enumerate(payload.slots):
        if slot.ends_at <= slot.starts_at:
            errors.append({"index": i, "error": "ends_at must be after starts_at"})
            continue
        existing = (
            db.query(models.BookingRequestSlot)
            .join(models.BookingRequest)
            .filter(
                models.BookingRequest.nanny_id == payload.nanny_id,
                models.BookingRequest.status.in_(["pending", "approved", "completed"]),
                models.BookingRequestSlot.starts_at < slot.ends_at,
                slot.starts_at < models.BookingRequestSlot.ends_at,
            )
            .first()
        )
        if existing:
            errors.append({"index": i, "error": "overlaps an existing booking or hold"})
            continue
        s = models.BookingRequestSlot(
            booking_request_id=req.id,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        )
        db.add(s)
        db.flush()
        created_slots.append({"id": s.id, "starts_at": s.starts_at, "ends_at": s.ends_at})
    req.status = "approved" if created_slots else "declined"
    if created_slots:
        req.payment_status = "paid"
    db.commit()
    return {
        "booking_request_id": req.id,
        "status": req.status,
        "payment_status": getattr(req, "payment_status", None),
        "created_slots": created_slots,
        "errors": errors,
    }
