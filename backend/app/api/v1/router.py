from fastapi import APIRouter

from app.api.v1 import auth, organizations, payments, scans

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(scans.router)
api_router.include_router(payments.router)
api_router.include_router(organizations.router)
