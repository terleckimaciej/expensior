import sqlite3
import os
import sys

# Add project root to path to allow importing from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.core.config import DB_PATH

def rollback_last_batch():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        
        # 1. Find the most recent batch
        cur.execute("SELECT import_batch_id, source_file_name, imported_at FROM import_batches ORDER BY imported_at DESC LIMIT 1")
        batch = cur.fetchone()
        
        if not batch:
            print("No import batches found in the database.")
            return
        
        batch_id, file_name, imported_at = batch
        print(f"Found last batch: {batch_id}")
        print(f"File: {file_name}")
        print(f"Imported at: {imported_at}")
        
        confirm = input("\nAre you sure you want to delete this batch and all its transactions? (y/n): ")
        if confirm.lower() != 'y':
            print("Abort.")
            return

        conn.execute("BEGIN")
        
        # 2. Delete transactions
        cur.execute("DELETE FROM transactions WHERE import_batch_id = ?", (batch_id,))
        tx_deleted = cur.rowcount
        
        # 3. Delete batch record
        cur.execute("DELETE FROM import_batches WHERE import_batch_id = ?", (batch_id,))
        
        conn.commit()
        print(f"\nSuccessfully rolled back:")
        print(f"- Deleted {tx_deleted} transactions.")
        print(f"- Removed batch record {batch_id}.")

    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    rollback_last_batch()
