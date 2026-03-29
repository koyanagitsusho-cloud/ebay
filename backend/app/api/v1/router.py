"""APIルーター集約"""

from fastapi import APIRouter

from app.api.v1 import auth, auto_research, jobs, listings, research

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(research.router)
api_router.include_router(listings.router)
api_router.include_router(jobs.router)
api_router.include_router(auto_research.router)
