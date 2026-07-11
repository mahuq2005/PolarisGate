"""Settings endpoints — admin config, blocklist, webhooks, domain thresholds."""
import logging

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.db import get_pool
from shared.schemas import (
    SettingsResponse,
    SettingsUpdate,
    DomainThreshold,
    DomainThresholdList,
)
import bcrypt

from ..helpers import (
    load_admin_from_db,
    save_admin_to_db,
    load_blocklist,
    save_blocklist,
    WEBHOOK_FILE,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    request: Request, current_user: dict = Depends(get_current_user)
):
    admin = await load_admin_from_db()
    return SettingsResponse(
        admin_email=admin.get("admin_email") if admin else None
    )


@router.post("/settings")
async def update_settings(
    request: Request,
    payload: SettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    admin = await load_admin_from_db()
    if not admin:
        raise HTTPException(400, "No admin configured.")
    new_email = payload.admin_email or admin["admin_email"]
    new_hash = admin["admin_password_hash"]
    if payload.new_password:
        if not payload.current_password:
            raise HTTPException(400, "Current password required")
        if len(payload.new_password) < 8:
            raise HTTPException(400, "New password must be at least 8 characters")
        if not bcrypt.checkpw(
            payload.current_password.encode(),
            admin["admin_password_hash"].encode(),
        ):
            raise HTTPException(400, "Current password incorrect")
        new_hash = bcrypt.hashpw(
            payload.new_password.encode(), bcrypt.gensalt()
        ).decode()
    await save_admin_to_db(new_email, new_hash)
    return {"status": "saved"}


# ── Blocklist ──
@router.get("/settings/blocklist")
async def get_blocklist(
    request: Request, current_user: dict = Depends(get_current_user)
):
    words = load_blocklist()
    return {"words": words, "count": len(words)}


@router.post("/settings/blocklist")
async def add_blocklist_word(
    request: Request, current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    word = (body.get("word") or "").strip().lower()
    if not word:
        raise HTTPException(400, "Word required")
    words = load_blocklist()
    if word not in words:
        words.append(word)
    save_blocklist(words)
    await log_audit(
        current_user.get("sub"),
        "blocklist_add",
        resource_type="blocklist",
        details={"word": word},
    )
    return {"words": words, "count": len(words)}


@router.delete("/settings/blocklist/{word}")
async def remove_blocklist_word(
    request: Request,
    word: str,
    current_user: dict = Depends(get_current_user),
):
    words = load_blocklist()
    words = [w for w in words if w != word.lower()]
    save_blocklist(words)
    await log_audit(
        current_user.get("sub"),
        "blocklist_remove",
        resource_type="blocklist",
        details={"word": word},
    )
    return {"words": words, "count": len(words)}


# ── Webhooks ──
@router.get("/settings/webhooks")
async def get_webhooks(
    request: Request, current_user: dict = Depends(get_current_user)
):
    try:
        with open(WEBHOOK_FILE) as f:
            data = yaml.safe_load(f)
            return data or {"url": "", "enabled": False, "events": "toxicity,pii"}
    except (FileNotFoundError, yaml.YAMLError):
        return {"url": "", "enabled": False, "events": "toxicity,pii"}


@router.post("/settings/webhooks")
async def save_webhooks(
    request: Request, current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    with open(WEBHOOK_FILE, "w") as f:
        yaml.safe_dump(body, f)
    return {"status": "saved"}


# ── Domain Thresholds ──
@router.get("/settings/domain-thresholds", response_model=DomainThresholdList)
async def get_domain_thresholds(
    request: Request, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS domain_thresholds "
            "(id SERIAL PRIMARY KEY, domain TEXT NOT NULL UNIQUE, "
            "severity TEXT DEFAULT 'medium', toxicity_action TEXT DEFAULT 'flag', "
            "pii_action TEXT DEFAULT 'mask')"
        )
        rows = await db.fetch(
            "SELECT domain, severity, toxicity_action, pii_action "
            "FROM domain_thresholds ORDER BY domain"
        )
        if rows:
            return DomainThresholdList(
                thresholds=[DomainThreshold(**dict(row)) for row in rows]
            )
        return DomainThresholdList(
            thresholds=[
                DomainThreshold(
                    domain="finance",
                    severity="high",
                    toxicity_action="block",
                    pii_action="block",
                ),
                DomainThreshold(
                    domain="healthcare",
                    severity="critical",
                    toxicity_action="block",
                    pii_action="block",
                ),
                DomainThreshold(
                    domain="education",
                    severity="medium",
                    toxicity_action="flag",
                    pii_action="mask",
                ),
                DomainThreshold(
                    domain="general",
                    severity="medium",
                    toxicity_action="flag",
                    pii_action="mask",
                ),
            ]
        )


@router.post("/settings/domain-thresholds")
async def save_domain_thresholds(
    request: Request,
    payload: DomainThresholdList,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS domain_thresholds "
            "(id SERIAL PRIMARY KEY, domain TEXT NOT NULL UNIQUE, "
            "severity TEXT DEFAULT 'medium', toxicity_action TEXT DEFAULT 'flag', "
            "pii_action TEXT DEFAULT 'mask')"
        )
        for t in payload.thresholds:
            await db.execute(
                "INSERT INTO domain_thresholds (domain, severity, toxicity_action, pii_action) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (domain) DO UPDATE SET "
                "severity=EXCLUDED.severity, toxicity_action=EXCLUDED.toxicity_action, "
                "pii_action=EXCLUDED.pii_action",
                t.domain,
                t.severity,
                t.toxicity_action,
                t.pii_action,
            )
    await log_audit(
        current_user.get("sub"),
        "domain_thresholds_update",
        resource_type="settings",
        details=payload.model_dump(),
    )
    return {"status": "saved"}