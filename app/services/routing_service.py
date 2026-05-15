"""
Intelligent Gateway Routing Service for ATLAS-OPS.

Uses the routing ML model to score each gateway, then selects the best one.
Factors in health metrics, latency, success rates, and circuit breaker state.
"""
from typing import Any

import numpy as np

from app.core.circuit_breaker import circuit_breakers
from app.core.logging import get_logger
from app.services.ml_loader import ROUTING_FEATURES, get_models

logger = get_logger(__name__)

SUPPORTED_GATEWAYS = ["stripe", "razorpay", "paypal", "square"]


class RoutingService:

    @staticmethod
    async def select_gateway(
        gateway_health_map: dict[str, dict[str, Any]],
    ) -> tuple[str, dict[str, float]]:
        """
        Score each gateway and select the best one.

        Args:
            gateway_health_map: {gateway_name: {success_rate, avg_latency_ms, circuit_state, total_requests}}

        Returns:
            (selected_gateway, gateway_scores_dict)
        """
        models = get_models()
        scores: dict[str, float] = {}

        for gw in SUPPORTED_GATEWAYS:
            health = gateway_health_map.get(gw, {})

            # Build features for this gateway
            success_rate = float(health.get("success_rate", 0.9))
            avg_latency = float(health.get("avg_latency_ms", 200))
            circuit_state_str = str(health.get("circuit_state", "closed"))
            total_requests = int(health.get("total_requests", 0))

            # Map circuit state to numeric
            circuit_numeric = 0.0
            if circuit_state_str in ("open", "OPEN"):
                circuit_numeric = 1.0
            elif circuit_state_str in ("half-open", "HALF_OPEN"):
                circuit_numeric = 0.5

            # Also check in-memory circuit breaker state
            if circuit_breakers.is_open(gw):
                circuit_numeric = 1.0

            # Health score = success rate
            health_score = success_rate

            feature_values = {
                "gateway_health_score": health_score,
                "recent_success_rate": success_rate,
                "avg_latency_ms": avg_latency,
                "circuit_state_numeric": circuit_numeric,
                "total_requests": total_requests,
            }

            # Build row in ROUTING_FEATURES order
            row = [float(feature_values.get(f, 0)) for f in ROUTING_FEATURES]
            X = np.array([row])

            try:
                proba = models.routing_model.predict_proba(X)[0]
                model_score = float(proba[1]) if len(proba) > 1 else float(proba[0])
            except Exception as exc:
                logger.warning("routing_model_failed", gateway=gw, error=str(exc))
                model_score = success_rate * 0.5  # fallback

            # ── Penalty: Circuit is open → heavily penalise ──────────────
            if circuit_numeric >= 1.0:
                model_score = -0.5  # negative = do not use
                logger.warning("routing_gateway_penalised", gateway=gw, reason="circuit_open")

            # ── Penalty: High latency ────────────────────────────────────
            if avg_latency > 2000:
                model_score -= 0.15

            scores[gw] = round(model_score, 4)

        # Select gateway with highest score (must be non-negative)
        valid_gateways = [(gw, s) for gw, s in scores.items() if s > 0]

        if valid_gateways:
            selected = max(valid_gateways, key=lambda x: x[1])[0]
        else:
            # All gateways have negative scores — pick least-bad
            selected = max(scores, key=scores.get)
            logger.error("all_gateways_degraded", scores=scores)

        logger.info(
            "gateway_selected",
            selected=selected,
            scores=scores,
            is_stub=models.routing_is_stub,
        )
        return selected, scores
