


from datetime import date, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models
from app.config import ADMIN_API_KEY

def require_admin(x_admin_key: str = Header(default=None), admin_key: str = None):
	key = x_admin_key or admin_key
	if key != ADMIN_API_KEY:
		raise HTTPException(status_code=401, detail="Invalid or missing admin key")

router = APIRouter(prefix="/admin", tags=["admin"])


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()

@router.post("/availability", dependencies=[Depends(require_admin)])
def set_availability(
	nanny_id: int = Query(...),
	day: date = Query(...),
	start_time: time = Query(time(0, 0)),
	end_time: time = Query(time(23, 59)),
	is_available: bool = Query(True),
	notes: Optional[str] = Query(None),
	db: Session = Depends(get_db),
):
	if start_time >= end_time:
		raise HTTPException(status_code=400, detail="start_time must be before end_time")
	# Overlap check
	existing_slots = db.query(models.NannyAvailability).filter_by(
		nanny_id=nanny_id,
		date=day
	).all()
	for slot in existing_slots:
		if (slot.start_time < end_time) and (start_time < slot.end_time):
			raise HTTPException(status_code=409, detail="Availability overlaps an existing slot")
	row = db.query(models.NannyAvailability).filter_by(
		nanny_id=nanny_id,
		date=day,
		start_time=start_time,
		end_time=end_time,
	).first()
	if row:
		row.is_available = is_available
		row.notes = notes
	else:
		row = models.NannyAvailability(
			nanny_id=nanny_id,
			date=day,
			start_time=start_time,
			end_time=end_time,
			is_available=is_available,
			notes=notes,
			created_by="admin",
		)
		db.add(row)
	db.commit()
	db.refresh(row)
	return row

@router.get("/availability", dependencies=[Depends(require_admin)])
def list_availability(
	nanny_id: int = Query(...),
	day: Optional[date] = Query(None),
	db: Session = Depends(get_db),
):
	q = db.query(models.NannyAvailability).filter_by(nanny_id=nanny_id)
	if day:
		q = q.filter_by(date=day)
	return q.all()


@router.post("/reviews/{review_id}/approve", dependencies=[Depends(require_admin)])
def approve_review(review_id: int, db: Session = Depends(get_db)):
	review = db.query(models.Review).filter_by(id=review_id).first()
	if not review:
		raise HTTPException(status_code=404, detail="Review not found")
	if not review.approved:
		review.approved = True
		db.commit()
		db.refresh(review)
	# If already approved, do not update or error, just return 200 with review
	return review


@router.get("/reviews", dependencies=[Depends(require_admin)])
def list_reviews(approved: bool = Query(False), db: Session = Depends(get_db)):
	return db.query(models.Review).filter_by(approved=approved).order_by(models.Review.created_at.desc()).all()
