"""Memory API schemas."""

from pydantic import BaseModel, Field


class MemoryFactCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(default="general", max_length=64)
    source_agent: str = Field(default="", max_length=128)


class SnapshotCreate(BaseModel):
    note: str = Field(default="", max_length=512)
