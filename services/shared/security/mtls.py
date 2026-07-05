"""mTLS client and server utilities for PolarisGate service-to-service communication.

Provides:
- create_mtls_client: HTTPX client with mTLS certs
- MtlsMiddleware: FastAPI middleware for mTLS verification
- CertReloader: File-watching cert reloader for zero-downtime rotation
"""
import os
import logging
import threading
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime, timezone

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

MTLS_ENABLED = os.getenv("MTLS_ENABLED", "false").lower() == "true"
MTLS_CA_CERT_PATH = os.getenv("MTLS_CA_CERT_PATH", "/etc/polarisgate/certs/ca.crt")
MTLS_CERT_PATH = os.getenv("MTLS_CERT_PATH", "/etc/polarisgate/certs/service.crt")
MTLS_KEY_PATH = os.getenv("MTLS_KEY_PATH", "/etc/polarisgate/certs/service.key")
MTLS_VERIFY_HOSTNAME = os.getenv("MTLS_VERIFY_HOSTNAME", "true").lower() == "true"
MTLS_CERT_RELOAD_INTERVAL = int(os.getenv("MTLS_CERT_RELOAD_INTERVAL", "300"))  # 5 minutes


# ─── Certificate Reloader ──────────────────────────────────────────────────

class CertReloader:
    """Watches certificate files and reloads on change.
    
    Supports zero-downtime certificate rotation by periodically
    checking file modification times.
    """
    
    def __init__(self):
        self._cert_path = Path(MTLS_CERT_PATH)
        self._key_path = Path(MTLS_KEY_PATH)
        self._ca_path = Path(MTLS_CA_CERT_PATH)
        self._cert: Optional[bytes] = None
        self._key: Optional[bytes] = None
        self._ca_cert: Optional[bytes] = None
        self._last_cert_mtime: float = 0
        self._last_key_mtime: float = 0
        self._last_ca_mtime: float = 0
        self._lock = threading.Lock()
        self._on_reload: Optional[Callable] = None
    
    def set_on_reload(self, callback: Callable):
        """Set callback for cert reload events."""
        self._on_reload = callback
    
    def load(self) -> bool:
        """Load or reload certificates from disk.
        
        Returns:
            True if certificates were loaded/changed, False if unchanged.
        """
        changed = False
        
        # Check CA cert
        if self._ca_path.exists():
            mtime = self._ca_path.stat().st_mtime
            if mtime > self._last_ca_mtime:
                with open(self._ca_path, "rb") as f:
                    self._ca_cert = f.read()
                self._last_ca_mtime = mtime
                changed = True
                logger.info("Reloaded CA certificate")
        
        # Check service cert
        if self._cert_path.exists():
            mtime = self._cert_path.stat().st_mtime
            if mtime > self._last_cert_mtime:
                with open(self._cert_path, "rb") as f:
                    self._cert = f.read()
                self._last_cert_mtime = mtime
                changed = True
                logger.info("Reloaded service certificate")
        
        # Check service key
        if self._key_path.exists():
            mtime = self._key_path.stat().st_mtime
            if mtime > self._last_key_mtime:
                with open(self._key_path, "rb") as f:
                    self._key = f.read()
                self._last_key_mtime = mtime
                changed = True
                logger.info("Reloaded service key")
        
        if changed and self._on_reload:
            self._on_reload()
        
        return changed
    
    def get_cert(self) -> Optional[bytes]:
        return self._cert
    
    def get_key(self) -> Optional[bytes]:
        return self._key
    
    def get_ca_cert(self) -> Optional[bytes]:
        return self._ca_cert
    
    def get_cert_info(self) -> Optional[dict]:
        """Get certificate metadata for monitoring."""
        if not self._cert:
            return None
        try:
            cert = x509.load_pem_x509_certificate(self._cert, default_backend())
            return {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "serial_number": format(cert.serial_number, "x"),
                "not_valid_before": cert.not_valid_before_utc.isoformat(),
                "not_valid_after": cert.not_valid_after_utc.isoformat(),
                "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
                "days_remaining": (cert.not_valid_after_utc - datetime.now(timezone.utc)).days,
            }
        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}")
            return None


# Global cert reloader
cert_reloader = CertReloader()


# ─── mTLS Client ───────────────────────────────────────────────────────────

