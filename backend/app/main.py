from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.api import api_router

# Setup app
app = FastAPI(title="Expensior API")

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"Hello": "Expensior API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# TODO: Include routers
# from .api import transactions
# app.include_router(transactions.router)
