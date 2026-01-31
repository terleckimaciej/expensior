import os
import shutil
import uuid
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.core.database import get_db_connection
from app.core.config import DATA_DIR
from app.services.importer import import_file

router = APIRouter()

# Directory for temporary uploads
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Dependency to get DB connection per request
def get_db():
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()

@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    on_conflict: str = "ignore",
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Receive a CSV file, save it to data/uploads/, process it, and cleanup.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    # Generate unique filename to avoid collisions in data/uploads/
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_path = UPLOAD_DIR / unique_filename

    try:
        # 1. Save uploaded file to the data/uploads folder
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Call the existing importer service
        # Note: import_file expects a string path
        result = import_file(str(temp_path), db, on_conflict=on_conflict)
        
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 3. Clean up the temporary file
        if temp_path.exists():
            temp_path.unlink()
