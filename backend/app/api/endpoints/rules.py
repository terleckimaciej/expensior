
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3

from app.core.database import get_db_connection
from app.schemas.rule import Rule, RuleCreate, RuleUpdate

router = APIRouter()

def get_db():
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()

def resolve_category_id(db: sqlite3.Connection, category: str, subcategory: str = None) -> int:
    """
    Helper to find category_id based on names.
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
    # Note: If user provided a subcategory that doesn't match the parent in DB, 
    # we might fallback to parent ID or leave None. This logic prioritizes exact match.
    if cat_id is None:
        query = "SELECT category_id FROM categories WHERE category = ? AND parent_id IS NULL"
        cur = db.execute(query, (category,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
            
    return cat_id

@router.get("/", response_model=List[Rule])
def read_rules(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.execute("""
        SELECT id, pattern, match_type, source_column, merchant, 
               category, subcategory, category_id, conditions, priority 
        FROM rules 
        ORDER BY priority DESC, id DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@router.post("/", response_model=Rule)
def create_rule(rule: RuleCreate, db: sqlite3.Connection = Depends(get_db)):
    # 1. Resolve category_id
    cat_id = resolve_category_id(db, rule.category, rule.subcategory)
    
    # 2. Insert
    query = """
        INSERT INTO rules (pattern, match_type, source_column, merchant, 
                           category, subcategory, category_id, conditions, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor = db.execute(query, (
        rule.pattern, rule.match_type, rule.source_column, rule.merchant,
        rule.category, rule.subcategory, cat_id, rule.conditions, rule.priority
    ))
    db.commit()
    new_id = cursor.lastrowid
    
    return {**rule.dict(), "id": new_id, "category_id": cat_id}

@router.put("/{rule_id}", response_model=Rule)
def update_rule(rule_id: int, rule: RuleUpdate, db: sqlite3.Connection = Depends(get_db)):
    # Check if exists
    check = db.execute("SELECT id FROM rules WHERE id = ?", (rule_id,)).fetchone()
    if not check:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    # 1. Resolve category_id
    cat_id = resolve_category_id(db, rule.category, rule.subcategory)
    
    # 2. Update
    query = """
        UPDATE rules 
        SET pattern=?, match_type=?, source_column=?, merchant=?,
            category=?, subcategory=?, category_id=?, conditions=?, priority=?
        WHERE id = ?
    """
    db.execute(query, (
        rule.pattern, rule.match_type, rule.source_column, rule.merchant,
        rule.category, rule.subcategory, cat_id, rule.conditions, rule.priority,
        rule_id
    ))
    db.commit()
    
    return {**rule.dict(), "id": rule_id, "category_id": cat_id}

@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    db.commit()
    return {"message": "Rule deleted"}
