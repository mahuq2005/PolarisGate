"""Compliance control mapping and evidence collection.
Supports SOC 2, FedRAMP, HIPAA, ISO 27001, GDPR, PCI DSS, EU AI Act.

Features:
- Control mapping to multiple frameworks
- Automated evidence collection
- Compliance gap analysis
- Audit-ready reporting
- Continuous compliance monitoring
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ComplianceControl:
    """A compliance control mapped to one or more frameworks."""
    control_id: str
    name: str
    description: str
    frameworks: List[str]  # e.g., ["SOC2-CC6.1", "FedRAMP-IA-5", "HIPAA-164.312"]
    status: str  # "implemented", "partial", "planned", "not_applicable"
    evidence_path: Optional[str] = None
    last_validated: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ComplianceFramework:
    """A compliance framework with its controls."""
    name: str
    version: str
    description: str
    controls: List[ComplianceControl]


class ComplianceManager:
    """Manages compliance controls across multiple frameworks."""

    def __init__(self, storage_path: str = "/app/compliance"):
        self.storage_path = storage_path
        self._frameworks: Dict[str, ComplianceFramework] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_frameworks()

    def _load_frameworks(self):
        """Load compliance frameworks from storage."""
        frameworks_file = os.path.join(self.storage_path, "frameworks.json")
        if os.path.exists(frameworks_file):
            try:
                with open(frameworks_file) as f:
                    data = json.load(f)
                for fw_data in data.get("frameworks", []):
                    controls = [ComplianceControl(**c) for c in fw_data.get("controls", [])]
                    self._frameworks[fw_data["name"]] = ComplianceFramework(
                        name=fw_data["name"],
                        version=fw_data["version"],
                        description=fw_data["description"],
                        controls=controls,
                    )
                logger.info("Loaded %d compliance frameworks", len(self._frameworks))
            except Exception as e:
                logger.error("Failed to load frameworks: %s", e)

        # Initialize default frameworks if none loaded
        if not self._frameworks:
            self._init_default_frameworks()

    def _init_default_frameworks(self):
        """Initialize default compliance frameworks with controls."""
        self._frameworks = {
            "SOC2": ComplianceFramework(
                name="SOC 2 Type II",
                version="2023",
                description="Service Organization Control 2 — Trust Services Criteria",
                controls=[
                    ComplianceControl("CC6.1", "Logical and Physical Access", "Controls over logical access", ["SOC2-CC6.1", "FedRAMP-IA-5", "HIPAA-164.312(a)(1)"], "implemented"),
                    ComplianceControl("CC6.3", "Role-based Access", "Role-based access controls", ["SOC2-CC6.3", "FedRAMP-AC-6", "ISO27001-A.9.2.3"], "implemented"),
                    ComplianceControl("CC6.7", "Encryption at Rest", "Data encryption at rest", ["SOC2-CC6.7", "FedRAMP-SC-28", "HIPAA-164.312(a)(2)(iv)"], "implemented"),
                    ComplianceControl("CC7.1", "Security Monitoring", "Continuous security monitoring", ["SOC2-CC7.1", "FedRAMP-SI-4", "PCI DSS-10.2"], "implemented"),
                    ComplianceControl("CC7.2", "Incident Response", "Incident response procedures", ["SOC2-CC7.2", "FedRAMP-IR-4", "HIPAA-164.308(a)(6)"], "partial"),
                    ComplianceControl("CC8.1", "Change Management", "Change management controls", ["SOC2-CC8.1", "FedRAMP-CM-3", "ISO27001-A.12.1.2"], "implemented"),
                ],
            ),
            "FedRAMP": ComplianceFramework(
                name="FedRAMP Moderate",
                version="5.0",
                description="Federal Risk and Authorization Management Program — NIST SP 800-53",
                controls=[
                    ComplianceControl("AC-2", "Account Management", "Account lifecycle management", ["FedRAMP-AC-2", "SOC2-CC6.1"], "implemented"),
                    ComplianceControl("AC-6", "Least Privilege", "Least privilege principle", ["FedRAMP-AC-6", "SOC2-CC6.3"], "implemented"),
                    ComplianceControl("AU-2", "Audit Events", "Auditable events definition", ["FedRAMP-AU-2", "SOC2-CC3.1"], "implemented"),
                    ComplianceControl("AU-3", "Audit Content", "Audit record content", ["FedRAMP-AU-3", "SOC2-CC3.2"], "implemented"),
                    ComplianceControl("AU-6", "Audit Review", "Audit review and analysis", ["FedRAMP-AU-6", "SOC2-CC3.3"], "partial"),
                    ComplianceControl("SC-13", "Cryptography", "Cryptographic protections", ["FedRAMP-SC-13", "HIPAA-164.312(a)(2)(iv)"], "implemented"),
                    ComplianceControl("SC-28", "Protection at Rest", "Protection of information at rest", ["FedRAMP-SC-28", "SOC2-CC6.7"], "implemented"),
                    ComplianceControl("SI-4", "System Monitoring", "System monitoring", ["FedRAMP-SI-4", "SOC2-CC7.1"], "implemented"),
                ],
            ),
            "HIPAA": ComplianceFramework(
                name="HIPAA Security Rule",
                version="2023",
                description="Health Insurance Portability and Accountability Act",
                controls=[
                    ComplianceControl("164.308(a)(1)", "Security Management", "Risk analysis and management", ["HIPAA-164.308(a)(1)", "ISO27001-A.5.1"], "implemented"),
                    ComplianceControl("164.308(a)(4)", "Access Control", "Access authorization and establishment", ["HIPAA-164.308(a)(4)", "SOC2-CC6.1"], "implemented"),
                    ComplianceControl("164.308(a)(6)", "Incident Response", "Security incident procedures", ["HIPAA-164.308(a)(6)", "SOC2-CC7.2"], "partial"),
                    ComplianceControl("164.312(a)(1)", "Unique User ID", "Unique user identification", ["HIPAA-164.312(a)(1)", "FedRAMP-IA-5"], "implemented"),
                    ComplianceControl("164.312(a)(2)(iv)", "Encryption", "Encryption of ePHI", ["HIPAA-164.312(a)(2)(iv)", "FedRAMP-SC-13"], "implemented"),
                    ComplianceControl("164.312(b)", "Audit Controls", "Audit control mechanisms", ["HIPAA-164.312(b)", "SOC2-CC3.1"], "implemented"),
                    ComplianceControl("164.312(c)(1)", "Integrity Controls", "Integrity controls for ePHI", ["HIPAA-164.312(c)(1)", "FedRAMP-SI-7"], "implemented"),
                    ComplianceControl("164.312(d)", "Transmission Security", "Transmission security", ["HIPAA-164.312(d)", "FedRAMP-SC-8"], "implemented"),
                ],
            ),
            "GDPR": ComplianceFramework(
                name="GDPR",
                version="2018",
                description="General Data Protection Regulation",
                controls=[
                    ComplianceControl("Art. 5", "Data Processing Principles", "Lawful, fair, transparent processing", ["GDPR-Art.5"], "implemented"),
                    ComplianceControl("Art. 7", "Consent", "Conditions for consent", ["GDPR-Art.7"], "partial"),
                    ComplianceControl("Art. 17", "Right to Erasure", "Right to be forgotten", ["GDPR-Art.17"], "partial"),
                    ComplianceControl("Art. 20", "Data Portability", "Right to data portability", ["GDPR-Art.20"], "implemented"),
                    ComplianceControl("Art. 25", "Data Protection by Design", "Privacy by design and default", ["GDPR-Art.25"], "implemented"),
                    ComplianceControl("Art. 32", "Security of Processing", "Security measures", ["GDPR-Art.32", "SOC2-CC6.1"], "implemented"),
                    ComplianceControl("Art. 33", "Breach Notification", "Data breach notification", ["GDPR-Art.33", "HIPAA-164.308(a)(6)"], "partial"),
                    ComplianceControl("Art. 35", "DPIA", "Data Protection Impact Assessment", ["GDPR-Art.35"], "planned"),
                ],
            ),
            "PCI_DSS": ComplianceFramework(
                name="PCI DSS v4.0",
                version="4.0",
                description="Payment Card Industry Data Security Standard",
                controls=[
                    ComplianceControl("3.4", "Cardholder Data Storage", "Render PAN unreadable", ["PCI-3.4", "FedRAMP-SC-28"], "implemented"),
                    ComplianceControl("3.5", "Key Management", "Protect cryptographic keys", ["PCI-3.5", "ISO27001-A.10.1"], "implemented"),
                    ComplianceControl("4.1", "Transmission Security", "Encrypt cardholder data in transit", ["PCI-4.1", "FedRAMP-SC-8"], "implemented"),
                    ComplianceControl("6.2", "Vulnerability Management", "Patch management", ["PCI-6.2", "FedRAMP-SI-2"], "partial"),
                    ComplianceControl("10.2", "Audit Trails", "Audit trail for system components", ["PCI-10.2", "SOC2-CC3.1"], "implemented"),
                    ComplianceControl("10.5", "Audit Trail Protection", "Protect audit trails from modification", ["PCI-10.5", "SOC2-CC3.4"], "implemented"),
                ],
            ),
            "EU_AI_Act": ComplianceFramework(
                name="EU AI Act",
                version="2024",
                description="European Union Artificial Intelligence Act",
                controls=[
                    ComplianceControl("Art. 9", "Risk Management", "Risk management system", ["EU-AI-Art.9"], "implemented"),
                    ComplianceControl("Art. 13", "Transparency", "Transparency and provision of information", ["EU-AI-Art.13"], "implemented"),
                    ComplianceControl("Art. 14", "Human Oversight", "Human oversight measures", ["EU-AI-Art.14"], "implemented"),
                    ComplianceControl("Art. 15", "Accuracy", "Accuracy, robustness, and cybersecurity", ["EU-AI-Art.15"], "implemented"),
                    ComplianceControl("Art. 10", "Data Governance", "Data and data governance", ["EU-AI-Art.10"], "partial"),
                    ComplianceControl("Art. 12", "Documentation", "Technical documentation", ["EU-AI-Art.12"], "partial"),
                ],
            ),
        }
        self._save_frameworks()
        logger.info("Initialized %d default compliance frameworks", len(self._frameworks))

    def _save_frameworks(self):
        """Save compliance frameworks to storage."""
        try:
            frameworks_file = os.path.join(self.storage_path, "frameworks.json")
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "frameworks": [
                    {
                        "name": fw.name,
                        "version": fw.version,
                        "description": fw.description,
                        "controls": [asdict(c) for c in fw.controls],
                    }
                    for fw in self._frameworks.values()
                ],
            }
            with open(frameworks_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save frameworks: %s", e)

    def get_framework(self, name: str) -> Optional[ComplianceFramework]:
        """Get a compliance framework by name."""
        return self._frameworks.get(name)

    def get_all_frameworks(self) -> Dict[str, ComplianceFramework]:
        """Get all compliance frameworks."""
        return self._frameworks

    def get_control(self, control_id: str) -> Optional[ComplianceControl]:
        """Find a control by ID across all frameworks."""
        for fw in self._frameworks.values():
            for c in fw.controls:
                if c.control_id == control_id:
                    return c
        return None

    def update_control_status(self, control_id: str, status: str, evidence_path: Optional[str] = None):
        """Update the status of a compliance control."""
        control = self.get_control(control_id)
        if control:
            control.status = status
            control.last_validated = datetime.now(timezone.utc).isoformat()
            if evidence_path:
                control.evidence_path = evidence_path
            self._save_frameworks()
            logger.info("Control %s status updated to %s", control_id, status)

    def get_gap_analysis(self) -> Dict[str, List[ComplianceControl]]:
        """Get compliance gaps (controls not fully implemented)."""
        gaps = {}
        for fw_name, fw in self._frameworks.items():
            gaps[fw_name] = [c for c in fw.controls if c.status in ("partial", "planned")]
        return gaps

    def get_compliance_score(self, framework_name: str) -> float:
        """Get compliance score (0.0 to 1.0) for a framework."""
        fw = self._frameworks.get(framework_name)
        if not fw or not fw.controls:
            return 0.0
        implemented = sum(1 for c in fw.controls if c.status == "implemented")
        return implemented / len(fw.controls)

    def get_overall_compliance_score(self) -> Dict[str, float]:
        """Get compliance scores for all frameworks."""
        return {
            name: self.get_compliance_score(name)
            for name in self._frameworks
        }

    def collect_evidence(self, control_id: str, evidence_data: Dict[str, Any]) -> bool:
        """Collect evidence for a compliance control."""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            evidence_file = os.path.join(self.storage_path, f"evidence_{control_id}_{timestamp}.json")
            evidence = {
                "control_id": control_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": evidence_data,
            }
            with open(evidence_file, "w") as f:
                json.dump(evidence, f, indent=2, default=str)
            self.update_control_status(control_id, "implemented", evidence_file)
            logger.info("Evidence collected for control %s", control_id)
            return True
        except Exception as e:
            logger.error("Failed to collect evidence for %s: %s", control_id, e)
            return False

    def generate_report(self, framework_name: str) -> dict:
        """Generate a compliance report for a framework."""
        fw = self._frameworks.get(framework_name)
        if not fw:
            return {"error": f"Framework {framework_name} not found"}

        return {
            "framework": fw.name,
            "version": fw.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_controls": len(fw.controls),
            "implemented": sum(1 for c in fw.controls if c.status == "implemented"),
            "partial": sum(1 for c in fw.controls if c.status == "partial"),
            "planned": sum(1 for c in fw.controls if c.status == "planned"),
            "not_applicable": sum(1 for c in fw.controls if c.status == "not_applicable"),
            "compliance_score": self.get_compliance_score(framework_name),
            "controls": [asdict(c) for c in fw.controls],
            "gaps": [asdict(c) for c in self.get_gap_analysis().get(framework_name, [])],
        }


# Singleton instance
_compliance_manager: Optional[ComplianceManager] = None


def get_compliance_manager() -> ComplianceManager:
    """Get or create the singleton compliance manager."""
    global _compliance_manager
    if _compliance_manager is None:
        _compliance_manager = ComplianceManager()
    return _compliance_manager


def get_compliance_report(framework: str = "SOC2") -> dict:
    """Get a compliance report for a specific framework."""
    return get_compliance_manager().generate_report(framework)


def get_all_compliance_scores() -> Dict[str, float]:
    """Get compliance scores for all frameworks."""
    return get_compliance_manager().get_overall_compliance_score()
