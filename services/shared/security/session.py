"""Session Management for PolarisGate.
Provides session tracking, concurrent session limits, and force-logout capabilities.

Features:
- Track active sessions per user
- Limit concurrent sessions per user
- Force logout on password change
- Session invalidation
- Session audit logging
"""
import os
import json
import logging
import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────

MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "5"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(24 * 3600)))  # 24 hours


# ─── Session Manager ─────────────────────────────────────────────────────

class SessionManager:
    """Manages user sessions with Redis-backed storage."""
    
    SESSION_KEY_PREFIX = "session:"
    USER_SESSIONS_PREFIX = "user_sessions:"
    
    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"{SessionManager.SESSION_KEY_PREFIX}{session_id}"
    
    @staticmethod
    def _user_sessions_key(user_email: str) -> str:
        return f"{SessionManager.USER_SESSIONS_PREFIX}{user_email}"
    
    @staticmethod
    async def create_session(
        redis,
        user_email: str,
        role: str = "viewer",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session for a user.
        
        If the user exceeds MAX_CONCURRENT_SESSIONS, the oldest session is revoked.
        Returns the session ID.
        """
        session_id = secrets.token_hex(32)
        now = datetime.now(timezone.utc)
        
        session_data = {
            "session_id": session_id,
            "user_email": user_email,
            "role": role,
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "metadata": metadata or {},
            "is_active": True,
        }
        
        # Store session
        await redis.setex(
            SessionManager._session_key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(session_data),
        )
        
        # Add to user's session list
        user_sessions_key = SessionManager._user_sessions_key(user_email)
        await redis.sadd(user_sessions_key, session_id)
        await redis.expire(user_sessions_key, SESSION_TTL_SECONDS)
        
        # Enforce concurrent session limit
        await SessionManager._enforce_session_limit(redis, user_email)
        
        logger.info(f"Session created for {user_email}: {session_id[:8]}...")
        return session_id
    
    @staticmethod
    async def _enforce_session_limit(redis, user_email: str):
        """Remove oldest sessions if user exceeds the limit."""
        user_sessions_key = SessionManager._user_sessions_key(user_email)
        session_ids = await redis.smembers(user_sessions_key)
        
        if len(session_ids) <= MAX_CONCURRENT_SESSIONS:
            return
        
        # Get session data with timestamps
        sessions = []
        for sid in session_ids:
            data = await redis.get(SessionManager._session_key(sid))
            if data:
                session_data = json.loads(data)
                sessions.append((session_data["created_at"], sid))
        
        # Sort by creation time (oldest first)
        sessions.sort()
        
        # Remove oldest sessions beyond the limit
        sessions_to_remove = len(sessions) - MAX_CONCURRENT_SESSIONS
        for _, sid in sessions[:sessions_to_remove]:
            await SessionManager.revoke_session(redis, sid)
            logger.info(f"Revoked oldest session {sid[:8]}... for {user_email}")
    
    @staticmethod
    async def validate_session(redis, session_id: str) -> Optional[Dict[str, Any]]:
        """Validate a session and return session data if valid.
        
        Also updates the last_activity timestamp.
        """
        data = await redis.get(SessionManager._session_key(session_id))
        if data is None:
            return None
        
        session_data = json.loads(data)
        
        if not session_data.get("is_active", True):
            return None
        
        # Update last activity
        session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
        await redis.setex(
            SessionManager._session_key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(session_data),
        )
        
        return session_data
    
    @staticmethod
    async def revoke_session(redis, session_id: str) -> bool:
        """Revoke a specific session."""
        data = await redis.get(SessionManager._session_key(session_id))
        if data is None:
            return False
        
        session_data = json.loads(data)
        session_data["is_active"] = False
        
        await redis.setex(
            SessionManager._session_key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(session_data),
        )
        
        # Remove from user's session list
        user_email = session_data.get("user_email")
        if user_email:
            await redis.srem(
                SessionManager._user_sessions_key(user_email),
                session_id,
            )
        
        logger.info(f"Session revoked: {session_id[:8]}...")
        return True
    
    @staticmethod
    async def revoke_all_user_sessions(redis, user_email: str) -> int:
        """Revoke all sessions for a specific user.
        
        Used when password is changed or user is deactivated.
        Returns the number of sessions revoked.
        """
        user_sessions_key = SessionManager._user_sessions_key(user_email)
        session_ids = await redis.smembers(user_sessions_key)
        
        count = 0
        for sid in session_ids:
            if await SessionManager.revoke_session(redis, sid):
                count += 1
        
        # Clean up the user's session set
        await redis.delete(user_sessions_key)
        
        logger.info(f"All {count} sessions revoked for {user_email}")
        return count
    
    @staticmethod
    async def get_user_active_sessions(redis, user_email: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        user_sessions_key = SessionManager._user_sessions_key(user_email)
        session_ids = await redis.smembers(user_sessions_key)
        
        active_sessions = []
        for sid in session_ids:
            data = await redis.get(SessionManager._session_key(sid))
            if data:
                session_data = json.loads(data)
                if session_data.get("is_active", True):
                    active_sessions.append(session_data)
        
        return active_sessions
    
    @staticmethod
    async def cleanup_expired_sessions(redis) -> int:
        """Clean up expired sessions from user session sets.
        
        Should be called periodically by a background task.
        """
        # This is handled automatically by Redis TTL, but we can
        # also do a manual cleanup for stale entries in user session sets
        count = 0
        # Scan for user session keys
        cursor = 0
        while True:
            cursor, keys = await redis.scan(
                cursor,
                match=f"{SessionManager.USER_SESSIONS_PREFIX}*",
                count=100,
            )
            for key in keys:
                session_ids = await redis.smembers(key)
                for sid in session_ids:
                    if not await redis.exists(SessionManager._session_key(sid)):
                        await redis.srem(key, sid)
                        count += 1
            if cursor == 0:
                break
        
        return count
