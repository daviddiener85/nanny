from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.deps import get_db, require_admin, compute_age
from app import models
from app.schemas import AdminUpdateUserRequest, AdminUpdateParentRequest, AdminUpdateNannyRequest, AdminUpdateNannyProfileRequest

router = APIRouter()

@router.get("/admin/parents")
def admin_list_parents(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    rows = (
        db.query(models.User, models.ParentProfile, models.Area)
        .outerjoin(models.ParentProfile, models.ParentProfile.user_id == models.User.id)
        .outerjoin(models.Area, models.Area.id == models.ParentProfile.area_id)
        .filter(models.User.role == "parent")
        .all()
    )
    out = []
    for user, parent, area in rows:
        out.append({
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "area_id": parent.area_id if parent else None,
            "area": {"id": area.id, "name": area.name} if area else None,
        })
    return out

@router.get("/admin/nannies")
def admin_list_nannies(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    rows = (
        db.query(models.Nanny, models.User, models.NannyProfile)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .outerjoin(models.NannyProfile, models.NannyProfile.nanny_id == models.Nanny.id)
        .all()
    )
    out = []
    for nanny, user, profile in rows:
        out.append({
            "nanny_id": nanny.id,
            "approved": nanny.approved,
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "nickname": user.nickname,
            "last_initial": user.last_initial,
            "profile_photo_url": user.profile_photo_url,
            "bio": getattr(profile, "bio", None),
            "date_of_birth": getattr(profile, "date_of_birth", None),
            "age": compute_age(getattr(profile, "date_of_birth", None)),
            "nationality": getattr(profile, "nationality", None),
            "ethnicity": getattr(profile, "ethnicity", None),
        })
    return out

@router.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUpdateUserRequest, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.email is not None:
        email = payload.email.lower().strip()
        existing = db.query(models.User).filter(models.User.email == email, models.User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = email
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        user.role = payload.role.strip()
    if payload.phone is not None:
        user.phone = payload.phone.strip() if payload.phone else None
    if payload.lat is not None:
        user.lat = payload.lat
    if payload.lng is not None:
        user.lng = payload.lng
    if payload.nickname is not None:
        user.nickname = payload.nickname.strip() if payload.nickname else None
    if payload.last_initial is not None:
        li = payload.last_initial.strip().upper() if payload.last_initial else None
        if li is not None and len(li) != 1:
            raise HTTPException(status_code=400, detail="last_initial must be 1 character")
        user.last_initial = li
    if payload.profile_photo_url is not None:
        user.profile_photo_url = payload.profile_photo_url.strip() if payload.profile_photo_url else None
    db.commit()
    db.refresh(user)
    return {"ok": True, "user_id": user.id}

@router.put("/admin/parents/{user_id}")
def admin_update_parent(user_id: int, payload: AdminUpdateParentRequest, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    parent = db.query(models.ParentProfile).filter_by(user_id=user_id).first()
    if not parent:
        parent = models.ParentProfile(user_id=user_id)
        db.add(parent)
        db.commit()
        db.refresh(parent)
    if payload.area_id is not None:
        parent.area_id = payload.area_id
    db.commit()
    return {"ok": True, "user_id": user_id}

@router.put("/admin/nannies/{nanny_id}")
def admin_update_nanny(nanny_id: int, payload: AdminUpdateNannyRequest, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    if payload.approved is not None:
        nanny.approved = payload.approved
    db.commit()
    return {"ok": True, "nanny_id": nanny_id}

@router.put("/admin/nanny-profiles/{nanny_id}")
def admin_update_nanny_profile(nanny_id: int, payload: AdminUpdateNannyProfileRequest, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    profile = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
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