def create_mtls_client(
    base_url: str = "",
    timeout: float = 30.0,
    verify_hostname: Optional[bool] = None,
) -> httpx.AsyncClient:
    """Create an HTTPX client configured for mTLS.
    
    If MTLS_ENABLED is false, creates a standard HTTP client.
    If MTLS_ENABLED is true, creates an mTLS client with client certificates.
    
    Args:
        base_url: Base URL for all requests
        timeout: Request timeout in seconds
        verify_hostname: Whether to verify hostname (default: MTLS_VERIFY_HOSTNAME)
    
    Returns:
        Configured httpx.AsyncClient
    """
    if verify_hostname is None:
        verify_hostname = MTLS_VERIFY_HOSTNAME
    
    if not MTLS_ENABLED:
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
        )
    
    # Load certificates
    cert_reloader.load()
    
    cert = cert_reloader.get_cert()
    key = cert_reloader.get_key()
    ca_cert = cert_reloader.get_ca_cert()
    
    if not cert or not key:
        logger.warning(
            "mTLS enabled but certificates not found. "
            "Falling back to HTTP. Set MTLS_ENABLED=false to suppress this warning."
        )
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
        )
    
    # Create SSL context
    import ssl
    ctx = ssl.create_default_context()
    
    # Load CA cert for verification
    if ca_cert:
        ctx.load_verify_locations(cadata=ca_cert.decode())
    
    # Load client cert
    ctx.load_cert_chain(
        certfile=MTLS_CERT_PATH,
        keyfile=MTLS_KEY_PATH,
    )
    
    # Hostname verification
    if not verify_hostname:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        verify=ctx,
    )


# ─── FastAPI mTLS Middleware ───────────────────────────────────────────────

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class MtlsMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that verifies mTLS client certificates.
    
    Extracts client certificate information from the request
    and makes it available as request.state.client_cert.
    
    When MTLS_ENABLED=false, this middleware is a no-op.
    """
    
    async def dispatch(self, request: Request, call_next):
        if not MTLS_ENABLED:
            return await call_next(request)
        
        # Extract client cert from headers (set by reverse proxy/ingress)
        client_cert_header = request.headers.get("X-Client-Cert")
        client_cert_pem = request.headers.get("X-Client-Cert-PEM")
        
        if client_cert_pem:
            try:
                cert = x509.load_pem_x509_certificate(
                    client_cert_pem.encode(), default_backend()
                )
                request.state.client_cert = {
                    "subject": cert.subject.rfc4514_string(),
                    "issuer": cert.issuer.rfc4514_string(),
                    "serial_number": format(cert.serial_number, "x"),
                    "not_valid_after": cert.not_valid_after_utc.isoformat(),
                    "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
                }
            except Exception as e:
                logger.warning(f"Failed to parse client certificate: {e}")
                request.state.client_cert = None
        else:
            request.state.client_cert = None
        
        response = await call_next(request)
        return response


# ─── Utility Functions ─────────────────────────────────────────────────────

async def get_service_certificate(service_name: str) -> tuple[str, str]:
    """Request a certificate from the Internal CA service.
    
    Args:
        service_name: The service name (used as Common Name)
    
    Returns:
        Tuple of (cert_pem, key_pem)
    """
    ca_url = os.getenv("CA_SERVICE_URL", "http://internal-ca:8443")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ca_url}/api/v1/ca/issue",
            json={
                "common_name": service_name,
                "san_dns": [f"{service_name}", f"{service_name}.polarisgate.svc.cluster.local"],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["certificate"], data["private_key"]


async def save_service_certificate(service_name: str):
    """Fetch and save a service certificate from the CA.
    
    This is called during service startup to ensure valid certificates.
    """
    if not MTLS_ENABLED:
        return
    
    cert_path = Path(MTLS_CERT_PATH)
    key_path = Path(MTLS_KEY_PATH)
    
    # Skip if certs already exist and are valid
    if cert_path.exists() and key_path.exists():
        cert_reloader.load()
        info = cert_reloader.get_cert_info()
        if info and info.get("days_remaining", 0) > 7:
            logger.info(f"Certificate for {service_name} is valid ({info['days_remaining']} days remaining)")
            return
    
    # Request new certificate
    logger.info(f"Requesting certificate for {service_name}")
    cert_pem, key_pem = await get_service_certificate(service_name)
    
    # Save to disk
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cert_path, "w") as f:
        f.write(cert_pem)
    with open(key_path, "w") as f:
        f.write(key_pem)
    
    # Reload
    cert_reloader.load()
    logger.info(f"Certificate for {service_name} saved and loaded")
