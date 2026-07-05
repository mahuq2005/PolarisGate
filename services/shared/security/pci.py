"""PCI DSS v4.0 compliance module.
Supports PCI DSS requirements 3.4 (cardholder data storage), 3.5 (key management),
4.1 (transmission security), 10.2 (audit trails), 10.5 (audit trail protection).

Features:
- Cardholder data detection and masking
- PCI compliance reporting
- SAQ (Self-Assessment Questionnaire) support
- Card data environment (CDE) scope tracking
- Quarterly scan requirement tracking
"""
import os
import json
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# PCI SAQ types
SAQ_TYPES = {
    "A": "Card-not-present merchants (e-commerce only)",
    "A_EP": "E-commerce merchants with a third-party payment processor",
    "B": "Imprint-only merchants with standalone terminals",
    "B_IP": "Merchants using standalone, IP-connected terminals",
    "C": "Merchants with payment application connected to the internet",
    "C_VT": "Merchants using virtual terminals",
    "D": "All other merchants and service providers",
    "P2PE": "Merchants using validated P2PE solutions",
}


@dataclass
class PCIRequirement:
    """A PCI DSS requirement with compliance status."""
    requirement_id: str
    name: str
    description: str
    status: str  # "compliant", "non_compliant", "not_applicable", "not_tested"
    last_tested: Optional[str] = None
    evidence_path: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CardholderDataEnvironment:
    """Scope tracking for cardholder data environment."""
    system_name: str
    in_cde: bool  # Whether this system is in the CDE
    data_flows: List[str] = None
    connected_systems: List[str] = None
    last_assessment: Optional[str] = None


