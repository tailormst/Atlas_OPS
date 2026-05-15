"""
RAG Explainer Service for ATLAS-OPS.

Generates human-readable explanations for transaction outcomes using
LangChain + OpenAI LLM, with a robust template-based fallback when
no API key is configured.
"""
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RAGExplainerService:
    """
    Provides two entry points:
      - explain()               → for gateway failures
      - explain_fraud_rejection() → for fraud rejections
    """

    @staticmethod
    async def explain(
        transaction_id: str,
        shap_values: dict[str, float],
        gateway_error: dict[str, Any],
        gateway: str,
    ) -> str:
        """Generate explanation for a gateway failure."""
        # Sort SHAP features by absolute contribution
        sorted_features = sorted(
            shap_values.items(), key=lambda x: abs(x[1]), reverse=True
        )[:5]

        # Try LLM path if OpenAI key exists
        if settings.openai_api_key:
            try:
                return await _llm_explain_failure(
                    transaction_id, sorted_features, gateway_error, gateway,
                )
            except Exception as exc:
                logger.warning("llm_explain_failed", error=str(exc))

        # Template fallback
        return _template_explain_failure(
            transaction_id, sorted_features, gateway_error, gateway,
        )

    @staticmethod
    async def explain_fraud_rejection(
        transaction_id: str,
        fraud_prob: float,
        shap_values: dict[str, float],
        features: dict[str, Any],
    ) -> str:
        """Generate explanation for a fraud rejection."""
        sorted_features = sorted(
            shap_values.items(), key=lambda x: abs(x[1]), reverse=True
        )[:5]

        if settings.openai_api_key:
            try:
                return await _llm_explain_fraud(
                    transaction_id, fraud_prob, sorted_features, features,
                )
            except Exception as exc:
                logger.warning("llm_explain_fraud_failed", error=str(exc))

        return _template_explain_fraud(
            transaction_id, fraud_prob, sorted_features, features,
        )


# ── Template Fallbacks ──────────────────────────────────────────────────────

def _template_explain_failure(
    transaction_id: str,
    sorted_features: list[tuple[str, float]],
    gateway_error: dict[str, Any],
    gateway: str,
) -> str:
    """Deterministic, rich explanation for gateway failures."""
    gw = gateway.upper()
    error_type = gateway_error.get("error", "Unknown error")
    latency = gateway_error.get("gateway_latency_ms", 0)
    http_status = gateway_error.get("http_status_code", 503)
    timeout = gateway_error.get("timeout_flag", False)
    conn_drop = gateway_error.get("connection_drop_flag", False)
    dns_fail = gateway_error.get("dns_failure_flag", False)
    health = gateway_error.get("gateway_health_score", 0)
    success_rate = gateway_error.get("recent_success_rate", 0)

    lines = [
        f"⚠️ Transaction {transaction_id[:8]}... FAILED via {gw} gateway.",
        "",
        f"Root Cause: {error_type}",
        f"HTTP Status: {http_status} | Latency: {latency:.0f}ms",
    ]

    if timeout:
        lines.append("• Gateway connection timed out — the external API did not respond within the allowed window.")
    if conn_drop:
        lines.append("• Connection was dropped mid-request — possible network instability or gateway overload.")
    if dns_fail:
        lines.append("• DNS resolution failed — the gateway hostname could not be resolved.")

    lines.append("")
    lines.append(f"Gateway Health: {health*100:.0f}% | Recent Success Rate: {success_rate*100:.0f}%")

    if sorted_features:
        lines.append("")
        lines.append("Top Contributing Factors (SHAP Analysis):")
        for feat, val in sorted_features:
            direction = "↑ increases" if val > 0 else "↓ decreases"
            lines.append(f"  • {feat}: {val:+.4f} ({direction} failure risk)")

    lines.append("")
    lines.append("Recommendation: If this gateway continues to fail, enable outage simulation to "
                 "redirect traffic to alternative gateways. Monitor circuit breaker state in the admin panel.")

    return "\n".join(lines)


