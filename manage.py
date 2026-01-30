import argparse
import sys
import os

# Ensure backend folder is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import get_db_connection
from app.services.importer import import_file
from app.services.classifier import run_classification
from app.services.rules_manager import load_rules_from_csv
from app.services.categories_manager import load_categories_from_csv

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

def cmd_load_rules(args):
    """Load rules from CSV."""
    from app.core.config import DATA_DIR
    default_csv = DATA_DIR / "rules.csv"
    
    csv_path = args.csv if args.csv else str(default_csv)
    
    print(f"Loading rules from {csv_path}...")
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        count = load_rules_from_csv(conn, csv_path, clear_existing=args.clear)
        conn.commit()
        print(f"Successfully loaded {count} rules.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

def cmd_load_categories(args):
    """Load categories from CSV."""
    from app.core.config import DATA_DIR
    default_csv = DATA_DIR / "categories.csv"
    
    csv_path = args.csv if args.csv else str(default_csv)
    
    print(f"Loading categories from {csv_path}...")
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        # Ensure foreign keys are on? Though load_categories handles one atomic operation usually.
        load_categories_from_csv(conn, csv_path, clear_existing=args.clear)
        conn.commit()
        # print success message inside function or here? function has print, but let's be safe
    except Exception as e:
        conn.rollback()
        print(f"Error loading categories: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Expensior Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import Command
    # Load Categories Command
    categories_parser = subparsers.add_parser("load-categories", help="Load categories from CSV")
    categories_parser.add_argument("--csv", help="Path to categories CSV")
    categories_parser.add_argument("--clear", action="store_true", help="Clear existing categories")
    categories_parser.set_defaults(func=cmd_load_categories)

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

    # Load Rules Command
    rules_parser = subparsers.add_parser("load-rules", help="Load rules from CSV")
    rules_parser.add_argument("--csv", help="Path to rules CSV")
    rules_parser.add_argument("--clear", action="store_true", help="Clear existing rules")
    rules_parser.set_defaults(func=cmd_load_rules)

    args = parser.parse_args()
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
