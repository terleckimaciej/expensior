import argparse
import csv
import os
import sqlite3


def load_rules_from_csv(csv_path: str, db_path: str, clear_existing: bool = False):
    """
    Load rules from CSV file into the rules table.
    
    CSV columns expected:
    - id (ignored - DB auto-generates)
    - pattern
    - match_type
    - source_column
    - merchant (nullable)
    - category (nullable)
    - subcategory (nullable)
    - conditions (nullable JSON string)
    - priority
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN')
        
        if clear_existing:
            print("Clearing existing rules...")
            conn.execute('DELETE FROM rules')
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows_inserted = 0
            
            for row in reader:
                # Skip empty or invalid rows
                if not row.get('pattern') or not row.get('match_type') or not row.get('source_column'):
                    print(f"Skipping invalid row: {row}")
                    continue
                
                # Prepare values (handle empty strings as NULL)
                pattern = row['pattern'].strip()
                match_type = row['match_type'].strip()
                source_column = row['source_column'].strip()
                merchant = row.get('merchant', '').strip() or None
                category = row.get('category', '').strip() or None
                subcategory = row.get('subcategory', '').strip() or None
                conditions = row.get('conditions', '').strip() or None
                priority_str = row.get('priority', '10').strip()
                priority = int(priority_str) if priority_str else 10
                
                conn.execute(
                    """
                    INSERT INTO rules 
                    (pattern, match_type, source_column, merchant, category, subcategory, conditions, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pattern, match_type, source_column, merchant, category, subcategory, conditions, priority)
                )
                rows_inserted += 1
        
        conn.commit()
        print(f"✓ Successfully loaded {rows_inserted} rules into database")
        
        # Show summary
        cursor = conn.execute('SELECT COUNT(*) FROM rules')
        total = cursor.fetchone()[0]
        print(f"Total rules in DB: {total}")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error loading rules: {e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Load rules from CSV into SQLite DB")
    parser.add_argument(
        '--csv',
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'rules.csv'),
        help='Path to rules CSV file'
    )
    parser.add_argument(
        '--db',
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'expensior.db'),
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing rules before loading'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        return
    
    if not os.path.exists(args.db):
        print(f"Error: Database not found: {args.db}")
        print("Run init_db.py first to create the database.")
        return
    
    load_rules_from_csv(args.csv, args.db, args.clear)


if __name__ == '__main__':
    main()
