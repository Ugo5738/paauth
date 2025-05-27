import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from auth_service.db import Base

class AppClient(Base):
    __tablename__ = "app_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_name = Column(String, unique=True, nullable=False, index=True)
    client_secret_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<AppClient(id='{self.id}', client_name='{self.client_name}')>"
