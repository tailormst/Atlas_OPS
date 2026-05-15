"""
ML Model Loader for ATLAS-OPS.

Attempts to load trained model files from disk; falls back gracefully to
DummyClassifier stubs so the API is always operational.
SHAP explainers are created for each model automatically.
"""

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import shap
from sklearn.dummy import DummyClassifier

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


# ── Feature definitions ──────────────────────────────────────────────────────
FRAUD_FEATURES = [
    "TransactionAmt",
    "card1",
    "card2",
    "P_emaildomain",
    "addr1",
    "addr2",
    "DeviceType",
    "DeviceInfo",
    "dist1",
    "dist2",
]

FAILURE_FEATURES = [
    "gateway_latency_ms",
    "retry_attempts",
    "gateway_health_score",
    "recent_success_rate",
    "timeout_flag",
    "connection_drop_flag",
    "dns_failure_flag",
    "http_status_code",
    "payment_gateway",
    "acquirer_bank",
]

ROUTING_FEATURES = [
    "gateway_health_score",
    "recent_success_rate",
    "avg_latency_ms",
    "circuit_state_numeric",
    "total_requests",
]


# ── Stub model fallback ──────────────────────────────────────────────────────
def _make_stub_classifier(strategy: str = "uniform") -> DummyClassifier:
    clf = DummyClassifier(strategy=strategy, random_state=42)

    X = np.zeros((4, 10))
    y = [0, 0, 1, 1]

    clf.fit(X, y)

    return clf


# ── Model loading ────────────────────────────────────────────────────────────
def _load_model(path: str, name: str) -> Any:
    abs_path = Path(path)

    if abs_path.exists():
        try:
            with open(abs_path, "rb") as f:
                model = pickle.load(f)

            logger.info(
                "ml_model_loaded",
                model=name,
                path=str(abs_path),
            )

            return model

        except Exception as exc:
            logger.warning(
                "ml_model_load_failed",
                model=name,
                path=str(abs_path),
                error=str(exc),
            )

    logger.warning(
        "ml_stub_model_active",
        model=name,
    )

    return _make_stub_classifier()


def _load_pickle_data(path: str, name: str) -> Any:
    abs_path = Path(path)

    if abs_path.exists():
        try:
            with open(abs_path, "rb") as f:
                data = pickle.load(f)

            logger.info(
                "pickle_data_loaded",
                name=name,
                path=str(abs_path),
            )

            return data

        except Exception as exc:
            logger.warning(
                "pickle_data_load_failed",
                name=name,
                path=str(abs_path),
                error=str(exc),
            )

    logger.warning(
        "pickle_data_missing",
        name=name,
        path=str(abs_path),
    )

    return None


# ── Encoder normalization ────────────────────────────────────────────────────
def _normalize_label_encoders(data: Any) -> dict[str, Any]:
    """
    Ensures label_encoders is always a dictionary.

    Handles:
    - dict
    - numpy arrays containing dict
    - invalid formats
    """

    if data is None:
        return {}

    # Already correct
    if isinstance(data, dict):
        return data

    # numpy object array
    if isinstance(data, np.ndarray):
        try:
            # Single object stored inside ndarray
            if data.shape == () or data.size == 1:
                extracted = data.item()

                if isinstance(extracted, dict):
                    return extracted

            # Try converting iterable key-value pairs
            if len(data) > 0:
                possible_dict = dict(data)

                if isinstance(possible_dict, dict):
                    return possible_dict

        except Exception as exc:
            logger.warning(
                "label_encoder_array_parse_failed",
                error=str(exc),
            )

    logger.warning(
        "invalid_label_encoder_format",
        received_type=str(type(data)),
    )

    return {}


# ── Utility functions ────────────────────────────────────────────────────────
def safe_label_encode(encoder: Any, val: Any) -> int:
    """
    Safely encode a string using LabelEncoder with fallback handling.
    """

    if encoder is None:
        return 0

    if not hasattr(encoder, "classes_"):
        return 0

    try:
        val_str = str(val)

        if val_str in encoder.classes_:
            return int(encoder.transform([val_str])[0])

        # Fallback categories
        for fallback in ["Other", "Unknown", "nan"]:
            if fallback in encoder.classes_:
                return int(encoder.transform([fallback])[0])

    except Exception as exc:
        logger.warning(
            "safe_label_encode_failed",
            error=str(exc),
        )

    return 0


