from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.db import SessionLocal
from datetime import date, datetime
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from typing import Optional

def compute_age(dob: Optional[date]) -> Optional[int]:
    if dob is None:
        return None
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years
from app import models
from app.schemas import (
    SetNannyAreasRequest,
    CreateNannyProfileRequest,
    UpdateNannyProfileRequest,
    SetParentAreaRequest,
    BookingSlot,
    BulkBookingRequest,
)

router = APIRouter()

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
def create_nanny_profile(nanny_id: int, payload: Optional[CreateNannyProfileRequest] = None, db: Session = Depends(get_db)):
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

@router.get("/nannies/search")
def search_nannies(parent_user_id: int, db: Session = Depends(get_db)):
    parent = db.query(models.ParentProfile).filter_by(user_id=parent_user_id).first()
    if not parent:
        raise HTTPException(status_code=400, detail="Parent area not set")
    rows = (
        db.query(models.NannyArea.nanny_id)
        .filter_by(area_id=parent.area_id)
        .distinct()
        .all()
    )
    nanny_ids = [r[0] for r in rows]
    if not nanny_ids:
        return []
    results = (
        db.query(models.Nanny, models.User)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .filter(models.Nanny.id.in_(nanny_ids))
        .all()
    )
    profiles = (
        db.query(models.NannyProfile)
        .filter(models.NannyProfile.nanny_id.in_(nanny_ids))
        .all()
    )
    profile_by_nanny_id = {p.nanny_id: p for p in profiles}
    def simple_list(items):
        return [{"id": x.id, "name": x.name} for x in (items or [])]
    response = []
    for nanny, user in results:
        p = profile_by_nanny_id.get(nanny.id)
        response.append(
            {
                "nanny_id": nanny.id,
                "approved": nanny.approved,
                "user_id": user.id,
                "name": user.name,
                "nickname": user.nickname,
                "last_initial": user.last_initial,
                "profile_photo_url": user.profile_photo_url,
                "bio": getattr(p, "bio", None),
                "date_of_birth": getattr(p, "date_of_birth", None),
                "age": compute_age(getattr(p, "date_of_birth", None)),
                "nationality": getattr(p, "nationality", None),
                "ethnicity": getattr(p, "ethnicity", None),
                "qualifications": simple_list(getattr(p, "qualifications", None)),
                "tags": simple_list(getattr(p, "tags", None)),
                "languages": simple_list(getattr(p, "languages", None)),
            }
        )
    return response


# Public endpoints only: set_nanny_areas, create_nanny_profile, update_nanny_profile, set_parent_area, search_nannies, create_bulk_booking_request, home
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
        day = slot.starts_at.date()
        start_t = slot.starts_at.time()
        end_t = slot.ends_at.time()
        avails = db.query(models.NannyAvailability).filter_by(
            nanny_id=payload.nanny_id,
            date=day,
            is_available=True,
        ).all()
        covered = any(a.start_time <= start_t and a.end_time >= end_t for a in avails)
        if not covered:
            errors.append({"index": i, "error": "nanny not available for this time window"})
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

