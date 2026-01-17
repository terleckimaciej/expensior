import sqlite3
from .config import DB_PATH

def get_db_connection():
    """
    Returns a raw sqlite3 connection (compatible with pandas).
    """
    # Ensure the directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    # conn.row_factory = sqlite3.Row # Optional, but good for dict-like access
    return conn
