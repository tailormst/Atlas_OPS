"""
Payment Failure Diagnosis Service for ATLAS-OPS.

Runs the failure model against gateway telemetry and extracts SHAP values
to identify which features contributed most to the failure.
"""
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.services.ml_loader import (
    FAILURE_FEATURES,
    FAILURE_FEATURE_DEFAULTS,
    get_models,
    safe_label_encode,
    scale_features,
    fill_missing_features,
)

logger = get_logger(__name__)


class FailureService:

    @staticmethod
    def _build_feature_vector(gateway_error: dict[str, Any]) -> np.ndarray:
        """
        Build the failure model feature vector from raw gateway error metadata.
        NEVER crashes — fills missing features with defaults.
        """
        models = get_models()

        # 1. Fill missing features
        features = fill_missing_features(gateway_error, FAILURE_FEATURE_DEFAULTS, FAILURE_FEATURES)

        # 2. Encode categorical fields
        gw_name = features.get("payment_gateway", "unknown")
        acq_bank = features.get("acquirer_bank", "unknown")

        if isinstance(gw_name, str):
            features["payment_gateway"] = safe_label_encode(
                models.label_encoders.get("gateway_id")
                or models.label_encoders.get("payment_gateway"),
                gw_name,
            )
        if isinstance(acq_bank, str):
            features["acquirer_bank"] = safe_label_encode(
                models.label_encoders.get("bank_id")
                or models.label_encoders.get("acquirer_bank"),
                acq_bank,
            )

        # 3. Ensure boolean flags are integers
        for flag in ("timeout_flag", "connection_drop_flag", "dns_failure_flag"):
            features[flag] = int(bool(features.get(flag, 0)))

        # 4. Scale features
        scaled = scale_features(models.standard_scaler, features)

        # 5. Build row in exact FAILURE_FEATURES order
        row = []
        for fname in FAILURE_FEATURES:
            val = scaled.get(fname, 0)
            try:
                row.append(float(val))
            except (ValueError, TypeError):
                row.append(0.0)

        return np.array([row])

    @staticmethod
    async def diagnose(
        gateway_error: dict[str, Any],
        transaction_shap: dict[str, float],
    ) -> tuple[float, dict[str, Any]]:
        """
        Diagnose a payment failure.

        Args:
            gateway_error: raw gateway error telemetry
            transaction_shap: SHAP values from the fraud model for context

        Returns:
            (failure_probability, diagnosis_dict)
        """
        models = get_models()
        X = FailureService._build_feature_vector(gateway_error)

        # ── Prediction ───────────────────────────────────────────────────────
        try:
            proba = models.failure_model.predict_proba(X)[0]
            failure_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception as exc:
            logger.error("failure_model_prediction_failed", error=str(exc), exc_info=True)
            # Conservative: this IS a failure, so predict high probability
            failure_prob = 0.75

        # ── SHAP ─────────────────────────────────────────────────────────────
        shap_dict: dict[str, float] = {}
        explainer = models.failure_explainer
        if explainer is not None:
            try:
                shap_vals = explainer.shap_values(X)
                if isinstance(shap_vals, list):
                    vals = shap_vals[1][0]
                else:
                    vals = shap_vals[0]
                shap_dict = {
                    feat: round(float(v), 6)
                    for feat, v in zip(FAILURE_FEATURES, vals)
                }
            except Exception as exc:
                logger.warning("failure_shap_failed", error=str(exc))
                shap_dict = FailureService._synthetic_failure_shap(gateway_error)
        else:
            shap_dict = FailureService._synthetic_failure_shap(gateway_error)

        # Top contributing features
        top_features = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

        diagnosis = {
            "failure_probability": round(failure_prob, 4),
            "top_contributing_features": [
                {"feature": f, "shap_value": s} for f, s in top_features
            ],
            "shap_values": shap_dict,
            "raw_error": gateway_error,
        }

        logger.info(
            "failure_diagnosed",
            failure_probability=failure_prob,
            is_stub=models.failure_is_stub,
            top_feature=top_features[0][0] if top_features else "n/a",
        )
        return failure_prob, diagnosis

    @staticmethod
    def _synthetic_failure_shap(gateway_error: dict[str, Any]) -> dict[str, float]:
        """Generate synthetic SHAP values based on error telemetry."""
        shap_vals = {}
        for feat in FAILURE_FEATURES:
            val = gateway_error.get(feat, 0)
            try:
                val_f = float(val) if not isinstance(val, str) else 0.0
            except (ValueError, TypeError):
                val_f = 0.0

            if feat == "gateway_latency_ms":
                shap_vals[feat] = round(min(val_f / 5000, 0.5), 6)
            elif feat == "timeout_flag" and val_f > 0:
                shap_vals[feat] = 0.35
            elif feat == "connection_drop_flag" and val_f > 0:
                shap_vals[feat] = 0.30
            elif feat == "dns_failure_flag" and val_f > 0:
                shap_vals[feat] = 0.28
            elif feat == "http_status_code":
                if val_f >= 500:
                    shap_vals[feat] = 0.25
                elif val_f >= 400:
                    shap_vals[feat] = 0.12
                else:
                    shap_vals[feat] = -0.05
            elif feat == "gateway_health_score":
                shap_vals[feat] = round(-(val_f - 0.5) * 0.3, 6)  # low health = positive contribution
            elif feat == "recent_success_rate":
                shap_vals[feat] = round(-(val_f - 0.5) * 0.2, 6)
            else:
                shap_vals[feat] = 0.0

        return shap_vals
