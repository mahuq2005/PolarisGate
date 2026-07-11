"""Policy management endpoints."""
import logging

import yaml
from fastapi import APIRouter, Depends, Request
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.schemas import PolicyList
import fcntl

from ..helpers import load_policies_from_file, POLICY_FILE_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])


@router.get("", response_model=PolicyList)
async def get_policies(request: Request, current_user: dict = Depends(get_current_user)):
    return load_policies_from_file()


@router.post("")
async def save_policies(
    request: Request,
    payload: PolicyList,
    current_user: dict = Depends(get_current_user),
):
    user_email = current_user.get("sub")
    await log_audit(user_email, "policy_update", resource_type="policy", details=payload.model_dump())
    try:
        with open(POLICY_FILE_PATH, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yaml.safe_dump(payload.model_dump(), f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except PermissionError:
        logger.warning("Cannot write policies.yaml")
    return {"status": "saved"}