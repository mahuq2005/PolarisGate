from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Optional, Dict
import uuid, re

class TraceIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    completion: str = Field(..., max_length=10000)
    model_id: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    tags: Dict[str, str] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("model_id")
    @classmethod
    def validate_model_id_format(cls, v):
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("model_id must be alphanumeric with dashes/underscores")
        return v

class TraceOut(BaseModel):
    id: str
    status: str

class TraceRecord(TraceIn):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
