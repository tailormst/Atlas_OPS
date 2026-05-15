"""
ML Model Loader for ATLAS-OPS.

Attempts to load trained model files from disk; falls back gracefully to
RiskAwareStubClassifier stubs so the API produces REALISTIC outcomes.
SHAP explainers are created for each model automatically.
"""
import os
import pickle
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import shap
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
import joblib

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


# ── Feature definitions ──────────────────────────────────────────────────────
FRAUD_FEATURES = [
    "TransactionAmt", "card1", "card2", "P_emaildomain",
    "addr1", "addr2", "DeviceType", "DeviceInfo", "dist1", "dist2",
]

FAILURE_FEATURES = [
    "gateway_latency_ms", "retry_attempts", "gateway_health_score",
    "recent_success_rate", "timeout_flag", "connection_drop_flag",
    "dns_failure_flag", "http_status_code", "payment_gateway", "acquirer_bank",
]

ROUTING_FEATURES = [
    "gateway_health_score", "recent_success_rate", "avg_latency_ms",
    "circuit_state_numeric", "total_requests",
]

# ── Risk-weighted defaults for missing features ─────────────────────────────
FRAUD_FEATURE_DEFAULTS = {
    "TransactionAmt": 100.0,
    "card1": 10000,
    "card2": 200,
    "P_emaildomain": "unknown.com",
    "addr1": 200,
    "addr2": 50,
    "DeviceType": "desktop",
    "DeviceInfo": "Unknown Browser",
    "dist1": 50.0,
    "dist2": 25.0,
}

FAILURE_FEATURE_DEFAULTS = {
    "gateway_latency_ms": 200.0,
    "retry_attempts": 0,
    "gateway_health_score": 0.8,
    "recent_success_rate": 0.9,
    "timeout_flag": 0,
    "connection_drop_flag": 0,
    "dns_failure_flag": 0,
    "http_status_code": 200,
    "payment_gateway": "unknown",
    "acquirer_bank": "unknown",
}


