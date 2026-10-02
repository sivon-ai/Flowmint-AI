"""Aggregate API v1 router."""

from fastapi import APIRouter

from app.api.v1.action_plans import router as action_plans_router
from app.api.v1.actions import router as actions_router
from app.api.v1.agents import router as agents_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.carts import router as carts_router
from app.api.v1.customers import router as customers_router
from app.api.v1.health import router as health_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.policies import router as policies_router
from app.api.v1.products import router as products_router
from app.api.v1.simulations import router as simulations_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(inventory_router)
api_router.include_router(customers_router)
api_router.include_router(carts_router)
api_router.include_router(orders_router)
api_router.include_router(payments_router)
api_router.include_router(agents_router)
api_router.include_router(opportunities_router)
api_router.include_router(simulations_router)
api_router.include_router(action_plans_router)
api_router.include_router(policies_router)
api_router.include_router(actions_router)
api_router.include_router(approvals_router)
api_router.include_router(audit_router)


