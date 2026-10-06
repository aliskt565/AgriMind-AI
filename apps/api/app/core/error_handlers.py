"""
Consistent error response shape across the whole API, per the roadmap's API
standards (Section 37 of the roadmap): every error has the same envelope so
the frontend can handle failures generically.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("agrimind.api")


def _error_body(message: str, error_type: str, details=None):
    return {"error": {"type": error_type, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail), "http_error"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Pydantic v2 can embed the raw exception object itself (e.g. a plain
        # ValueError raised inside a @field_validator) in errors()[i]['ctx'],
        # which is not directly JSON-serializable. jsonable_encoder safely
        # converts any such non-serializable values (falling back to their
        # string representation) instead of the response crashing with a
        # 500 while trying to build the 422 error body.
        return JSONResponse(
            status_code=422,
            content=_error_body("Request validation failed", "validation_error", jsonable_encoder(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak stack traces or internals to the client -- log server-side only.
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("An unexpected error occurred. Please try again.", "internal_error"),
        )
