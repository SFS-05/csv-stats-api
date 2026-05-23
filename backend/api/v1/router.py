"""
API v1 router — aggregates all endpoint routers.
"""
from fastapi import APIRouter

from backend.api.v1.endpoints.auth import router as auth_router
from backend.api.v1.endpoints.datasets import router as datasets_router
from backend.api.v1.endpoints.jobs import router as jobs_router
from backend.api.v1.endpoints.visualizations import router as viz_router
from backend.api.v1.endpoints.ai import router as ai_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(datasets_router)
api_router.include_router(jobs_router)
api_router.include_router(viz_router)
api_router.include_router(ai_router)