"""
Centralized exception hierarchy for the application.
All domain exceptions inherit from AppError for consistent error handling.
"""
from __future__ import annotations

from http import HTTPStatus
from typing import Any


class AppError(Exception):
    """Base application exception with HTTP status and structured detail."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


# ── Auth Exceptions ───────────────────────────────────────────────────────────
class AuthenticationError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication failed"


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired"


class TokenInvalidError(AuthenticationError):
    error_code = "TOKEN_INVALID"
    message = "Token is invalid"


class PermissionDeniedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action"


# ── Resource Exceptions ───────────────────────────────────────────────────────
class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Resource not found"


class DatasetNotFoundError(NotFoundError):
    error_code = "DATASET_NOT_FOUND"
    message = "Dataset not found"


class JobNotFoundError(NotFoundError):
    error_code = "JOB_NOT_FOUND"
    message = "Job not found"


class UserNotFoundError(NotFoundError):
    error_code = "USER_NOT_FOUND"
    message = "User not found"


# ── Conflict Exceptions ───────────────────────────────────────────────────────
class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "CONFLICT"
    message = "Resource already exists"


class DuplicateEmailError(ConflictError):
    error_code = "DUPLICATE_EMAIL"
    message = "Email address already registered"


# ── Validation Exceptions ─────────────────────────────────────────────────────
class ValidationError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class FileTooLargeError(ValidationError):
    error_code = "FILE_TOO_LARGE"
    message = "Uploaded file exceeds maximum allowed size"


class InvalidFileTypeError(ValidationError):
    error_code = "INVALID_FILE_TYPE"
    message = "File type is not supported"


class InvalidMimeTypeError(ValidationError):
    error_code = "INVALID_MIME_TYPE"
    message = "File MIME type is not allowed"


class MalformedFileError(ValidationError):
    error_code = "MALFORMED_FILE"
    message = "File is malformed or corrupted"


class PathTraversalError(ValidationError):
    error_code = "PATH_TRAVERSAL"
    message = "Path traversal attempt detected"


# ── Processing Exceptions ─────────────────────────────────────────────────────
class ProcessingError(AppError):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "PROCESSING_ERROR"
    message = "Dataset processing failed"


class ProfilingError(ProcessingError):
    error_code = "PROFILING_ERROR"
    message = "Dataset profiling failed"


class StorageError(AppError):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "STORAGE_ERROR"
    message = "Storage operation failed"


class JobCancelledError(AppError):
    status_code = HTTPStatus.GONE
    error_code = "JOB_CANCELLED"
    message = "Job was cancelled"


class JobTimeoutError(ProcessingError):
    error_code = "JOB_TIMEOUT"
    message = "Job exceeded time limit"


# ── Rate Limit Exceptions ─────────────────────────────────────────────────────
class RateLimitError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded. Please try again later"


# ── AI Exceptions ─────────────────────────────────────────────────────────────
class AIServiceError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "AI_SERVICE_ERROR"
    message = "AI service is temporarily unavailable"


class AIGroundingError(AIServiceError):
    error_code = "AI_GROUNDING_ERROR"
    message = "AI response could not be grounded in dataset statistics"