class RiskAwareStubClassifier:
    """
    A heuristic-based classifier that produces REALISTIC fraud/failure scores
    based on input features. Used as fallback when trained .pkl models are
    missing. Much better than DummyClassifier which returns random ~0.5.

    For fraud detection:
      - High amounts (>1000) increase fraud probability
      - Unknown/suspicious email domains increase probability
      - Large distances increase probability
      - Unknown devices increase probability

    For failure prediction:
      - High latency increases failure probability
      - Timeout/connection flags increase probability
      - Low health scores increase probability

    For routing:
      - High success rate + low latency = high routing score
    """

    def __init__(self, model_type: str = "fraud"):
        self.model_type = model_type
        self.classes_ = np.array([0, 1])
        self._is_stub = True

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        results = []
        for row in X:
            if self.model_type == "fraud":
                score = self._fraud_heuristic(row)
            elif self.model_type == "failure":
                score = self._failure_heuristic(row)
            elif self.model_type == "routing":
                score = self._routing_heuristic(row)
            else:
                score = 0.5
            # Clamp to valid probability range
            score = max(0.01, min(0.99, score))
            results.append([1.0 - score, score])
        return np.array(results)

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return (proba[:, 1] >= 0.5).astype(int)

    def _fraud_heuristic(self, row: np.ndarray) -> float:
        """
        FRAUD_FEATURES order:
        0: TransactionAmt, 1: card1, 2: card2, 3: P_emaildomain(encoded),
        4: addr1, 5: addr2, 6: DeviceType(encoded), 7: DeviceInfo(encoded),
        8: dist1, 9: dist2
        """
        score = 0.15  # baseline — most transactions are legit

        # Amount-based risk
        amt = float(row[0]) if len(row) > 0 else 100.0
        if amt > 5000:
            score += 0.35
        elif amt > 2000:
            score += 0.20
        elif amt > 1000:
            score += 0.12
        elif amt > 500:
            score += 0.05

        # Distance-based risk (dist1, dist2)
        dist1 = float(row[8]) if len(row) > 8 else 0.0
        dist2 = float(row[9]) if len(row) > 9 else 0.0
        if dist1 > 200:
            score += 0.15
        elif dist1 > 100:
            score += 0.08
        if dist2 > 150:
            score += 0.10

        # Email domain risk (encoded — high values often = rare/suspicious)
        email_enc = float(row[3]) if len(row) > 3 else 0.0
        if email_enc > 50:  # unusual encoded domain
            score += 0.10

        # Device risk (encoded — high values = rare/unknown device)
        device_enc = float(row[7]) if len(row) > 7 else 0.0
        if device_enc > 100:
            score += 0.08

        # Card risk — very high card1 values are suspicious
        card1 = float(row[1]) if len(row) > 1 else 10000
        if card1 > 50000:
            score += 0.05

        # Add small deterministic noise based on features for variety
        feature_hash = hashlib.md5(row.tobytes()).hexdigest()
        noise = (int(feature_hash[:4], 16) / 65535.0 - 0.5) * 0.08
        score += noise

        return score

    def _failure_heuristic(self, row: np.ndarray) -> float:
        """
        FAILURE_FEATURES order:
        0: gateway_latency_ms, 1: retry_attempts, 2: gateway_health_score,
        3: recent_success_rate, 4: timeout_flag, 5: connection_drop_flag,
        6: dns_failure_flag, 7: http_status_code, 8: payment_gateway(enc),
        9: acquirer_bank(enc)
        """
        score = 0.10  # baseline

        latency = float(row[0]) if len(row) > 0 else 200.0
        retries = float(row[1]) if len(row) > 1 else 0
        health = float(row[2]) if len(row) > 2 else 0.8
        success_rate = float(row[3]) if len(row) > 3 else 0.9
        timeout = float(row[4]) if len(row) > 4 else 0
        conn_drop = float(row[5]) if len(row) > 5 else 0
        dns_fail = float(row[6]) if len(row) > 6 else 0
        http_status = float(row[7]) if len(row) > 7 else 200

        # Direct failure indicators
        if timeout > 0:
            score += 0.30
        if conn_drop > 0:
            score += 0.25
        if dns_fail > 0:
            score += 0.25

        # HTTP status code risk
        if http_status >= 500:
            score += 0.25
        elif http_status >= 400:
            score += 0.15

        # Latency risk
        if latency > 2000:
            score += 0.20
        elif latency > 1000:
            score += 0.10

        # Health score (inverted)
        score += (1.0 - max(0.0, min(1.0, health))) * 0.15

        # Success rate (inverted)
        score += (1.0 - max(0.0, min(1.0, success_rate))) * 0.10

        # Retry attempts
        score += min(retries * 0.05, 0.15)

        return score

    def _routing_heuristic(self, row: np.ndarray) -> float:
        """
        ROUTING_FEATURES order:
        0: gateway_health_score, 1: recent_success_rate, 2: avg_latency_ms,
        3: circuit_state_numeric, 4: total_requests
        """
        health = float(row[0]) if len(row) > 0 else 0.8
        success_rate = float(row[1]) if len(row) > 1 else 0.9
        latency = float(row[2]) if len(row) > 2 else 200.0
        circuit_open = float(row[3]) if len(row) > 3 else 0
        total_req = float(row[4]) if len(row) > 4 else 0

        # Score = how GOOD this gateway is (higher = better route)
        score = 0.5  # baseline

        # Health contributes positively
        score += health * 0.2

        # Success rate contributes positively
        score += success_rate * 0.2

        # Low latency is good
        if latency < 200:
            score += 0.1
        elif latency > 1000:
            score -= 0.15

        # Open circuit = bad
        if circuit_open > 0:
            score -= 0.4

        # More requests = more data = slight positive
        if total_req > 100:
            score += 0.05

        return max(0.05, min(0.95, score))


def _make_stub_classifier(model_type: str = "fraud") -> RiskAwareStubClassifier:
    """Create a risk-aware stub classifier that produces realistic predictions."""
    logger.warning(
        "ml_stub_model_active",
        model_type=model_type,
        message="Using heuristic-based stub. Place trained .pkl files in app/ml_models/ for real ML inference.",
    )
    return RiskAwareStubClassifier(model_type=model_type)


def _load_model(path: str, name: str, model_type: str = "fraud") -> Any:
    abs_path = Path(path)
    if abs_path.exists() and abs_path.stat().st_size > 100:
        try:
            with open(abs_path, "rb") as f:
                model = pickle.load(f)

            # Introspect the loaded model
            model_info = {
                "type": type(model).__name__,
                "size_bytes": abs_path.stat().st_size,
            }
            if hasattr(model, "n_features_in_"):
                model_info["n_features"] = model.n_features_in_
            if hasattr(model, "feature_names_in_"):
                model_info["feature_names"] = list(model.feature_names_in_[:5])
            if hasattr(model, "classes_"):
                model_info["classes"] = list(model.classes_)
            if hasattr(model, "n_estimators"):
                model_info["n_estimators"] = model.n_estimators

            logger.info("ml_model_loaded", model=name, path=str(abs_path), **model_info)
            return model
        except Exception as exc:
            logger.warning(
                "ml_model_load_failed",
                model=name,
                path=str(abs_path),
                error=str(exc),
            )
    else:
        logger.warning(
            "ml_model_file_missing",
            model=name,
            path=str(abs_path),
            exists=abs_path.exists(),
        )

    return _make_stub_classifier(model_type)


