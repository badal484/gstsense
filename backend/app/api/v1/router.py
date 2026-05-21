from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    ca_firms,
    dashboard,
    itc,
    notices,
    organizations,
    payments,
    preferences,
    scans,
    subscriptions,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(scans.router)
api_router.include_router(payments.router)
api_router.include_router(organizations.router)
api_router.include_router(itc.router)
api_router.include_router(notices.router)
api_router.include_router(ca_firms.router)
api_router.include_router(dashboard.router)
api_router.include_router(preferences.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin.router)
