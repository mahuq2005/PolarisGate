"""MLflow experiment tracking integration for NorthGuard.
Enterprise-grade: Tracks model training runs, parameters, metrics, and artifacts
for reproducibility and model governance.

Supports graceful degradation when MLflow server is unavailable.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "northguard-models")


class MLflowTracker:
    """MLflow experiment tracking wrapper with graceful fallback.

    All methods are safe to call even when MLflow is not configured.
    When MLflow is unavailable, operations are silently skipped with a
    debug-level log message.
    """

    def __init__(self, tracking_uri: str = "", experiment_name: str = ""):
        self.tracking_uri = tracking_uri or MLFLOW_TRACKING_URI
        self.experiment_name = experiment_name or MLFLOW_EXPERIMENT_NAME
        self._mlflow = None
        self._active_run = None
        self._enabled = False
        self._init_attempted = False

    def _initialize(self) -> bool:
        """Lazy-initialize MLflow connection."""
        if self._init_attempted:
            return self._enabled
        self._init_attempted = True

        if not self.tracking_uri:
            logger.debug("MLflow tracking URI not configured, experiment tracking disabled")
            return False

        try:
            import mlflow
            self._mlflow = mlflow
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            self._enabled = True
            logger.info(f"MLflow tracking initialized: {self.tracking_uri} / {self.experiment_name}")
        except ImportError:
            logger.debug("mlflow package not installed, experiment tracking disabled")
        except Exception as e:
            logger.warning(f"MLflow initialization failed: {e}")
            self._enabled = False

        return self._enabled

    @property
    def enabled(self) -> bool:
        """Check if MLflow tracking is active."""
        return self._initialize()

    def start_run(self, run_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None) -> bool:
        """Start a new MLflow run.

        Args:
            run_name: Optional name for the run
            tags: Optional tags to attach to the run

        Returns:
            True if run started successfully, False otherwise
        """
        if not self._initialize():
            return False

        try:
            all_tags = {
                "source": "northguard",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if tags:
                all_tags.update(tags)

            self._active_run = self._mlflow.start_run(
                run_name=run_name,
                tags=all_tags,
            )
            logger.info(f"MLflow run started: {self._active_run.info.run_id}")
            return True
        except Exception as e:
            logger.warning(f"MLflow start_run failed: {e}")
            return False

    def end_run(self, status: str = "FINISHED") -> None:
        """End the current MLflow run."""
        if self._active_run and self._enabled:
            try:
                self._mlflow.end_run(status=status)
                logger.info(f"MLflow run ended: {status}")
            except Exception as e:
                logger.warning(f"MLflow end_run failed: {e}")
        self._active_run = None

    def log_param(self, key: str, value: Any) -> bool:
        """Log a single parameter.

        Args:
            key: Parameter name
            value: Parameter value

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.log_param(key, value)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_param failed: {e}")
            return False

    def log_params(self, params: Dict[str, Any]) -> bool:
        """Log multiple parameters at once.

        Args:
            params: Dict of parameter names to values

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.log_params(params)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_params failed: {e}")
            return False

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> bool:
        """Log a single metric.

        Args:
            key: Metric name
            value: Metric value
            step: Optional step number

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.log_metric(key, value, step=step)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_metric failed: {e}")
            return False

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> bool:
        """Log multiple metrics at once.

        Args:
            metrics: Dict of metric names to values
            step: Optional step number

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.log_metrics(metrics, step=step)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_metrics failed: {e}")
            return False

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None) -> bool:
        """Log a local file as an MLflow artifact.

        Args:
            local_path: Path to the local file
            artifact_path: Optional subdirectory within the artifact URI

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.log_artifact(local_path, artifact_path=artifact_path)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_artifact failed: {e}")
            return False

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: Optional[str] = None,
    ) -> bool:
        """Log a model as an MLflow artifact.

        Args:
            model: The model object to log
            artifact_path: Path within the artifact URI
            registered_model_name: Optional name for model registry

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            self._mlflow.pyfunc.log_model(
                artifact_path=artifact_path,
                python_model=model,
                registered_model_name=registered_model_name,
            )
            return True
        except Exception as e:
            logger.debug(f"MLflow log_model failed: {e}")
            return False

    def log_model_version_metrics(
        self,
        model_name: str,
        version: int,
        metrics: Dict[str, float],
    ) -> bool:
        """Log metrics for a specific model version in the registry.

        Args:
            model_name: Registered model name
            version: Model version number
            metrics: Dict of metric names to values

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            client = self._mlflow.MlflowClient()
            for key, value in metrics.items():
                client.log_metric(
                    run_id=self._active_run.info.run_id if self._active_run else None,
                    key=key,
                    value=value,
                )
            return True
        except Exception as e:
            logger.debug(f"MLflow log_model_version_metrics failed: {e}")
            return False

    def log_classification_report(
        self,
        report: Dict[str, Any],
        prefix: str = "",
    ) -> bool:
        """Log a classification report as individual metrics.

        Args:
            report: Dict with keys like precision, recall, f1-score, support
            prefix: Optional prefix for metric names

        Returns:
            True if logged successfully
        """
        if not self._enabled:
            return False
        try:
            metrics = {}
            for label, scores in report.items():
                if isinstance(scores, dict):
                    for metric_name, value in scores.items():
                        if isinstance(value, (int, float)):
                            metrics[f"{prefix}{label}_{metric_name}"] = value
            if metrics:
                self._mlflow.log_metrics(metrics)
            return True
        except Exception as e:
            logger.debug(f"MLflow log_classification_report failed: {e}")
            return False


# Module-level singleton for easy import
_tracker: Optional[MLflowTracker] = None


def get_mlflow_tracker() -> MLflowTracker:
    """Get or create the global MLflow tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = MLflowTracker()
    return _tracker


def log_model_training(
    model_name: str,
    params: Dict[str, Any],
    metrics: Dict[str, float],
    tags: Optional[Dict[str, str]] = None,
) -> bool:
    """Convenience function to log a complete model training run.

    Args:
        model_name: Name of the model being trained
        params: Training parameters
        metrics: Evaluation metrics
        tags: Optional tags

    Returns:
        True if logged successfully
    """
    tracker = get_mlflow_tracker()
    if not tracker.start_run(run_name=f"train_{model_name}", tags=tags):
        return False

    try:
        tracker.log_params(params)
        tracker.log_metrics(metrics)
        return True
    finally:
        tracker.end_run()
