
import sqlite3
from app.core.database import get_db_connection
from app.services.categories_manager import load_categories_from_csv

def init_categories_db():
    conn = get_db_connection()
    try:
        # 1. Create the table if it doesn't exist (using the schema definition logic)
        print("Ensuring categories table exists...")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
          id               INTEGER PRIMARY KEY AUTOINCREMENT,
          name             TEXT NOT NULL,
          parent_id        INTEGER,

          FOREIGN KEY (parent_id) REFERENCES categories(id)
            ON DELETE CASCADE,

          UNIQUE(name, parent_id)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);")
        
        # 2. Import from CSV
        csv_path = 'data/categories.csv'
        print(f"Importing categories from {csv_path}...")
        load_categories_from_csv(conn, csv_path, clear_existing=False)
        
    except Exception as e:
        print(f"Error during category initialization: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_categories_db()