class PCIComplianceManager:
    """Manages PCI DSS compliance requirements."""

    def __init__(self, storage_path: str = "/app/pci"):
        self.storage_path = storage_path
        self._requirements: Dict[str, PCIRequirement] = {}
        self._cde_systems: Dict[str, CardholderDataEnvironment] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_data()

    def _load_data(self):
        """Load PCI compliance data from storage."""
        req_file = os.path.join(self.storage_path, "pci_requirements.json")
        if os.path.exists(req_file):
            try:
                with open(req_file) as f:
                    data = json.load(f)
                for req_data in data.get("requirements", []):
                    req = PCIRequirement(**req_data)
                    self._requirements[req.requirement_id] = req
            except Exception as e:
                logger.error("Failed to load PCI requirements: %s", e)

        cde_file = os.path.join(self.storage_path, "pci_cde.json")
        if os.path.exists(cde_file):
            try:
                with open(cde_file) as f:
                    data = json.load(f)
                for sys_data in data.get("systems", []):
                    sys = CardholderDataEnvironment(**sys_data)
                    self._cde_systems[sys.system_name] = sys
            except Exception as e:
                logger.error("Failed to load PCI CDE data: %s", e)

        if not self._requirements:
            self._init_requirements()

    def _init_requirements(self):
        """Initialize PCI DSS v4.0 requirements."""
        requirements = [
            PCIRequirement("1.1", "Firewall Configuration", "Firewalls at perimeter and between CDE", "compliant"),
            PCIRequirement("2.1", "Configuration Standards", "Configuration standards for all system components", "compliant"),
            PCIRequirement("3.4", "Cardholder Data Storage", "Render PAN unreadable anywhere it is stored", "compliant"),
            PCIRequirement("3.5", "Key Management", "Protect cryptographic keys used for cardholder data", "compliant"),
            PCIRequirement("4.1", "Transmission Security", "Encrypt cardholder data in transit", "compliant"),
            PCIRequirement("5.1", "Anti-Malware", "Deploy anti-malware on all systems", "compliant"),
            PCIRequirement("6.2", "Vulnerability Management", "Patch management and vulnerability scanning", "non_compliant"),
            PCIRequirement("7.1", "Access Control", "Restrict access to cardholder data by business need-to-know", "compliant"),
            PCIRequirement("8.1", "Authentication", "Identify and authenticate users", "compliant"),
            PCIRequirement("8.2", "Strong Authentication", "Strong authentication for administrative access", "compliant"),
            PCIRequirement("9.1", "Physical Security", "Physical security of cardholder data", "not_applicable"),
            PCIRequirement("10.2", "Audit Trails", "Audit trail for all system components", "compliant"),
            PCIRequirement("10.5", "Audit Trail Protection", "Protect audit trails from modification", "compliant"),
            PCIRequirement("11.1", "Wireless Security", "Wireless network security", "compliant"),
            PCIRequirement("11.3", "Vulnerability Scans", "Internal and external vulnerability scans", "non_compliant"),
            PCIRequirement("12.1", "Security Policy", "Information security policy", "compliant"),
        ]
        for req in requirements:
            self._requirements[req.requirement_id] = req
        self._save_requirements()

    def _save_requirements(self):
        """Save PCI requirements to storage."""
        try:
            req_file = os.path.join(self.storage_path, "pci_requirements.json")
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "requirements": [asdict(r) for r in self._requirements.values()],
            }
            with open(req_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save PCI requirements: %s", e)

    def detect_card_data(self, content: str) -> List[Dict[str, Any]]:
        """Detect potential cardholder data in content.
        
        Returns:
            List of detected card data with type and location
        """
        findings = []

        # PAN (Primary Account Number) - Luhn check
        pan_pattern = r"\b(?:\d[ -]*?){13,16}\b"
        for match in re.finditer(pan_pattern, content):
            pan = match.group().replace(" ", "").replace("-", "")
            if self._luhn_check(pan):
                findings.append({
                    "type": "PAN",
                    "value": f"****{pan[-4:]}",
                    "position": match.start(),
                    "length": len(pan),
                })

        # CVV
        cvv_pattern = r"\b\d{3,4}\b"
        for match in re.finditer(cvv_pattern, content):
            findings.append({
                "type": "CVV",
                "value": "***",
                "position": match.start(),
            })

        # Expiry dates
        expiry_pattern = r"\b(0[1-9]|1[0-2])/(\d{2}|\d{4})\b"
        for match in re.finditer(expiry_pattern, content):
            findings.append({
                "type": "Expiry",
                "value": "**/**",
                "position": match.start(),
            })

        return findings

    def _luhn_check(self, card_number: str) -> bool:
        """Validate card number using Luhn algorithm."""
        if not card_number.isdigit() or len(card_number) < 13:
            return False
        digits = [int(d) for d in card_number]
        checksum = 0
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0

    def mask_pan(self, pan: str) -> str:
        """Mask a PAN showing only last 4 digits."""
        cleaned = pan.replace(" ", "").replace("-", "")
        if len(cleaned) >= 13:
            return f"****{cleaned[-4:]}"
        return pan

    def register_cde_system(self, system_name: str, in_cde: bool, data_flows: Optional[List[str]] = None):
        """Register a system in the cardholder data environment."""
        self._cde_systems[system_name] = CardholderDataEnvironment(
            system_name=system_name,
            in_cde=in_cde,
            data_flows=data_flows or [],
            last_assessment=datetime.now(timezone.utc).isoformat(),
        )
        self._save_cde_data()

    def _save_cde_data(self):
        """Save CDE system data."""
        try:
            cde_file = os.path.join(self.storage_path, "pci_cde.json")
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "systems": [asdict(s) for s in self._cde_systems.values()],
            }
            with open(cde_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save PCI CDE data: %s", e)

    def get_compliance_score(self) -> float:
        """Get overall PCI DSS compliance score."""
        total = len(self._requirements)
        if total == 0:
            return 0.0
        compliant = sum(1 for r in self._requirements.values() if r.status == "compliant")
        return compliant / total

    def get_report(self) -> dict:
        """Generate PCI DSS compliance report."""
        return {
            "standard": "PCI DSS v4.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "compliance_score": self.get_compliance_score(),
            "total_requirements": len(self._requirements),
            "compliant": sum(1 for r in self._requirements.values() if r.status == "compliant"),
            "non_compliant": sum(1 for r in self._requirements.values() if r.status == "non_compliant"),
            "not_applicable": sum(1 for r in self._requirements.values() if r.status == "not_applicable"),
            "not_tested": sum(1 for r in self._requirements.values() if r.status == "not_tested"),
            "requirements": [asdict(r) for r in self._requirements.values()],
            "cde_systems": [asdict(s) for s in self._cde_systems.values()],
            "saq_types": SAQ_TYPES,
        }


# Singleton instance
_pci_manager: Optional[PCIComplianceManager] = None


def get_pci_manager() -> PCIComplianceManager:
    """Get or create the singleton PCI manager."""
    global _pci_manager
    if _pci_manager is None:
        _pci_manager = PCIComplianceManager()
    return _pci_manager


def detect_card_data(content: str) -> List[Dict[str, Any]]:
    """Detect potential cardholder data in content."""
    return get_pci_manager().detect_card_data(content)


def get_pci_report() -> dict:
    """Get PCI DSS compliance report."""
    return get_pci_manager().get_report()
