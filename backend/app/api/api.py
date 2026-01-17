from fastapi import APIRouter
from app.api.endpoints import transactions, categories

api_router = APIRouter()
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])

# Future routers:
# api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
# api_router.include_router(importing.router, prefix="/import", tags=["import"])
