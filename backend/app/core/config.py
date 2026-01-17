import os
from pathlib import Path

# Project root: expensior/backend/app/core -> ... -> expensior
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "expensior.db"
SQL_DIR = BASE_DIR / "sql"
