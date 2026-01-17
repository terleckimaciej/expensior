import sqlite3
import os
from .config import DB_PATH

def get_db_connection():
    """
    Returns a raw sqlite3 connection.
    """
    # Debug: Print where we are looking for the DB
    if not os.path.exists(DB_PATH):
        print(f"CRITICAL ERROR: Database file not found at: {DB_PATH}")
        # We assume the API strictly needs the DB to exist.
    
    # Enable check_same_thread=False to avoid threading issues with FastAPI reloading
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return conn
