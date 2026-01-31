"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, query, schema, database

# Create API v1 router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(query.router)
api_router.include_router(schema.router)
api_router.include_router(database.router)
