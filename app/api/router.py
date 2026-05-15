"""
ATLAS-OPS API Router — mounts all endpoint sub-routers under /v1.
"""
from fastapi import APIRouter

from app.api import auth, gateways, ml, pipeline, simulate, transaction

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router)
api_router.include_router(transaction.router)
api_router.include_router(pipeline.router)
api_router.include_router(gateways.router)
api_router.include_router(simulate.router)
api_router.include_router(ml.router)
