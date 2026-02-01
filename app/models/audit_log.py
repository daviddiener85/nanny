from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    action = Column(String, nullable=False)          # example: "update_nanny_profile"
    entity_type = Column(String, nullable=False)     # example: "NannyProfile"
    entity_id = Column(Integer, nullable=True)       # example: nanny_id
    details = Column(Text, nullable=True)            # free text or JSON string

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    actor = relationship("User")