"""
Security-owned. Every protected route uses:  Depends(get_authenticated_customer)
Tag security engineer on any PR touching this file.
"""
from fastapi import Header, HTTPException, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from core.database import get_db
from core.security import extract_bearer_token, verify_api_key, make_request_log
from models.api_key import APIKey

logger = logging.getLogger(__name__)


async def get_authenticated_customer(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """
    Validates Bearer API key. Returns the APIKey record (which has .user_id = customer_id).
    Cross-tenant isolation: callers must always filter by api_key.user_id in data queries.
    """
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Missing or malformed Authorization header", "code": "AUTH_MISSING"},
        )

    result = await db.execute(
        select(APIKey).where(APIKey.is_active == True)  # noqa: E712
    )
    matched: APIKey | None = None
    for key_record in result.scalars().all():
        if verify_api_key(token, key_record.key_hash):
            matched = key_record
            break

    if not matched:
        logger.warning("auth_failed", extra=make_request_log(
            api_key_plaintext=token,
            ip=request.client.host if request.client else "",
            path=str(request.url.path),
        ))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid API key", "code": "AUTH_INVALID"},
        )

    logger.info("auth_ok", extra=make_request_log(
        customer_id=str(matched.user_id),
        api_key_plaintext=token,
        ip=request.client.host if request.client else "",
        path=str(request.url.path),
    ))
    return matched
