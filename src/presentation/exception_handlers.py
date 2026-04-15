from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)

logger = structlog.get_logger(__name__)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    logger.warning("domain_error", error=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Неверные учётные данные"})


async def authz_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def duplicate_handler(request: Request, exc: DuplicateEntityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def register_exception_handlers(app):
    app.add_exception_handler(EntityNotFoundError, not_found_handler)
    app.add_exception_handler(AuthenticationError, auth_error_handler)
    app.add_exception_handler(AuthorizationError, authz_error_handler)
    app.add_exception_handler(DuplicateEntityError, duplicate_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
