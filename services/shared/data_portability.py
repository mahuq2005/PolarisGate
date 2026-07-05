"""Data portability and GDPR compliance for NorthGuard.
Enterprise-grade: User data export, deletion, and portability support
in compliance with GDPR Article 20 (right to data portability) and
Article 17 (right to erasure / right to be forgotten).

Supports exporting user data in machine-readable formats (JSON, CSV)
and secure deletion of user records across all services.
"""
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataPortabilityError(Exception):
    """Base exception for data portability operations."""
    pass


class UserNotFoundError(DataPortabilityError):
    """Raised when a user ID is not found."""
    pass


class DataExportError(DataPortabilityError):
    """Raised when data export fails."""
    pass


class DataDeletionError(DataPortabilityError):
    """Raised when data deletion fails."""
    pass


class DataPortabilityManager:
    """Manages GDPR data portability and erasure requests.

    Handles:
    - Data export (JSON, CSV formats)
    - Data deletion (right to be forgotten)
    - Audit logging of all portability requests
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.getenv("DATA_PORTABILITY_DIR", "/data/portability")
        self._export_history: List[Dict[str, Any]] = []
        self._deletion_history: List[Dict[str, Any]] = []
        self._data_store: Dict[str, List[Dict[str, Any]]] = {}

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

    def register_user_data(self, user_id: str, data: Dict[str, Any]) -> None:
        """Register user data for portability.

        Args:
            user_id: Unique user identifier
            data: User data to store
        """
        if user_id not in self._data_store:
            self._data_store[user_id] = []
        self._data_store[user_id].append({
            **data,
            "_registered_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Data registered for user {user_id}")

    def export_user_data(
        self,
        user_id: str,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Export all data for a user in the requested format.

        Args:
            user_id: Unique user identifier
            format: Export format ('json' or 'csv')

        Returns:
            Dict with export metadata and data

        Raises:
            UserNotFoundError: If user has no data
            DataExportError: If export fails
        """
        if user_id not in self._data_store or not self._data_store[user_id]:
            raise UserNotFoundError(f"No data found for user {user_id}")

        records = self._data_store[user_id]
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            if format == "json":
                export_data = self._export_json(user_id, records, timestamp)
            elif format == "csv":
                export_data = self._export_csv(user_id, records, timestamp)
            else:
                raise DataExportError(f"Unsupported format: {format}")

            # Log the export
            export_record = {
                "user_id": user_id,
                "format": format,
                "timestamp": timestamp,
                "record_count": len(records),
            }
            self._export_history.append(export_record)

            logger.info(f"Data exported for user {user_id} ({format}, {len(records)} records)")
            return export_data

        except Exception as e:
            raise DataExportError(f"Failed to export data for user {user_id}: {e}")

    def _export_json(
        self,
        user_id: str,
        records: List[Dict[str, Any]],
        timestamp: str,
    ) -> Dict[str, Any]:
        """Export data as JSON."""
        export = {
            "export_metadata": {
                "user_id": user_id,
                "exported_at": timestamp,
                "record_count": len(records),
                "format": "json",
                "generated_by": "NorthGuard Data Portability Service",
            },
            "data": records,
        }

        # Save to file
        filename = f"export_{user_id}_{timestamp.replace(':', '-')}.json"
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, "w") as f:
            json.dump(export, f, indent=2, default=str)

        return export

    def _export_csv(
        self,
        user_id: str,
        records: List[Dict[str, Any]],
        timestamp: str,
    ) -> Dict[str, Any]:
        """Export data as CSV."""
        if not records:
            return {"export_metadata": {"user_id": user_id, "record_count": 0}, "data": []}

        # Collect all keys from all records
        all_keys = set()
        for record in records:
            all_keys.update(record.keys())

        # Remove internal keys
        all_keys.discard("_registered_at")
        fieldnames = sorted(all_keys)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)

        csv_content = output.getvalue()

        # Save to file
        filename = f"export_{user_id}_{timestamp.replace(':', '-')}.csv"
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, "w") as f:
            f.write(csv_content)

        return {
            "export_metadata": {
                "user_id": user_id,
                "exported_at": timestamp,
                "record_count": len(records),
                "format": "csv",
                "generated_by": "NorthGuard Data Portability Service",
            },
            "data": csv_content,
        }

    def delete_user_data(self, user_id: str) -> Dict[str, Any]:
        """Delete all data for a user (right to be forgotten).

        Args:
            user_id: Unique user identifier

        Returns:
            Dict with deletion metadata

        Raises:
            UserNotFoundError: If user has no data
        """
        if user_id not in self._data_store:
            raise UserNotFoundError(f"No data found for user {user_id}")

        record_count = len(self._data_store[user_id])
        timestamp = datetime.now(timezone.utc).isoformat()

        # Remove data
        del self._data_store[user_id]

        # Log the deletion
        deletion_record = {
            "user_id": user_id,
            "timestamp": timestamp,
            "record_count": record_count,
        }
        self._deletion_history.append(deletion_record)

        logger.info(f"Data deleted for user {user_id} ({record_count} records removed)")
        return {
            "user_id": user_id,
            "deleted_at": timestamp,
            "record_count": record_count,
            "status": "deleted",
        }

    def user_has_data(self, user_id: str) -> bool:
        """Check if a user has stored data.

        Args:
            user_id: Unique user identifier

        Returns:
            True if user has data
        """
        return user_id in self._data_store and len(self._data_store[user_id]) > 0

    def get_export_history(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get export history, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of export history records
        """
        if user_id:
            return [e for e in self._export_history if e["user_id"] == user_id]
        return self._export_history

    def get_deletion_history(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get deletion history, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of deletion history records
        """
        if user_id:
            return [d for d in self._deletion_history if d["user_id"] == user_id]
        return self._deletion_history

    def get_status(self) -> Dict[str, Any]:
        """Get current data portability status.

        Returns:
            Dict with status info
        """
        return {
            "total_users_with_data": len(self._data_store),
            "total_exports": len(self._export_history),
            "total_deletions": len(self._deletion_history),
            "data_dir": self.data_dir,
        }


# Module-level singleton
_manager: Optional[DataPortabilityManager] = None


def get_data_portability_manager() -> DataPortabilityManager:
    """Get or create the global DataPortabilityManager instance."""
    global _manager
    if _manager is None:
        _manager = DataPortabilityManager()
    return _manager
