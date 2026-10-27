import hashlib
import hmac
import time
from typing import Optional
from fastapi import Header, HTTPException, Request, status
from .config import settings


def generate_hmac_signature(timestamp: str, body: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature matching CodeIgniter 4 client implementation."""
    payload = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


async def verify_ci4_signature(
    request: Request,
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_ci4_signature: Optional[str] = Header(None, alias="X-CI4-Signature"),
) -> bool:
    """
    Validates HMAC signature sent by CodeIgniter 4 DhktAiClient.
    If settings.REQUIRE_HMAC is False and no signature header is sent, allow the request (dev mode).
    If signature headers are sent, they must be valid.
    """
    secret = settings.AI_INTERNAL_HMAC_SECRET

    # If HMAC is optional and no headers provided, bypass for ease of development / Swagger docs
    if not settings.REQUIRE_HMAC and not x_ci4_signature and not x_timestamp:
        return True

    if not x_timestamp or not x_ci4_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required security headers: X-Timestamp and X-CI4-Signature",
        )

    # Check timestamp freshness to prevent replay attacks
    try:
        req_time = int(x_timestamp)
        now = int(time.time())
        if abs(now - req_time) > settings.HMAC_MAX_SKEW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Request timestamp expired (skew > {settings.HMAC_MAX_SKEW_SECONDS}s)",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Timestamp header value",
        )

    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        # PENTING: Jangan panggil request.body() pada multipart/form-data karena
        # akan menghabiskan stream ASGI Starlette (error: Stream consumed).
        valid_sigs = [
            hmac.new(secret.encode("utf-8"), f"{x_timestamp}.multipart".encode("utf-8"), hashlib.sha256).hexdigest(),
            hmac.new(secret.encode("utf-8"), x_timestamp.encode("utf-8"), hashlib.sha256).hexdigest(),
        ]
        if not any(hmac.compare_digest(s, x_ci4_signature) for s in valid_sigs):
            if settings.REQUIRE_HMAC:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid HMAC signature for multipart request",
                )
        return True

    # Read raw body for JSON requests
    body = await request.body()
    expected_sig = generate_hmac_signature(x_timestamp, body, secret)

    if not hmac.compare_digest(expected_sig, x_ci4_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid HMAC signature",
        )

    return True
