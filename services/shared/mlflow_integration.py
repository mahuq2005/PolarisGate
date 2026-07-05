"""MLflow integration layer for NorthGuard.
Enterprise-grade: Connects drift detection, model evaluation, and cost tracking
to MLflow for experiment tracking and model governance.

All operations gracefully degrade when MLflow is unavailable.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.mlflow_client import get_mlflow_tracker, MLflowTracker
from shared.drift_detector import DriftDetector
from shared.model_evaluator import evaluate_classifier, ClassificationMetrics
from shared.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class MLflowIntegration:
    """Wires MLflow tracking into NorthGuard's ML pipeline.

    Connects drift detection alerts, model evaluation results, and cost
    tracking metrics to MLflow runs for centralized experiment management.
    """

    def __init__(self, tracker: Optional[MLflowTracker] = None):
        self.tracker = tracker or get_mlflow_tracker()

    def log_drift_alert(self, alert: Dict[str, Any]) -> bool:
        """Log a drift detection alert as an MLflow run.

        Args:
            alert: Drift alert dict from DriftDetector

        Returns:
            True if logged successfully
        """
        if not self.tracker.enabled:
            return False

        run_name = f"drift_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        if not self.tracker.start_run(run_name=run_name, tags={"type": "drift_detection"}):
            return False

        try:
            # Log drift metrics
            metrics = {
                "psi": alert.get("psi", 0.0),
                "kl_divergence": alert.get("kl_divergence", 0.0),
                "current_toxicity_rate": alert.get("current_toxicity_rate", 0.0),
                "baseline_toxicity_rate": alert.get("baseline_toxicity_rate", 0.0) or 0.0,
                "window_size": float(alert.get("window_size", 0)),
                "baseline_size": float(alert.get("baseline_size", 0)),
            }
            self.tracker.log_metrics(metrics)

            # Log alert details as params
            sub_alerts = alert.get("alerts", [])
            for i, sub in enumerate(sub_alerts):
                self.tracker.log_param(f"alert_{i}_type", sub.get("type", "unknown"))
                self.tracker.log_param(f"alert_{i}_severity", sub.get("severity", "info"))
                self.tracker.log_param(f"alert_{i}_metric", sub.get("metric", "unknown"))
                self.tracker.log_param(f"alert_{i}_value", str(sub.get("value", "")))

            self.tracker.log_param("drift_detected", str(alert.get("drift_detected", False)))
            self.tracker.log_param("alert_count", str(len(sub_alerts)))

            logger.info(f"Drift alert logged to MLflow: PSI={metrics['psi']:.3f}")
            return True
        except Exception as e:
            logger.debug(f"Failed to log drift alert to MLflow: {e}")
            return False
        finally:
            self.tracker.end_run()

    def log_model_evaluation(
        self,
        model_name: str,
        eval_results: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log model evaluation results as an MLflow run.

        Args:
            model_name: Name of the evaluated model
            eval_results: Results dict from evaluate_classifier()
            params: Optional training/inference parameters

        Returns:
            True if logged successfully
        """
        if not self.tracker.enabled:
            return False

        run_name = f"eval_{model_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        if not self.tracker.start_run(run_name=run_name, tags={"type": "model_evaluation", "model": model_name}):
            return False

        try:
            # Log evaluation metrics
            metrics = {
                "accuracy": eval_results.get("accuracy", 0.0),
                "precision": eval_results.get("precision", 0.0),
                "recall": eval_results.get("recall", 0.0),
                "f1_score": eval_results.get("f1_score", 0.0),
                "specificity": eval_results.get("specificity", 0.0),
                "total_samples": float(eval_results.get("total_samples", 0)),
            }
            self.tracker.log_metrics(metrics)

            # Log confusion matrix as params
            cm = eval_results.get("confusion_matrix", {})
            if cm:
                self.tracker.log_param("true_positives", str(cm.get("true_positives", 0)))
                self.tracker.log_param("true_negatives", str(cm.get("true_negatives", 0)))
                self.tracker.log_param("false_positives", str(cm.get("false_positives", 0)))
                self.tracker.log_param("false_negatives", str(cm.get("false_negatives", 0)))

            # Log support
            support = eval_results.get("support", {})
            if support:
                self.tracker.log_param("support_toxic", str(support.get("toxic", 0)))
                self.tracker.log_param("support_non_toxic", str(support.get("non_toxic", 0)))

            # Log optional params
            if params:
                self.tracker.log_params(params)

            self.tracker.log_param("threshold", str(eval_results.get("threshold", 0.5)))
            self.tracker.log_param("model_name", model_name)

            logger.info(f"Model evaluation logged to MLflow: {model_name} F1={metrics['f1_score']:.4f}")
            return True
        except Exception as e:
            logger.debug(f"Failed to log model evaluation to MLflow: {e}")
            return False
        finally:
            self.tracker.end_run()

    def log_cost_summary(self, cost_tracker: CostTracker) -> bool:
        """Log cost tracking summary as an MLflow run.

        Args:
            cost_tracker: CostTracker instance with accumulated metrics

        Returns:
            True if logged successfully
        """
        if not self.tracker.enabled:
            return False

        summary = cost_tracker.get_summary()
        run_name = f"cost_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        if not self.tracker.start_run(run_name=run_name, tags={"type": "cost_tracking"}):
            return False

        try:
            metrics = {
                "total_requests": float(summary.get("total_requests", 0)),
                "total_tokens": float(summary.get("total_tokens", 0)),
                "total_cost_usd": summary.get("total_cost_usd", 0.0),
                "total_inference_time_ms": summary.get("total_inference_time_ms", 0.0),
                "total_carbon_g": summary.get("total_carbon_g", 0.0),
                "avg_cost_per_request": summary.get("avg_cost_per_request", 0.0),
                "avg_tokens_per_request": summary.get("avg_tokens_per_request", 0.0),
                "uptime_hours": summary.get("uptime_hours", 0.0),
            }
            self.tracker.log_metrics(metrics)

            # Log per-model breakdown
            models = summary.get("models", {})
            for model_name, model_data in models.items():
                self.tracker.log_param(f"model_{model_name}_requests", str(model_data.get("requests", 0)))
                self.tracker.log_param(f"model_{model_name}_cost", str(model_data.get("total_cost", 0.0)))

            logger.info(f"Cost summary logged to MLflow: ${metrics['total_cost_usd']:.4f}")
            return True
        except Exception as e:
            logger.debug(f"Failed to log cost summary to MLflow: {e}")
            return False
        finally:
            self.tracker.end_run()

    def log_benchmark_comparison(
        self,
        benchmark_results: Dict[str, Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log benchmark comparison of multiple classifiers as an MLflow run.

        Args:
            benchmark_results: Results dict from benchmark_classifiers()
            params: Optional parameters to log

        Returns:
            True if logged successfully
        """
        if not self.tracker.enabled:
            return False

        run_name = f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        if not self.tracker.start_run(run_name=run_name, tags={"type": "benchmark_comparison"}):
            return False

        try:
            # Log metrics for each classifier
            for classifier_name, results in benchmark_results.items():
                if "error" in results:
                    self.tracker.log_param(f"{classifier_name}_error", results["error"])
                    continue

                prefix = f"{classifier_name}_"
                metrics = {
                    f"{prefix}accuracy": results.get("accuracy", 0.0),
                    f"{prefix}precision": results.get("precision", 0.0),
                    f"{prefix}recall": results.get("recall", 0.0),
                    f"{prefix}f1_score": results.get("f1_score", 0.0),
                    f"{prefix}specificity": results.get("specificity", 0.0),
                    f"{prefix}total_samples": float(results.get("total_samples", 0)),
                }
                self.tracker.log_metrics(metrics)

            if params:
                self.tracker.log_params(params)

            logger.info(f"Benchmark comparison logged to MLflow: {len(benchmark_results)} classifiers")
            return True
        except Exception as e:
            logger.debug(f"Failed to log benchmark comparison to MLflow: {e}")
            return False
        finally:
            self.tracker.end_run()


# Module-level singleton
_integration: Optional[MLflowIntegration] = None


def get_mlflow_integration() -> MLflowIntegration:
    """Get or create the global MLflowIntegration instance."""
    global _integration
    if _integration is None:
        _integration = MLflowIntegration()
    return _integration
