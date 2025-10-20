from fastapi import APIRouter

from .routes import comparisons, health, uploads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(uploads.router, prefix="/documents")
api_router.include_router(comparisons.router)
