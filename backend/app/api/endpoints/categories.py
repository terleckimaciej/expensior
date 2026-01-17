
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3

from app.core.database import get_db_connection
from app.schemas.category import Category, SubCategory

router = APIRouter()

def get_db():
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()

@router.get("/", response_model=List[Category])
def read_categories(db: sqlite3.Connection = Depends(get_db)):
    """
    Get all categories with their subcategories structured hierarchically.
    """
    # Fetch all categories
    cursor = db.execute("SELECT id, name, parent_id FROM categories ORDER BY name")
    rows = cursor.fetchall()
    
    # Organize into dicts
    categories_map = {}
    roots = []
    
    # First pass: Create objects
    raw_cats = []
    for row in rows:
        cat_dict = dict(row)
        cat_dict['subcategories'] = []
        raw_cats.append(cat_dict)
        categories_map[cat_dict['id']] = cat_dict

    # Second pass: Build tree
    for cat in raw_cats:
        if cat['parent_id'] is None:
            roots.append(cat)
        else:
            parent = categories_map.get(cat['parent_id'])
            if parent:
                parent['subcategories'].append(cat)
    
    return roots