def scale_features(
    standard_scaler: Any,
    features: dict[str, Any],
) -> dict[str, Any]:
    """
    Applies StandardScaler safely to numerical features.
    """

    if (
        standard_scaler is None
        or not hasattr(standard_scaler, "feature_names_in_")
    ):
        return features

    mapping = {
        "amount": "TransactionAmt",
        "health_score": "gateway_health_score",
        "gateway_latency": "gateway_latency_ms",
        "avg_latency": "avg_latency_ms",
        "success_rate": "recent_success_rate",
    }

    row = []

    for col in standard_scaler.feature_names_in_:
        our_key = mapping.get(col, col)

        try:
            row.append(float(features.get(our_key, 0.0)))

        except Exception:
            row.append(0.0)

    try:
        scaled_row = standard_scaler.transform([row])[0]

    except Exception as exc:
        logger.warning(
            "standard_scaler_failed",
            error=str(exc),
        )

        return features

    scaled_features = features.copy()

    for col, scaled_val in zip(
        standard_scaler.feature_names_in_,
        scaled_row,
    ):
        our_key = mapping.get(col, col)

        if our_key in scaled_features:
            scaled_features[our_key] = float(scaled_val)

    return scaled_features


# ── Data container ───────────────────────────────────────────────────────────
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

    fraud_features: list[str] = field(
        default_factory=lambda: FRAUD_FEATURES
    )

    failure_features: list[str] = field(
        default_factory=lambda: FAILURE_FEATURES
    )

    routing_features: list[str] = field(
        default_factory=lambda: ROUTING_FEATURES
    )


# ── Global singleton ─────────────────────────────────────────────────────────
_models: Optional[LoadedModels] = None


# ── SHAP explainers ──────────────────────────────────────────────────────────
def _build_shap_explainer(
    model: Any,
    feature_count: int,
) -> Any:
    """
    Build SHAP explainer safely.
    """

    try:
        return shap.TreeExplainer(model)

    except Exception:
        pass

    try:
        bg = np.zeros((1, feature_count))

        return shap.KernelExplainer(
            model.predict_proba,
            bg,
        )

    except Exception as exc:
        logger.warning(
            "shap_explainer_init_failed",
            error=str(exc),
        )

        return None


# ── Main loader ──────────────────────────────────────────────────────────────
def load_all_models() -> LoadedModels:
    """
    Load all ML models + SHAP explainers.
    Called once during FastAPI startup.
    """

    global _models

    fraud_model = _load_model(
        settings.fraud_model_path,
        "fraud",
    )

    failure_model = _load_model(
        settings.failure_model_path,
        "failure",
    )

    routing_model = _load_model(
        settings.routing_model_path,
        "routing",
    )

    models_dir = Path(settings.fraud_model_path).parent

    scaler_path = models_dir / "standard_scaler.pkl"
    encoders_path = models_dir / "label_encoders.pkl"

    # ── Load scaler ─────────────────────────────────────────────────────────
    standard_scaler = _load_pickle_data(
        str(scaler_path),
        "standard_scaler",
    )

    # ── Load encoders safely ────────────────────────────────────────────────
    raw_encoders = _load_pickle_data(
        str(encoders_path),
        "label_encoders",
    )

    label_encoders = _normalize_label_encoders(raw_encoders)

    logger.info(
        "label_encoders_ready",
        encoder_keys=list(label_encoders.keys()),
    )

    # ── Build loaded model object ───────────────────────────────────────────
    _models = LoadedModels(
        fraud_model=fraud_model,
        failure_model=failure_model,
        routing_model=routing_model,

        label_encoders=label_encoders,
        standard_scaler=standard_scaler,

        fraud_explainer=_build_shap_explainer(
            fraud_model,
            len(FRAUD_FEATURES),
        ),

        failure_explainer=_build_shap_explainer(
            failure_model,
            len(FAILURE_FEATURES),
        ),

        # Disabled for memory optimization
        routing_explainer=None,
    )

    # ── Logging ─────────────────────────────────────────────────────────────
    if (
        isinstance(fraud_model, DummyClassifier)
        or isinstance(failure_model, DummyClassifier)
        or isinstance(routing_model, DummyClassifier)
    ):
        logger.warning(
            "fallback_dummy_models_active",
        )

    else:
        logger.info(
            "real_ml_models_loaded",
        )

    return _models


# ── Public accessor ──────────────────────────────────────────────────────────
def get_models() -> LoadedModels:
    if _models is None:
        raise RuntimeError(
            "Models not loaded. Call load_all_models() at startup."
        )

    return _models