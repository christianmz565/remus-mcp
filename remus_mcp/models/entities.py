"""Pydantic models per entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RemEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    oid: int
    name: str | None = None
    description: str | None = None
    comments: str | None = None
    versionMajor: int | None = None
    versionMinor: int | None = None
    versionDate: datetime | None = None
    number: int | None = None
    document: int | None = None
    parent: int | None = None
    order: int | None = None

    def to_row(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> RemEntity:
        # Normalize keys: lower? Jet uses oid, name etc.
        return cls(**row)


# Specific subclasses for validation convenience
class TraceEntity(BaseModel):
    model_config = ConfigDict(extra="allow")
    oid: int
    source: int | None = None
    target: int | None = None
    isChecked: bool | None = None
