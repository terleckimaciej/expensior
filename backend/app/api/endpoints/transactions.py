from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import sqlite3

from app.core.database import get_db_connection
from app.schemas.transaction import Transaction, TransactionUpdate

router = APIRouter()

# Dependency to get DB connection per request (and close it after)
def get_db():
    conn = get_db_connection()
    try:
        # Enable row factory to access columns by name
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()

@router.get("/", response_model=List[Transaction])
def read_transactions(
    skip: int = 0,
    limit: int = 50,
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Get list of transactions.
    """
    # We join with classifications to get the CURRENT category for each transaction
    query = """
    SELECT 
        t.*,
        tc.category,
        tc.subcategory,
        tc.category_id,
        tc.merchant
    FROM transactions t
    LEFT JOIN transaction_classifications tc 
        ON t.transaction_id = tc.transaction_id 
        AND tc.is_current = 1
    ORDER BY t.date DESC
    LIMIT ? OFFSET ?
    """
    cursor = db.execute(query, (limit, skip))
    rows = cursor.fetchall()
    
    # Convert sqlite3.Row objects to dicts matching our Schema
    results = []
    for row in rows:
        results.append(dict(row))
    
    return results

@router.get("/{transaction_id}", response_model=Transaction)
def read_transaction(transaction_id: str, db: sqlite3.Connection = Depends(get_db)):
    query = """
    SELECT 
        t.*,
        tc.category,
        tc.subcategory,
        tc.category_id,
        tc.merchant
    FROM transactions t
    LEFT JOIN transaction_classifications tc 
        ON t.transaction_id = tc.transaction_id 
        AND tc.is_current = 1
    WHERE t.transaction_id = ?
    """
    cursor = db.execute(query, (transaction_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return dict(row)