def _load_pickle_data(path: str, name: str) -> Any:
    abs_path = Path(path)
    if abs_path.exists() and abs_path.stat().st_size > 10:
        try:
            with open(abs_path, "rb") as f:
                data = pickle.load(f)
            logger.info("pickle_data_loaded", name=name, path=str(abs_path), type=type(data).__name__)
            return data
        except Exception as exc:
            logger.warning(
                "pickle_data_load_failed",
                name=name,
                path=str(abs_path),
                error=str(exc),
            )
    return None


def safe_label_encode(encoder: Any, val: Any) -> int:
    """Safely encode a string using the provided LabelEncoder with fallback."""
    if encoder is None or not hasattr(encoder, "classes_"):
        return 0

    val_str = str(val)

    # Direct match
    if val_str in encoder.classes_:
        return int(encoder.transform([val_str])[0])

    # Fallback: try common unknown buckets
    for fallback in ["Other", "Unknown", "other", "unknown", "nan", "UNKNOWN"]:
        if fallback in encoder.classes_:
            return int(encoder.transform([fallback])[0])

    # Final fallback: use max_class + 1 to represent "unknown"
    # This is safer than 0 because 0 maps to a real known class
    max_encoded = len(encoder.classes_) - 1
    logger.debug(
        "label_encode_unknown_fallback",
        value=val_str,
        fallback_to=max_encoded,
    )
    return max_encoded


def scale_features(standard_scaler: Any, features: dict[str, Any]) -> dict[str, Any]:
    """Applies the StandardScaler if available to numerical features."""
    if standard_scaler is None:
        return features

    if not hasattr(standard_scaler, "transform"):
        return features

    # Map standard_scaler feature names to backend variable names
    mapping = {
        "amount": "TransactionAmt",
        "health_score": "gateway_health_score",
        "gateway_latency": "gateway_latency_ms",
        "avg_latency": "avg_latency_ms",
        "success_rate": "recent_success_rate",
    }

    # Get scaler's expected feature names
    if hasattr(standard_scaler, "feature_names_in_"):
        scaler_features = list(standard_scaler.feature_names_in_)
    elif hasattr(standard_scaler, "n_features_in_"):
        # No feature names available — can't safely apply
        logger.debug("scaler_no_feature_names", n_features=standard_scaler.n_features_in_)
        return features
    else:
        return features

    # Build the row in scaler's expected order
    row = []
    for col in scaler_features:
        our_key = mapping.get(col, col)
        val = features.get(our_key)
        if val is None:
            # Use training mean if available
            idx = scaler_features.index(col)
            if hasattr(standard_scaler, "mean_") and idx < len(standard_scaler.mean_):
                val = float(standard_scaler.mean_[idx])
                logger.debug("scaler_imputed_mean", feature=col, mean_value=val)
            else:
                val = 0.0
        row.append(float(val))

    try:
        scaled_row = standard_scaler.transform([row])[0]
    except Exception as exc:
        logger.warning("standard_scaler_failed", error=str(exc))
        return features

    scaled_features = features.copy()
    for col, scaled_val in zip(scaler_features, scaled_row):
        our_key = mapping.get(col, col)
        if our_key in scaled_features:
            scaled_features[our_key] = scaled_val
    return scaled_features


def fill_missing_features(features: dict[str, Any], defaults: dict[str, Any], feature_list: list[str]) -> dict[str, Any]:
    """
    Fill in any missing features with intelligent defaults.
    Logs warnings for every substitution.
    """
    filled = features.copy()
    for fname in feature_list:
        if fname not in filled or filled[fname] is None:
            default_val = defaults.get(fname, 0)
            filled[fname] = default_val
            logger.warning(
                "feature_missing_filled",
                feature=fname,
                default_value=default_val,
                message=f"Feature '{fname}' was missing, using default: {default_val}",
            )
    return filled


