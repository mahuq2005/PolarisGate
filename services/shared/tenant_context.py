"""Tenant Context Middleware — extracts team_id from JWT for multi-tenant scoping."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extracts team_id from JWT claims and attaches to request.state.
    
    All downstream routes can read ``request.state.team_id`` and 
    ``request.state.user_id`` for team-scoped operations (budgets,
    quotas, policies, audit trails).
    """
    
    async def dispatch(self, request: Request, call_next):
        request.state.team_id = "default"
        request.state.user_id = "anonymous"
        
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from shared.security.auth import decode_token
                token = auth_header.replace("Bearer ", "")
                payload = decode_token(token)
                if payload:
                    request.state.user_id = payload.get("sub", "anonymous")
                    request.state.team_id = payload.get("team_id", payload.get("sub", "default"))
                    request.state.role = payload.get("role", "viewer")
            except Exception as e:
                logger.debug("Could not decode token for tenant context: %s", e)
        
        response = await call_next(request)
        return response