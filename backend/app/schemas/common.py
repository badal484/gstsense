from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard success envelope returned by every endpoint."""

    status: str = "success"
    data: Optional[T] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all exception handlers."""

    status: str = "error"
    error: ErrorDetail
    request_id: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    status: str = "success"
    data: list[T]
    meta: PaginationMeta


def make_response(data: T) -> ApiResponse[T]:
    """Wrap data in the standard success envelope."""
    return ApiResponse(status="success", data=data)


def make_error(
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Build the standard error envelope."""
    return ErrorResponse(
        status="error",
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id,
    )