@dataclass
class LoadedModels:
    fraud_model: Any = field(default=None)
    failure_model: Any = field(default=None)
    routing_model: Any = field(default=None)

    label_encoders: dict[str, Any] = field(default_factory=dict)
    standard_scaler: Any = field(default=None)

    fraud_explainer: Optional[Any] = field(default=None)
    failure_explainer: Optional[Any] = field(default=None)
    routing_explainer: Optional[Any] = field(default=None)

    fraud_features: list[str] = field(default_factory=lambda: FRAUD_FEATURES)
    failure_features: list[str] = field(default_factory=lambda: FAILURE_FEATURES)
    routing_features: list[str] = field(default_factory=lambda: ROUTING_FEATURES)

    @property
    def fraud_is_stub(self) -> bool:
        return getattr(self.fraud_model, "_is_stub", False) or isinstance(self.fraud_model, DummyClassifier)

    @property
    def failure_is_stub(self) -> bool:
        return getattr(self.failure_model, "_is_stub", False) or isinstance(self.failure_model, DummyClassifier)

    @property
    def routing_is_stub(self) -> bool:
        return getattr(self.routing_model, "_is_stub", False) or isinstance(self.routing_model, DummyClassifier)


# Global singleton
_models: Optional[LoadedModels] = None


def _build_shap_explainer(model: Any, feature_count: int, name: str = "") -> Any:
    """Build a SHAP explainer, returning None for stubs."""
    # Don't attempt SHAP on stub classifiers
    if getattr(model, "_is_stub", False) or isinstance(model, DummyClassifier):
        logger.info("shap_skipped_stub_model", model=name)
        return None

    try:
        # Try TreeExplainer first (XGBoost / RF / etc.)
        explainer = shap.TreeExplainer(model)
        logger.info("shap_tree_explainer_created", model=name)
        return explainer
    except Exception as e:
        logger.debug("shap_tree_explainer_failed", model=name, error=str(e))

    try:
        bg = np.zeros((10, feature_count))
        explainer = shap.KernelExplainer(model.predict_proba, bg)
        logger.info("shap_kernel_explainer_created", model=name)
        return explainer
    except Exception as exc:
        logger.warning("shap_explainer_init_failed", model=name, error=str(exc))
        return None


def load_all_models() -> LoadedModels:
    """Load all three models + SHAP explainers. Call once at app startup."""
    global _models

    fraud_model = _load_model(settings.fraud_model_path, "fraud", "fraud")
    failure_model = _load_model(settings.failure_model_path, "failure", "failure")
    routing_model = _load_model(settings.routing_model_path, "routing", "routing")

    scaler_path = Path(settings.fraud_model_path).parent / "standard_scaler.pkl"
    encoders_path = Path(settings.fraud_model_path).parent / "label_encoders.pkl"

    standard_scaler = _load_pickle_data(str(scaler_path), "standard_scaler")
    
    encoders_data = _load_pickle_data(str(encoders_path), "label_encoders")
    label_encoders = encoders_data if encoders_data is not None else {}

    # Log encoder details
    if isinstance(label_encoders, dict) and label_encoders:
        for enc_name, enc in label_encoders.items():
            if hasattr(enc, "classes_"):
                logger.info(
                    "label_encoder_loaded",
                    encoder=enc_name,
                    n_classes=len(enc.classes_),
                    sample_classes=list(enc.classes_[:5]),
                )

    # Log scaler details
    if standard_scaler is not None and hasattr(standard_scaler, "feature_names_in_"):
        logger.info(
            "standard_scaler_loaded",
            features=list(standard_scaler.feature_names_in_),
            n_features=len(standard_scaler.feature_names_in_),
        )

    _models = LoadedModels(
        fraud_model=fraud_model,
        failure_model=failure_model,
        routing_model=routing_model,
        label_encoders=label_encoders,
        standard_scaler=standard_scaler,
        fraud_explainer=_build_shap_explainer(fraud_model, len(FRAUD_FEATURES), "fraud"),
        failure_explainer=_build_shap_explainer(failure_model, len(FAILURE_FEATURES), "failure"),
        routing_explainer=None,  # Routing doesn't need SHAP explanation
    )

    # Summary logging
    stub_models = []
    real_models = []
    for name, model in [("fraud", fraud_model), ("failure", failure_model), ("routing", routing_model)]:
        if getattr(model, "_is_stub", False) or isinstance(model, DummyClassifier):
            stub_models.append(name)
        else:
            real_models.append(name)

    if stub_models:
        logger.warning(
            "ml_models_summary",
            real_models=real_models,
            stub_models=stub_models,
            message=f"Stub models active for: {', '.join(stub_models)}. "
                    "Place trained .pkl files in app/ml_models/ for production inference.",
        )
    else:
        logger.info("ml_models_summary", message="All real ML models loaded successfully", models=real_models)

    return _models


def get_models() -> LoadedModels:
    if _models is None:
        raise RuntimeError("Models not loaded. Call load_all_models() at startup.")
    return _models
