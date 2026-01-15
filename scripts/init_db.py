import sqlite3
import os

# Get project root directory (two levels up from this script)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Build full paths to database and schema
db_path = os.path.join(project_root, "data", "expensior.db")
schema_path = os.path.join(project_root, "sql", "schema.sql")

# Connect to database and apply schema
conn = sqlite3.connect(db_path)
with open(schema_path, "r", encoding="utf-8") as f:
    conn.executescript(f.read())

conn.commit()
conn.close()

print(f"DB initialized at: {db_path}")
