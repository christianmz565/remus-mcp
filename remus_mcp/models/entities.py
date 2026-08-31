"""Pydantic models per entity."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class RemEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    oid: int
    name: Optional[str] = None
    description: Optional[str] = None
    comments: Optional[str] = None
    versionMajor: Optional[int] = None
    versionMinor: Optional[int] = None
    versionDate: Optional[datetime] = None
    number: Optional[int] = None
    document: Optional[int] = None
    parent: Optional[int] = None
    order: Optional[int] = None

    def to_row(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "RemEntity":
        # Normalize keys: lower? Jet uses oid, name etc.
        return cls(**row)

# Specific subclasses for validation convenience
class TraceEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    oid: int
    source: Optional[int] = None
    target: Optional[int] = None
    isChecked: Optional[bool] = None
