import argparse
import sys
import os

# Ensure backend folder is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import get_db_connection
from app.services.importer import import_file
from app.services.classifier import run_classification

def cmd_import(args):
    """Import CSV file."""
    conn = get_db_connection()
    try:
        print(f"Importing {args.input}...")
        result = import_file(args.input, conn, on_conflict=args.on_conflict, dry_run=args.dry_run)
        print("Import Results:", result)
    finally:
        conn.close()

def cmd_classify(args):
    """Run classification."""
    conn = get_db_connection()
    try:
        print("Running classification...")
        result = run_classification(conn, dry_run=args.dry_run)
        print("Classification Results:", result)
    finally:
        conn.close()

def cmd_init_db(args):
    """Initialize database (simple wrapper)."""
    # This roughly mimics init_db.py but using the config
    from app.core.config import DB_PATH, SQL_DIR
    import sqlite3
    
    print(f"Initializing DB at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    schema_path = SQL_DIR / "schema.sql"
    
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    
    conn.commit()
    conn.close()
    print("Done.")

def main():
    parser = argparse.ArgumentParser(description="Expensior Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import Command
    import_parser = subparsers.add_parser("import", help="Import a bank CSV")
    import_parser.add_argument("input", help="Path to CSV file")
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.add_argument("--on-conflict", choices=['ignore', 'replace', 'abort'], default='ignore')
    import_parser.set_defaults(func=cmd_import)

    # Classify Command
    classify_parser = subparsers.add_parser("classify", help="Run rules on unclassified transactions")
    classify_parser.add_argument("--dry-run", action="store_true")
    classify_parser.set_defaults(func=cmd_classify)

    # Init DB Command
    init_parser = subparsers.add_parser("init-db", help="Initialize database from schema")
    init_parser.set_defaults(func=cmd_init_db)

    args = parser.parse_args()
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
