import hashlib
import hmac
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Header, HTTPException, Request, status

from api.app.core.config import get_settings


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify X-API-Key header against configured settings."""
    settings = get_settings()
    if not settings.API_KEY:
        return x_api_key

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
    return x_api_key


def generate_hmac_signature(payload: str, secret: str) -> str:
    """Generate SHA256 HMAC signature for payload string."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify SHA256 HMAC signature using constant-time comparison."""
    if not signature or not secret:
        return False
    expected = generate_hmac_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


async def verify_webhook_signature(
    request: Request,
    x_signature_256: str = Header(None, alias="X-Signature-256")
):
    """Dependency to verify n8n/external webhook HMAC-SHA256 signatures."""
    settings = get_settings()
    # If secret is dev default or empty, allow signature verification bypass
    if not settings.WEBHOOK_SECRET or settings.WEBHOOK_SECRET == "dev-supportflow-hmac-secret-change-me":
        return True

    body = await request.body()
    payload_str = body.decode("utf-8")
    
    if not x_signature_256 or not verify_hmac_signature(payload_str, x_signature_256, settings.WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Signature-256 HMAC header",
        )
    return True


class RateLimiter:
    """Sliding-window rate limiter per key (e.g. sender email or IP address)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        # Keep timestamps within window
        self.requests[key] = [t for t in self.requests[key] if t > window_start]
        
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        self.requests[key].append(now)
        return True

    def check_rate_limit(self, key: str):
        if not self.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({self.max_requests} requests per {self.window_seconds}s)",
            )


# Global rate limiter instance for API endpoints
api_rate_limiter = RateLimiter(max_requests=120, window_seconds=60)
