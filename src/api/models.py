from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class GenerateRequest(BaseModel):
    email_content: str = Field(..., min_length=10, max_length=10000, description="The email content to generate subjects for")
    original_subject: Optional[str] = Field(None, max_length=255, description="Optional original subject line")
    
    @field_validator('email_content')
    @classmethod
    def validate_email_content(cls, v):
        if not v.strip():
            raise ValueError('Email content cannot be empty')
        return v.strip()

class SubjectVariation(BaseModel):
    id: str
    subject_line: str = Field(..., max_length=60)
    variation_index: int
    
class GenerateResponse(BaseModel):
    ab_test_id: str
    variations: List[SubjectVariation]
    cached: bool = False
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class TrackRequest(BaseModel):
    variation_id: str
    event_type: str = Field(..., pattern="^(sent|opened|clicked)$")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class TrackResponse(BaseModel):
    success: bool
    message: str

class AnalyticsResponse(BaseModel):
    test_id: str
    created_at: str
    original_subject: Optional[str]
    is_active: bool
    variations: List[Dict[str, Any]]

class TopPerformingSubject(BaseModel):
    subject_line: str
    click_rate: float
    open_rate: float
    times_sent: int
    test_created: str

class DashboardMetrics(BaseModel):
    total_tests: int
    active_tests: int
    total_emails_sent: int
    overall_click_rate: float
    tests_created_this_week: int

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database: str
    cache: str