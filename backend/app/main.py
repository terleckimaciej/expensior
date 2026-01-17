from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Setup app
app = FastAPI(title="Expensior API")

@app.get("/")
def read_root():
    return {"Hello": "Expensior"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# TODO: Include routers
# from .api import transactions
# app.include_router(transactions.router)
