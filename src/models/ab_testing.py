from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid

class Base(DeclarativeBase):
    pass

class ABTest(Base):
    __tablename__ = "ab_tests"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    email_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship to variations
    variations = relationship("TestVariation", back_populates="ab_test")

class TestVariation(Base):
    __tablename__ = "test_variations"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ab_test_id: Mapped[str] = mapped_column(String(64), ForeignKey("ab_tests.id"))
    subject_line: Mapped[str] = mapped_column(String(255), nullable=False)
    variation_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-4
    
    # Multi-armed bandit metrics
    times_selected: Mapped[int] = mapped_column(Integer, default=0)
    times_sent: Mapped[int] = mapped_column(Integer, default=0)
    opens: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationship back to test
    ab_test = relationship("ABTest", back_populates="variations")

class EmailEvent(Base):
    __tablename__ = "email_events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variation_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_variations.id"))
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sent', 'opened', 'clicked'
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)