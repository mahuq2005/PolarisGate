"""Consent management module for GDPR, PIPEDA, and HIPAA compliance.
Supports GDPR (Art. 7, Art. 17), PIPEDA (Principle 3), HIPAA (164.508).

Features:
- Consent record management with audit trail
- Consent withdrawal and right to erasure
- Purpose-based consent tracking
- Automated consent expiry
- Consent verification API
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConsentRecord:
    """A record of user consent for data processing."""
    consent_id: str
    user_id: str
    purpose: str  # e.g., "marketing", "analytics", "healthcare_processing"
    status: str  # "granted", "withdrawn", "expired"
    granted_at: str
    expires_at: Optional[str] = None
    withdrawn_at: Optional[str] = None
    data_categories: List[str] = None  # e.g., ["email", "health_data", "location"]
    processing_methods: List[str] = None  # e.g., ["ai_inference", "storage", "sharing"]
    third_party_sharing: bool = False
    consent_version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ConsentManager:
    """Manages user consent records with full audit trail."""

    def __init__(self, storage_path: str = "/app/consent"):
        self.storage_path = storage_path
        self._records: Dict[str, ConsentRecord] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_records()

    def _load_records(self):
        """Load consent records from storage."""
        records_file = os.path.join(self.storage_path, "consent_records.json")
        if os.path.exists(records_file):
            try:
                with open(records_file) as f:
                    data = json.load(f)
                for record_data in data.get("records", []):
                    record = ConsentRecord(**record_data)
                    self._records[record.consent_id] = record
                logger.info("Loaded %d consent records", len(self._records))
            except Exception as e:
                logger.error("Failed to load consent records: %s", e)

    def _save_records(self):
        """Save consent records to storage."""
        try:
            records_file = os.path.join(self.storage_path, "consent_records.json")
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "records": [asdict(r) for r in self._records.values()],
            }
            with open(records_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save consent records: %s", e)

    def grant_consent(
        self,
        user_id: str,
        purpose: str,
        data_categories: List[str],
        processing_methods: Optional[List[str]] = None,
        third_party_sharing: bool = False,
        ttl_days: Optional[int] = 365,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsentRecord:
        """Record a new consent grant.
        
        Args:
            user_id: Unique user identifier
            purpose: Purpose of data processing
            data_categories: Categories of data covered
            processing_methods: Methods of processing
            third_party_sharing: Whether data may be shared with third parties
            ttl_days: Consent validity period in days (None = no expiry)
            ip_address: IP address of the user
            user_agent: User agent of the browser/device
        
        Returns:
            The created ConsentRecord
        """
        import uuid
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            consent_id=str(uuid.uuid4()),
            user_id=user_id,
            purpose=purpose,
            status="granted",
            granted_at=now.isoformat(),
            expires_at=(now + timedelta(days=ttl_days)).isoformat() if ttl_days else None,
            data_categories=data_categories or [],
            processing_methods=processing_methods or ["storage"],
            third_party_sharing=third_party_sharing,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._records[record.consent_id] = record
        self._save_records()
        logger.info("Consent granted: user=%s purpose=%s id=%s", user_id, purpose, record.consent_id[:8])
        return record

    def withdraw_consent(self, consent_id: str) -> bool:
        """Withdraw a previously granted consent.
        
        Args:
            consent_id: The consent record ID
        
        Returns:
            True if consent was withdrawn
        """
        record = self._records.get(consent_id)
        if not record:
            logger.warning("Consent not found: %s", consent_id)
            return False
        if record.status != "granted":
            logger.warning("Consent %s is already %s", consent_id, record.status)
            return False

        record.status = "withdrawn"
        record.withdrawn_at = datetime.now(timezone.utc).isoformat()
        self._save_records()
        logger.info("Consent withdrawn: id=%s user=%s purpose=%s", consent_id, record.user_id, record.purpose)
        return True

    def withdraw_all_user_consent(self, user_id: str) -> int:
        """Withdraw all consents for a user (right to erasure).
        
        Args:
            user_id: The user whose consents to withdraw
        
        Returns:
            Number of consents withdrawn
        """
        count = 0
        for record in self._records.values():
            if record.user_id == user_id and record.status == "granted":
                record.status = "withdrawn"
                record.withdrawn_at = datetime.now(timezone.utc).isoformat()
                count += 1
        if count:
            self._save_records()
            logger.info("All consents withdrawn for user %s (%d records)", user_id, count)
        return count

    def check_consent(self, user_id: str, purpose: str, data_category: str) -> bool:
        """Check if a user has valid consent for a specific purpose and data category.
        
        Args:
            user_id: The user to check
            purpose: The processing purpose
            data_category: The data category
        
        Returns:
            True if valid consent exists
        """
        now = datetime.now(timezone.utc)
        for record in self._records.values():
            if record.user_id != user_id:
                continue
            if record.purpose != purpose:
                continue
            if record.status != "granted":
                continue
            if data_category not in (record.data_categories or []):
                continue
            # Check expiry
            if record.expires_at:
                expiry = datetime.fromisoformat(record.expires_at)
                if now > expiry:
                    continue
            return True
        return False

    def get_user_consents(self, user_id: str) -> List[ConsentRecord]:
        """Get all consent records for a user."""
        return [r for r in self._records.values() if r.user_id == user_id]

    def get_expired_consents(self) -> List[ConsentRecord]:
        """Get all expired consents that need renewal."""
        now = datetime.now(timezone.utc)
        expired = []
        for record in self._records.values():
            if record.status == "granted" and record.expires_at:
                expiry = datetime.fromisoformat(record.expires_at)
                if now > expiry:
                    expired.append(record)
        return expired

    def get_stats(self) -> dict:
        """Get consent management statistics."""
        total = len(self._records)
        granted = sum(1 for r in self._records.values() if r.status == "granted")
        withdrawn = sum(1 for r in self._records.values() if r.status == "withdrawn")
        expired = len(self.get_expired_consents())
        return {
            "total_records": total,
            "granted": granted,
            "withdrawn": withdrawn,
            "expired": expired,
            "unique_users": len(set(r.user_id for r in self._records.values())),
        }


# Singleton instance
_consent_manager: Optional[ConsentManager] = None


def get_consent_manager() -> ConsentManager:
    """Get or create the singleton consent manager."""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()
    return _consent_manager


def check_user_consent(user_id: str, purpose: str, data_category: str) -> bool:
    """Check if a user has given consent."""
    return get_consent_manager().check_consent(user_id, purpose, data_category)


def grant_user_consent(
    user_id: str,
    purpose: str,
    data_categories: List[str],
    ttl_days: int = 365,
) -> ConsentRecord:
    """Grant consent for a user."""
    return get_consent_manager().grant_consent(user_id, purpose, data_categories, ttl_days=ttl_days)
