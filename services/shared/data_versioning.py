"""Data versioning for NorthGuard.
Enterprise-grade: Content-addressed data snapshots, version tracking,
and reproducibility support for training datasets.

Simple file-based approach — no external DVC dependency required.
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Default snapshot directory
SNAPSHOT_DIR = os.getenv("DATA_SNAPSHOT_DIR", "/data/snapshots")


def compute_content_hash(data: List[Dict[str, Any]]) -> str:
    """Compute a content-addressed hash for a dataset.

    Uses SHA-256 over the sorted JSON representation to ensure
    deterministic hashing regardless of input order.

    Args:
        data: List of data records (dicts)

    Returns:
        SHA-256 hex digest
    """
    # Sort by canonical JSON representation for deterministic hashing
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_record_hash(record: Dict[str, Any]) -> str:
    """Compute a hash for a single data record.

    Args:
        record: A single data record

    Returns:
        SHA-256 hex digest
    """
    serialized = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


class DataVersion:
    """Represents a versioned snapshot of training/evaluation data."""

    def __init__(
        self,
        version_id: str,
        content_hash: str,
        record_count: int,
        created_at: str,
        metadata: Optional[Dict[str, Any]] = None,
        parent_version: Optional[str] = None,
    ):
        self.version_id = version_id
        self.content_hash = content_hash
        self.record_count = record_count
        self.created_at = created_at
        self.metadata = metadata or {}
        self.parent_version = parent_version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "content_hash": self.content_hash,
            "record_count": self.record_count,
            "created_at": self.created_at,
            "parent_version": self.parent_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataVersion":
        return cls(
            version_id=data["version_id"],
            content_hash=data["content_hash"],
            record_count=data["record_count"],
            created_at=data["created_at"],
            metadata=data.get("metadata", {}),
            parent_version=data.get("parent_version"),
        )


class DataVersionManager:
    """Manages data versioning and snapshots for ML datasets.

    Creates content-addressed snapshots, tracks version history,
    and provides reproducibility support.
    """

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        self._versions: Dict[str, DataVersion] = {}
        self._current_version: Optional[str] = None
        self._ensure_snapshot_dir()

    def _ensure_snapshot_dir(self) -> None:
        """Create snapshot directory if it doesn't exist."""
        try:
            os.makedirs(self.snapshot_dir, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create snapshot directory {self.snapshot_dir}: {e}")

    def _load_manifest(self) -> Dict[str, Any]:
        """Load the version manifest file."""
        manifest_path = os.path.join(self.snapshot_dir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load manifest: {e}")
        return {"versions": [], "current": None}

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Save the version manifest file."""
        manifest_path = os.path.join(self.snapshot_dir, "manifest.json")
        try:
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2, default=str)
        except OSError as e:
            logger.warning(f"Failed to save manifest: {e}")

    def create_snapshot(
        self,
        data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        parent_version: Optional[str] = None,
    ) -> Optional[DataVersion]:
        """Create a new versioned snapshot of the given data.

        Args:
            data: List of data records to snapshot
            metadata: Optional metadata about this snapshot
            parent_version: Optional parent version ID

        Returns:
            DataVersion if snapshot was created, None otherwise
        """
        if not data:
            logger.warning("Cannot create snapshot from empty data")
            return None

        content_hash = compute_content_hash(data)
        version_id = f"v{int(time.time())}_{content_hash[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Check if this content already exists
        manifest = self._load_manifest()
        for existing in manifest.get("versions", []):
            if existing.get("content_hash") == content_hash:
                logger.info(f"Snapshot already exists: {existing['version_id']}")
                version = DataVersion.from_dict(existing)
                self._versions[version.version_id] = version
                return version

        # Save snapshot data
        snapshot_path = os.path.join(self.snapshot_dir, f"{version_id}.json")
        try:
            with open(snapshot_path, "w") as f:
                json.dump(data, f, default=str)
        except OSError as e:
            logger.error(f"Failed to save snapshot {version_id}: {e}")
            return None

        # Create version record
        version = DataVersion(
            version_id=version_id,
            content_hash=content_hash,
            record_count=len(data),
            created_at=created_at,
            metadata=metadata or {},
            parent_version=parent_version or self._current_version,
        )

        # Update manifest
        manifest["versions"].append(version.to_dict())
        manifest["current"] = version_id
        self._save_manifest(manifest)

        self._versions[version_id] = version
        self._current_version = version_id

        logger.info(
            f"Created data snapshot {version_id}: "
            f"{version.record_count} records, hash={content_hash[:16]}..."
        )
        return version

    def load_snapshot(self, version_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load data from a specific snapshot version.

        Args:
            version_id: Version ID to load

        Returns:
            List of data records, or None if not found
        """
        snapshot_path = os.path.join(self.snapshot_dir, f"{version_id}.json")
        if not os.path.exists(snapshot_path):
            logger.warning(f"Snapshot {version_id} not found")
            return None

        try:
            with open(snapshot_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load snapshot {version_id}: {e}")
            return None

    def get_version(self, version_id: str) -> Optional[DataVersion]:
        """Get metadata for a specific version.

        Args:
            version_id: Version ID to look up

        Returns:
            DataVersion if found, None otherwise
        """
        if version_id in self._versions:
            return self._versions[version_id]

        # Check manifest
        manifest = self._load_manifest()
        for v in manifest.get("versions", []):
            if v["version_id"] == version_id:
                version = DataVersion.from_dict(v)
                self._versions[version_id] = version
                return version
        return None

    def get_current_version(self) -> Optional[DataVersion]:
        """Get the current (latest) version.

        Returns:
            DataVersion for the current version, or None
        """
        manifest = self._load_manifest()
        current_id = manifest.get("current")
        if current_id:
            return self.get_version(current_id)
        return None

    def get_version_history(self, limit: int = 10) -> List[DataVersion]:
        """Get version history, most recent first.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of DataVersion objects
        """
        manifest = self._load_manifest()
        versions = []
        for v in reversed(manifest.get("versions", [])):
            versions.append(DataVersion.from_dict(v))
            if len(versions) >= limit:
                break
        return versions

    def get_data_hash(self, data: List[Dict[str, Any]]) -> str:
        """Compute the content hash for a dataset without creating a snapshot.

        Useful for logging data versions in MLflow runs.

        Args:
            data: List of data records

        Returns:
            SHA-256 hex digest
        """
        return compute_content_hash(data)

    def add_record_hash(self, record: Dict[str, Any]) -> str:
        """Add a content hash to a record for traceability.

        Args:
            record: Data record to hash

        Returns:
            Hash string (first 16 chars of SHA-256)
        """
        return compute_record_hash(record)


# Module-level singleton
_manager: Optional[DataVersionManager] = None


def get_data_version_manager() -> DataVersionManager:
    """Get or create the global DataVersionManager instance."""
    global _manager
    if _manager is None:
        _manager = DataVersionManager()
    return _manager
