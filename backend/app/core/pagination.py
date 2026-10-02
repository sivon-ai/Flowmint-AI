"""
Pagination utilities for list endpoints.
"""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginationMeta(BaseModel):
    """Pagination metadata returned in API responses."""
    page: int
    per_page: int
    total: int
    total_pages: int

    @classmethod
    def from_params(cls, params: PaginationParams, total: int) -> "PaginationMeta":
        total_pages = max(1, (total + params.per_page - 1) // params.per_page)
        return cls(
            page=params.page,
            per_page=params.per_page,
            total=total,
            total_pages=total_pages,
        )
