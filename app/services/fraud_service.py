"""
Fraud Detection Service for ATLAS-OPS.

Scores a transaction for fraud probability and extracts SHAP feature
contributions to explain the decision.
"""
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.services.ml_loader import (
    FRAUD_FEATURES,
    FRAUD_FEATURE_DEFAULTS,
    get_models,
    safe_label_encode,
    scale_features,
    fill_missing_features,
)

logger = get_logger(__name__)


class FraudService:
    """Stateless service — relies on the globally loaded model singleton."""

    @staticmethod
    def _build_feature_vector(features: dict[str, Any]) -> np.ndarray:
        """
        Map a normalised features dict to a numpy row using FRAUD_FEATURES order.
        Applies real LabelEncoders for strings and StandardScaler for numericals.

        NEVER crashes — fills missing features with risk-aware defaults.
        """
        models = get_models()

        # 1. Fill any missing features with intelligent defaults
        features = fill_missing_features(features, FRAUD_FEATURE_DEFAULTS, FRAUD_FEATURES)

        # 2. Apply Label Encoding to known string fields
        if "P_emaildomain" in features and isinstance(features["P_emaildomain"], str):
            features["P_emaildomain"] = safe_label_encode(
                models.label_encoders.get("email_domain")
                or models.label_encoders.get("P_emaildomain"),
                features["P_emaildomain"],
            )
        if "DeviceType" in features and isinstance(features["DeviceType"], str):
            features["DeviceType"] = safe_label_encode(
                models.label_encoders.get("device_type")
                or models.label_encoders.get("DeviceType"),
                features["DeviceType"],
            )
        if "DeviceInfo" in features and isinstance(features["DeviceInfo"], str):
            features["DeviceInfo"] = safe_label_encode(
                models.label_encoders.get("device_info")
                or models.label_encoders.get("DeviceInfo"),
                features["DeviceInfo"],
            )

        # 3. Scale numerical features
        scaled_features = scale_features(models.standard_scaler, features)

        # 4. Build row in exact FRAUD_FEATURES order
        row = []
        for fname in FRAUD_FEATURES:
            val = scaled_features.get(fname, 0)
            try:
                row.append(float(val))
            except (ValueError, TypeError):
                logger.warning("fraud_feature_cast_failed", feature=fname, value=val)
                row.append(0.0)

        return np.array([row])

    @staticmethod
    async def score(features: dict[str, Any]) -> tuple[float, dict[str, float]]:
        """
        Score a transaction for fraud.

        Args:
            features: dict with keys matching FRAUD_FEATURES

        Returns:
            (fraud_probability: float, shap_values: dict[feature_name -> contribution])
        """
        models = get_models()
        X = FraudService._build_feature_vector(features)

        # ── Prediction ───────────────────────────────────────────────────────
        try:
            proba = models.fraud_model.predict_proba(X)[0]
            # proba shape: (n_classes,)  — index 1 = P(fraud)
            fraud_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception as exc:
            logger.error("fraud_model_prediction_failed", error=str(exc), exc_info=True)
            # Conservative fallback — flag as medium-high risk so it's NOT auto-approved
            fraud_prob = 0.55

        # ── SHAP ─────────────────────────────────────────────────────────────
        shap_dict: dict[str, float] = {}
        explainer = models.fraud_explainer
        if explainer is not None:
            try:
                shap_vals = explainer.shap_values(X)
                # shap_vals can be (classes, samples, features) for multi-class
                if isinstance(shap_vals, list):
                    vals = shap_vals[1][0]  # class-1 SHAP values for sample 0
                else:
                    vals = shap_vals[0]
                shap_dict = {
                    feat: round(float(v), 6)
                    for feat, v in zip(FRAUD_FEATURES, vals)
                }
            except Exception as exc:
                logger.warning("fraud_shap_failed", error=str(exc))
                # Generate synthetic SHAP from feature values for explanation
                shap_dict = FraudService._synthetic_shap(features)
        else:
            # No explainer — generate synthetic feature importance
            shap_dict = FraudService._synthetic_shap(features)

        logger.info(
            "fraud_scored",
            fraud_probability=round(fraud_prob, 4),
            is_stub=models.fraud_is_stub,
            top_feature=max(shap_dict, key=lambda k: abs(shap_dict[k]))
            if shap_dict
            else "n/a",
        )
        return fraud_prob, shap_dict

    @staticmethod
    def _synthetic_shap(features: dict[str, Any]) -> dict[str, float]:
        """
        Generate synthetic SHAP-like values based on feature deviation from
        'normal' baselines. Used when real SHAP is unavailable.
        """
        baselines = {
            "TransactionAmt": 100.0,
            "card1": 10000,
            "card2": 200,
            "P_emaildomain": 0,
            "addr1": 200,
            "addr2": 50,
            "DeviceType": 0,
            "DeviceInfo": 0,
            "dist1": 10.0,
            "dist2": 5.0,
        }
        shap_vals = {}
        for feat in FRAUD_FEATURES:
            val = features.get(feat, 0)
            baseline = baselines.get(feat, 0)
            try:
                val_f = float(val)
                base_f = float(baseline)
                if feat == "TransactionAmt":
                    # Positive = increases fraud risk
                    shap_vals[feat] = round(max(0, (val_f - 200) / 5000), 6)
                elif feat in ("dist1", "dist2"):
                    shap_vals[feat] = round(max(0, (val_f - 20) / 500), 6)
                else:
                    diff = (val_f - base_f) / max(abs(base_f), 1)
                    shap_vals[feat] = round(diff * 0.05, 6)
            except (ValueError, TypeError):
                shap_vals[feat] = 0.0
        return shap_vals
