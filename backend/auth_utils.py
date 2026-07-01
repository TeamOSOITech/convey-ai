# auth_utils.py — shared authentication dependency
# Extracted from main.py so route modules can import it without circular imports.

import asyncio
from fastapi import Header, HTTPException
from database import supabase as _supabase_auth


async def require_auth(authorization: str = Header(default=None)):
    """
    FastAPI dependency — use as Depends(require_auth) on any protected route.
    Extracts the Bearer token from the Authorization header and validates it
    against Supabase. Raises 401 if missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>"
        )
    token = authorization[len("Bearer "):].strip()
    try:
        user_response = await asyncio.to_thread(_supabase_auth.auth.get_user, token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")