"""Standard error helpers — security-owned. Use these, never raise raw HTTPException."""
from fastapi import HTTPException, status


def unauthorized(msg="Unauthorized", code="UNAUTHORIZED"):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "unauthorized", "message": msg, "code": code})


def forbidden(msg="Forbidden", code="FORBIDDEN"):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail={"error": "forbidden", "message": msg, "code": code})


def not_found(resource="Resource", code="NOT_FOUND"):
    # Cross-tenant: always 404, never 403 — don't reveal existence
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                        detail={"error": "not_found", "message": f"{resource} not found", "code": code})


def bad_request(msg="Bad request", code="BAD_REQUEST"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "bad_request", "message": msg, "code": code})


def conflict(msg="Conflict", code="CONFLICT"):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                        detail={"error": "conflict", "message": msg, "code": code})


def unprocessable(msg="Unprocessable", code="UNPROCESSABLE"):
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": "unprocessable", "message": msg, "code": code})


def server_error(msg="Internal server error", code="SERVER_ERROR"):
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"error": "server_error", "message": msg, "code": code})
