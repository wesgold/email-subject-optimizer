from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

# Custom UUID type that works with both PostgreSQL and SQLite
class UUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return value
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value

class Base(DeclarativeBase):
    pass

class ABTest(Base):
    __tablename__ = "ab_tests"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    email_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Test")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    variations = relationship("ABTestVariation", back_populates="ab_test", cascade="all, delete-orphan")
    events = relationship("ABTestEvent", back_populates="ab_test", cascade="all, delete-orphan")

class ABTestVariation(Base):
    __tablename__ = "ab_test_variations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    ab_test_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("ab_tests.id"))
    subject_line: Mapped[str] = mapped_column(String(255), nullable=False)
    variation_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-4
    
    # Multi-armed bandit metrics
    times_selected: Mapped[int] = mapped_column(Integer, default=0)
    times_sent: Mapped[int] = mapped_column(Integer, default=0)
    opens: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Calculated rates
    open_rate: Mapped[float] = mapped_column(Float, default=0.0)
    click_rate: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    ab_test = relationship("ABTest", back_populates="variations")
    events = relationship("ABTestEvent", back_populates="variation", cascade="all, delete-orphan")

class ABTestEvent(Base):
    __tablename__ = "ab_test_events"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    ab_test_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("ab_tests.id"))
    variation_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("ab_test_variations.id"))
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # send, open, click, conversion
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    ab_test = relationship("ABTest", back_populates="events")
    variation = relationship("ABTestVariation", back_populates="events")

# Keep legacy aliases for backward compatibility
TestVariation = ABTestVariation
EmailEvent = ABTestEvent