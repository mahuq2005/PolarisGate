"""Shared helpers used across gateway routers."""
import logging
import os
import yaml
import fcntl

logger = logging.getLogger(__name__)

from shared.db import get_pool

POLICY_FILE_PATH = os.getenv("POLICY_FILE_PATH", "/app/policies.yaml")
BLOCKLIST_FILE = "/app/blocklist.yaml"
WEBHOOK_FILE = "/app/webhooks.yaml"

DEFAULT_POLICIES = [
    {"name": "Hate speech", "category": "hate_speech", "type": "toxicity", "severity": "medium", "action": "block", "message": "Hate speech detected.", "enabled": True},
    {"name": "Harassment", "category": "harassment", "type": "toxicity", "severity": "medium", "action": "block", "message": "Harassment detected.", "enabled": True},
    {"name": "Threat", "category": "threat", "type": "toxicity", "severity": "low", "action": "block", "message": "Threat detected.", "enabled": True},
    {"name": "Violence", "category": "violence", "type": "toxicity", "severity": "medium", "action": "block", "message": "Violent content blocked.", "enabled": True},
    {"name": "Profanity", "category": "profanity", "type": "toxicity", "severity": "high", "action": "flag", "message": "Profanity flagged.", "enabled": True},
    {"name": "SIN", "category": "SIN", "type": "pii", "patterns": ["\\b\\d{3}-\\d{3}-\\d{3}\\b", "\\b\\d{9}\\b"], "action": "mask", "message": "SIN masked.", "enabled": True},
    {"name": "Health Card", "category": "health_card", "type": "pii", "patterns": ["\\b\\d{4}-\\d{3}-\\d{3}-[A-Z]{2}\\b"], "action": "mask", "message": "Health card masked.", "enabled": True},
    {"name": "Phone Number", "category": "phone", "type": "pii", "patterns": ["\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b"], "action": "mask", "message": "Phone masked.", "enabled": True},
    {"name": "Credit Card", "category": "credit_card", "type": "pii", "patterns": ["\\b(?:\\d[ -]*?){13,16}\\b"], "action": "block", "message": "Credit card blocked.", "enabled": True},
    {"name": "Email", "category": "email", "type": "pii", "patterns": ["\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"], "action": "mask", "message": "Email masked.", "enabled": True},
    {"name": "IP Address", "category": "ip_address", "type": "pii", "patterns": ["\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b"], "action": "mask", "message": "IP masked.", "enabled": True},
    {"name": "Driver's License", "category": "driver_license", "type": "pii", "patterns": ["\\b[A-Z]\\d{4}-\\d{5}-\\d{5}\\b"], "action": "mask", "message": "Driver's license masked.", "enabled": True},
    {"name": "Passport", "category": "passport", "type": "pii", "patterns": ["\\b[A-Z]{2}\\d{6}\\b"], "action": "mask", "message": "Passport masked.", "enabled": True},
]

MULTI_LANG_KEYWORDS = {
    "fr": ["haine","raciste","tuer","attaquer","idiot","stupide","détruire","mort","menace"],
    "es": ["odio","racista","matar","atacar","idiota","estúpido","destruir","muerte","amenaza"],
    "de": ["hass","rassistisch","töten","angreifen","idiot","dumm","zerstören","tod","drohung"],
    "ar": ["كراهية","عنصري","قتل","هجوم","غبي","تدمير","موت","تهديد"],
    "hi": ["नफ़रत","नस्लवादी","मारना","हमला","बेवकूफ़","नष्ट","मौत","धमकी"],
    "zh": ["仇恨","种族主义","杀","攻击","愚蠢","毁灭","死亡","威胁"],
}


async def load_admin_from_db():
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT admin_email, admin_password_hash "
                "FROM admin_settings WHERE id = 1"
            )
            if row:
                return {
                    "admin_email": row["admin_email"],
                    "admin_password_hash": row["admin_password_hash"],
                }
    except Exception as exc:
        logger.warning("Failed to load admin settings: %s", exc)
    return None


async def save_admin_to_db(email: str, password_hash: str, session_timeout_minutes: int = None):
    pool = await get_pool()
    async with pool.acquire() as db:
        if session_timeout_minutes is not None:
            await db.execute(
                "INSERT INTO admin_settings (id, admin_email, admin_password_hash, session_timeout_minutes) "
                "VALUES (1, $1, $2, $3) ON CONFLICT (id) DO UPDATE SET "
                "admin_email=EXCLUDED.admin_email, "
                "admin_password_hash=EXCLUDED.admin_password_hash, "
                "session_timeout_minutes=EXCLUDED.session_timeout_minutes, "
                "updated_at=NOW()",
                email, password_hash, session_timeout_minutes,
            )
        else:
            await db.execute(
                "INSERT INTO admin_settings (id, admin_email, admin_password_hash) "
                "VALUES (1, $1, $2) ON CONFLICT (id) DO UPDATE SET "
                "admin_email=EXCLUDED.admin_email, "
                "admin_password_hash=EXCLUDED.admin_password_hash, updated_at=NOW()",
                email, password_hash,
            )


async def get_session_timeout_minutes() -> int:
    """Return the session timeout in minutes, defaulting to 30."""
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT session_timeout_minutes FROM admin_settings WHERE id = 1"
            )
            if row and row["session_timeout_minutes"] is not None:
                return row["session_timeout_minutes"]
    except Exception as exc:
        logger.debug("Failed to load session timeout: %s", exc)
    return 30


async def save_session_timeout_minutes(minutes: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO admin_settings (id, session_timeout_minutes) "
            "VALUES (1, $1) ON CONFLICT (id) DO UPDATE SET "
            "session_timeout_minutes=EXCLUDED.session_timeout_minutes, updated_at=NOW()",
            minutes,
        )


def load_blocklist():
    try:
        with open(BLOCKLIST_FILE) as f:
            data = yaml.safe_load(f)
            return data.get("words", []) if data else []
    except (FileNotFoundError, yaml.YAMLError) as exc:
        logger.debug("Blocklist not loaded: %s", exc)
        return []


def save_blocklist(words):
    with open(BLOCKLIST_FILE, "w") as f:
        yaml.safe_dump({"words": words}, f)


def load_policies_from_file():
    try:
        with open(POLICY_FILE_PATH) as f:
            data = yaml.safe_load(f)
            if data and "policies" in data and len(data["policies"]) > 0:
                return data
    except (FileNotFoundError, yaml.YAMLError) as exc:
        logger.debug("Custom policies not loaded, using defaults: %s", exc)
    return {"policies": DEFAULT_POLICIES}


def detect_language(text):
    counts = {"en": 0}
    tl = text.lower()
    for lang, keywords in MULTI_LANG_KEYWORDS.items():
        counts[lang] = sum(1 for kw in keywords if kw in tl)
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "en"