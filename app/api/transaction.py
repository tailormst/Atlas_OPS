"""
POST /v1/transaction/process — Standard (non-streaming) transaction endpoint.
GET  /v1/transaction/{txn_id}/explain — Fetch explanation for a transaction.
GET  /v1/transactions — Paginated transaction list.
GET  /v1/transactions/{txn_id} — Single transaction detail.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, col, func

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ml_result import MLResult
from app.models.schemas import TransactionRequest
from app.models.transaction import Transaction, TransactionStatus
from app.services.failure_service import FailureService
from app.services.fraud_service import FraudService
from app.services.gateway_service import GatewayService
from app.services.rag_explainer import RAGExplainerService
from app.services.routing_service import RoutingService

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)


@router.post(
    "/transaction/process",
    summary="Process a transaction (non-streaming)",
    tags=["Transactions"],
)
async def process_transaction(
    payload: TransactionRequest,
    db: AsyncSession = Depends(get_db),
):
    txn_id = uuid.uuid4()
    start = time.monotonic()

    # ── Fraud Scoring ────────────────────────────────────────────────────
    fraud_features = {
        "TransactionAmt": payload.amount,
        "card1": payload.card1,
        "card2": payload.card2,
        "P_emaildomain": payload.email_domain,
        "addr1": payload.addr1,
        "addr2": payload.addr2,
        "DeviceType": payload.device_type,
        "DeviceInfo": payload.device_info,
        "dist1": payload.dist1,
        "dist2": payload.dist2,
    }
    fraud_prob, fraud_shap = await FraudService.score(fraud_features)
    fraud_flag = fraud_prob >= settings.fraud_threshold

    transaction = Transaction(
        id=txn_id,
        amount=payload.amount,
        card1=payload.card1,
        card2=payload.card2,
        email_domain=payload.email_domain,
        addr1=payload.addr1,
        addr2=payload.addr2,
        device_type=payload.device_type,
        device_info=payload.device_info,
        dist1=payload.dist1,
        dist2=payload.dist2,
        fraud_score=fraud_prob,
        fraud_flag=fraud_flag,
    )
    db.add(transaction)

    # ── Fraud Rejection ──────────────────────────────────────────────────
    if fraud_flag:
        transaction.status = TransactionStatus.REJECTED
        db.add(MLResult(
            transaction_id=txn_id,
            model_name="fraud",
            prediction=fraud_prob,
            confidence=fraud_prob,
            shap_values=fraud_shap,
            raw_features=fraud_features,
        ))
        explanation = await RAGExplainerService.explain_fraud_rejection(
            str(txn_id), fraud_prob, fraud_shap, fraud_features
        )
        await db.commit()
        elapsed = round((time.monotonic() - start) * 1000, 1)
        return {
            "transaction_id": str(txn_id),
            "status": "REJECTED",
            "fraud_score": round(fraud_prob, 4),
            "fraud_flag": True,
            "explanation": explanation,
            "shap_values": fraud_shap,
            "elapsed_ms": elapsed,
        }

    # ── Routing ──────────────────────────────────────────────────────────
    all_health = await GatewayService.get_all_health(db)
    health_map = {
        gh.gateway_name: {
            "success_rate": gh.success_rate,
            "avg_latency_ms": gh.avg_latency_ms,
            "circuit_state": gh.circuit_state,
            "total_requests": gh.total_requests,
        }
        for gh in all_health
    }
    selected_gateway, gateway_scores = await RoutingService.select_gateway(health_map)
    transaction.selected_gateway = selected_gateway

    # ── Gateway Execution ────────────────────────────────────────────────
    gw_result = await GatewayService.execute(selected_gateway, fraud_features, db)

    if gw_result["success"]:
        transaction.status = TransactionStatus.APPROVED
        transaction.gateway_response = gw_result["gateway_response"]
        await db.commit()
        elapsed = round((time.monotonic() - start) * 1000, 1)
        return {
            "transaction_id": str(txn_id),
            "status": "APPROVED",
            "fraud_score": round(fraud_prob, 4),
            "selected_gateway": selected_gateway,
            "gateway_response": gw_result["gateway_response"],
            "elapsed_ms": elapsed,
        }

    # ── Reroute ──────────────────────────────────────────────────────────
    sorted_gateways = sorted(
        [(gw, s) for gw, s in gateway_scores.items() if s > 0 and gw != selected_gateway],
        key=lambda x: x[1], reverse=True,
    )
    if sorted_gateways:
        reroute_gw = sorted_gateways[0][0]
        reroute_result = await GatewayService.execute(reroute_gw, fraud_features, db)
        if reroute_result["success"]:
            transaction.status = TransactionStatus.REROUTED
            transaction.selected_gateway = reroute_gw
            transaction.rerouted_from = selected_gateway
            transaction.gateway_response = reroute_result["gateway_response"]
            await db.commit()
            elapsed = round((time.monotonic() - start) * 1000, 1)
            return {
                "transaction_id": str(txn_id),
                "status": "REROUTED",
                "fraud_score": round(fraud_prob, 4),
                "selected_gateway": reroute_gw,
                "rerouted_from": selected_gateway,
                "elapsed_ms": elapsed,
            }

    # ── Full Failure ─────────────────────────────────────────────────────
    gateway_error = gw_result.get("gateway_error", {})
    failure_prob, diagnosis = await FailureService.diagnose(gateway_error, fraud_shap)
    explanation = await RAGExplainerService.explain(
        str(txn_id), {**fraud_shap, **diagnosis.get("shap_values", {})},
        gateway_error, selected_gateway,
    )

    if gateway_error.get("timeout_flag"):
        transaction.status = TransactionStatus.TIMEOUT
    else:
        transaction.status = TransactionStatus.FAILED

    transaction.gateway_response = gateway_error
    db.add(MLResult(
        transaction_id=txn_id,
        model_name="failure",
        prediction=failure_prob,
        confidence=failure_prob,
        shap_values=diagnosis.get("shap_values"),
        raw_features=gateway_error,
        llm_explanation=explanation,
    ))
    await db.commit()
    elapsed = round((time.monotonic() - start) * 1000, 1)
    return {
        "transaction_id": str(txn_id),
        "status": transaction.status.value,
        "fraud_score": round(fraud_prob, 4),
        "selected_gateway": selected_gateway,
        "failure_probability": round(failure_prob, 4),
        "explanation": explanation,
        "elapsed_ms": elapsed,
    }


@router.get(
    "/transaction/{txn_id}/explain",
    summary="Get AI explanation for a transaction",
    tags=["Transactions"],
)
async def explain_transaction(
    txn_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        txn_uuid = uuid.UUID(txn_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction ID format")

    result = await db.execute(
        select(Transaction).where(Transaction.id == txn_uuid)
    )
    txn = result.scalar_one_or_none()
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Get ML results
    ml_results = await db.execute(
        select(MLResult).where(MLResult.transaction_id == txn_uuid)
    )
    ml_rows = ml_results.scalars().all()

    response = {
        "transaction_id": str(txn.id),
        "status": txn.status.value,
        "amount": txn.amount,
        "fraud_score": txn.fraud_score,
        "fraud_flag": txn.fraud_flag,
        "selected_gateway": txn.selected_gateway,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
    }

    for ml in ml_rows:
        if ml.model_name == "fraud":
            response["fraud_shap_values"] = ml.shap_values
        elif ml.model_name == "failure":
            response["failure_shap_values"] = ml.shap_values
            response["llm_explanation"] = ml.llm_explanation

    return response


@router.get(
    "/transactions",
    summary="List transactions with pagination",
    tags=["Transactions"],
)
async def list_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: APPROVED, REJECTED, FAILED, etc."),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    query = select(Transaction).order_by(col(Transaction.created_at).desc())

    if status:
        try:
            status_enum = TransactionStatus(status.upper())
            query = query.where(Transaction.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Count total
    count_query = select(func.count()).select_from(Transaction)
    if status:
        count_query = count_query.where(Transaction.status == TransactionStatus(status.upper()))
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch page
    result = await db.execute(query.offset(offset).limit(per_page))
    transactions = result.scalars().all()

    return {
        "transactions": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "status": t.status.value,
                "fraud_score": t.fraud_score,
                "fraud_flag": t.fraud_flag,
                "selected_gateway": t.selected_gateway,
                "rerouted_from": t.rerouted_from,
                "email_domain": t.email_domain,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }