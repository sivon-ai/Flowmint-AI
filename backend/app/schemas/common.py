"""
Common response schemas used across all endpoints.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.pagination import PaginationMeta

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""
    success: bool = True
    data: T | None = None
    meta: PaginationMeta | None = None
    errors: list[ErrorDetail] | None = None

    @classmethod
    def ok(cls, data: Any, meta: PaginationMeta | None = None) -> "ApiResponse":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def error(cls, code: str, message: str, field: str | None = None) -> "ApiResponse":
        return cls(
            success=False,
            errors=[ErrorDetail(code=code, message=message, field=field)],
        )
