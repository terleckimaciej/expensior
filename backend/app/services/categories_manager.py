
import csv
import sqlite3
import os
from typing import Optional

def load_categories_from_csv(conn: sqlite3.Connection, csv_path: str, clear_existing: bool = False):
    """
    Load categories from CSV file into the categories table.
    Expected CSV format: category,subcategory
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        if clear_existing:
            conn.execute('DELETE FROM categories')
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Cache for parent categories to avoid repeated lookups
            # Key: Category Name, Value: ID
            parent_cache = {}

            # Pre-load existing parents if not clearing
            if not clear_existing:
                cursor = conn.execute("SELECT name, id FROM categories WHERE parent_id IS NULL")
                for name, pid in cursor.fetchall():
                    parent_cache[name] = pid

            for row in reader:
                category = row.get('category', '').strip()
                subcategory = row.get('subcategory', '').strip()

                if not category:
                    continue

                # 1. Handle Parent Category
                parent_id = parent_cache.get(category)
                
                if parent_id is None:
                    # Insert new parent
                    try:
                        cursor = conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, NULL)", (category,))
                        parent_id = cursor.lastrowid
                        parent_cache[category] = parent_id
                    except sqlite3.IntegrityError:
                        # Race condition or already exists (and not in cache?)
                        cursor = conn.execute("SELECT id FROM categories WHERE name = ? AND parent_id IS NULL", (category,))
                        res = cursor.fetchone()
                        if res:
                            parent_id = res[0]
                            parent_cache[category] = parent_id
                
                # 2. Handle Subcategory
                if subcategory:
                    # Insert child linked to parent
                    try:
                        conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (subcategory, parent_id))
                    except sqlite3.IntegrityError:
                        # Already exists, skip
                        pass
        
        conn.commit()
        print(f"Categories imported successfully from {csv_path}")

    except Exception as e:
        conn.rollback()
        raise e