def _template_explain_fraud(
    transaction_id: str,
    fraud_prob: float,
    sorted_features: list[tuple[str, float]],
    features: dict[str, Any],
) -> str:
    """Deterministic, rich explanation for fraud rejections."""
    amount = features.get("TransactionAmt", 0)
    email = features.get("P_emaildomain", "unknown")
    device = features.get("DeviceInfo", "unknown")
    dist1 = features.get("dist1", 0)

    lines = [
        f"🚫 Transaction {transaction_id[:8]}... REJECTED — Fraud probability: {fraud_prob*100:.1f}%",
        "",
        f"The AI fraud model determined this transaction has a {fraud_prob*100:.1f}% probability of being fraudulent, "
        f"which exceeds the {settings.fraud_threshold*100:.0f}% threshold.",
        "",
        "Transaction Details:",
        f"  • Amount: ${amount:,.2f}",
        f"  • Email Domain: {email}",
        f"  • Device: {device}",
        f"  • Distance 1: {dist1:.0f} units",
    ]

    if sorted_features:
        lines.append("")
        lines.append("Top Risk Factors (SHAP Analysis):")
        for feat, val in sorted_features:
            if val > 0:
                lines.append(f"  🔴 {feat}: {val:+.4f} — INCREASES fraud risk")
            else:
                lines.append(f"  🟢 {feat}: {val:+.4f} — decreases fraud risk")

    if fraud_prob > 0.9:
        lines.append("\n⛔ VERY HIGH RISK — This transaction exhibits multiple fraud indicators.")
    elif fraud_prob > 0.75:
        lines.append("\n⚠️ HIGH RISK — Significant fraud indicators detected. Manual review recommended.")
    else:
        lines.append("\n🔶 MODERATE RISK — Transaction exceeds fraud threshold. Review payment details.")

    return "\n".join(lines)


# ── LLM Path ────────────────────────────────────────────────────────────────

async def _llm_explain_failure(
    transaction_id: str,
    sorted_features: list[tuple[str, float]],
    gateway_error: dict[str, Any],
    gateway: str,
) -> str:
    """Use LangChain + OpenAI to generate an explanation."""
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate

    llm = ChatOpenAI(
        model=settings.openai_model or "gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.3,
        max_tokens=500,
    )

    features_text = "\n".join(
        f"  - {f}: {v:+.4f} ({'increases' if v > 0 else 'decreases'} risk)"
        for f, v in sorted_features
    )

    prompt = ChatPromptTemplate.from_template(
        "You are an AI payment operations analyst. "
        "A transaction (ID: {txn_id}) failed through the {gateway} gateway.\n\n"
        "Gateway error details:\n{error_json}\n\n"
        "Top SHAP feature contributions to failure:\n{features}\n\n"
        "Provide a concise, professional explanation of why the transaction failed "
        "and what actions the merchant should take. Use bullet points."
    )

    chain = prompt | llm
    response = await chain.ainvoke({
        "txn_id": transaction_id[:8],
        "gateway": gateway.upper(),
        "error_json": str(gateway_error),
        "features": features_text,
    })
    return response.content


async def _llm_explain_fraud(
    transaction_id: str,
    fraud_prob: float,
    sorted_features: list[tuple[str, float]],
    features: dict[str, Any],
) -> str:
    """Use LangChain + OpenAI to generate a fraud rejection explanation."""
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate

    llm = ChatOpenAI(
        model=settings.openai_model or "gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.3,
        max_tokens=500,
    )

    features_text = "\n".join(
        f"  - {f}: {v:+.4f}" for f, v in sorted_features
    )

    prompt = ChatPromptTemplate.from_template(
        "You are an AI fraud analyst. "
        "A payment transaction (ID: {txn_id}) was REJECTED with fraud score {fraud_pct}%.\n\n"
        "Transaction features: Amount=${amount}, Email domain={email}, Device={device}\n\n"
        "Top SHAP risk factors:\n{features}\n\n"
        "Provide a clear, concise explanation for why this transaction was flagged as fraudulent. "
        "Use professional language suitable for a merchant dashboard."
    )

    chain = prompt | llm
    response = await chain.ainvoke({
        "txn_id": transaction_id[:8],
        "fraud_pct": f"{fraud_prob*100:.1f}",
        "amount": features.get("TransactionAmt", 0),
        "email": features.get("P_emaildomain", "unknown"),
        "device": features.get("DeviceInfo", "unknown"),
        "features": features_text,
    })
    return response.content
