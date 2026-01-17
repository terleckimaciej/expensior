import sys
import os
import sqlite3
from typing import List

# Add backend to path so we can import modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.database import get_db_connection
from app.schemas.transaction import Transaction

def test_query():
    print("1. Connecting to DB...")
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        print("   Success.")
    except Exception as e:
        print(f"   FAIL: {e}")
        return

    print("2. Running SQL Query...")
    query = """
    SELECT 
        t.*,
        tc.category,
        tc.subcategory,
        tc.merchant
    FROM transactions t
    LEFT JOIN transaction_classifications tc 
        ON t.transaction_id = tc.transaction_id 
        AND tc.is_current = 1
    ORDER BY t.date DESC
    LIMIT 5
    """
    try:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        print(f"   Success. Retrieved {len(rows)} rows.")
    except Exception as e:
        print(f"   FAIL: {e}")
        return

    print("3. Validating Data with Pydantic Schema...")
    for i, row in enumerate(rows):
        data = dict(row)
        print(f"   Row {i} keys: {list(data.keys())}")
        try:
            # Try to parse
            obj = Transaction(**data)
            print(f"   Row {i} OK: {obj.transaction_id}")
        except Exception as e:
            print(f"   Row {i} VALIDATION ERROR: {e}")
            print(f"   Data content: {data}")
            return

    print("Done. Everything seems correct.")

if __name__ == "__main__":
    test_query()
