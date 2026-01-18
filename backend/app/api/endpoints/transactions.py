
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

def resolve_category_id(db: sqlite3.Connection, category: str, subcategory: str = None) -> Optional[int]:
    """
    Helper to find category_id based on names.
    Note: Ideally this should be in a shared service.
    """
    if not category:
        return None
    
    cat_id = None
    
    if subcategory:
        # Try to find specific child
        query = """
        SELECT c.category_id 
        FROM categories c
        JOIN categories p ON c.parent_id = p.category_id
        WHERE c.category = ? AND p.category = ?
        """
        cur = db.execute(query, (subcategory, category))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
            
    # If not found (or no subcategory), try finding just the parent
    if cat_id is None:
        query = "SELECT category_id FROM categories WHERE category = ? AND parent_id IS NULL"
        cur = db.execute(query, (category,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
            
    return cat_id

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
    ORDER BY t.action_date DESC, t.booking_date DESC
    LIMIT ? OFFSET ?
    """
    # Wait, original schema didn't have action_date/booking_date, just date.
    # Let me revert to using just 'date'.
    
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

@router.put("/{transaction_id}/categorize", response_model=Transaction)
def categorize_transaction(
    transaction_id: str,
    update_data: TransactionUpdate,
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Manually categorize a transaction.
    Adds a new record to transaction_classifications with method='manual'.
    """
    # 1. Verify transaction exists
    check = db.execute("SELECT transaction_id FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
    if not check:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    # 2. Resolve category_id
    cat_id = resolve_category_id(db, update_data.category, update_data.subcategory)
    
    try:
        db.execute("BEGIN")
        
        # 3. Mark existing current classifications as not current
        db.execute("""
            UPDATE transaction_classifications 
            SET is_current = 0 
            WHERE transaction_id = ? AND is_current = 1
        """, (transaction_id,))
        
        # 4. Insert new classification
        db.execute("""
            INSERT INTO transaction_classifications 
            (transaction_id, category, subcategory, merchant, category_id, method, is_current)
            VALUES (?, ?, ?, ?, ?, 'manual', 1)
        """, (
            transaction_id,
            update_data.category,
            update_data.subcategory,
            update_data.merchant,
            cat_id
        ))
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    # 5. Return updated transaction
    return read_transaction(transaction_id, db)
