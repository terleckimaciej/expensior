import csv
import sqlite3
import os

def load_rules_from_csv(conn: sqlite3.Connection, csv_path: str, clear_existing: bool = False):
    """
    Load rules from CSV file into the rules table.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Use existing transaction or start a new one?
    # Since we are passed a connection, we should let the caller manage the transaction or manage it here carefully.
    # The original script did 'BEGIN'.
    # We can try/except block here.
    
    try:
        # Check if we are already in a transaction? sqlite3 doesn't easily convert this.
        # But commonly we can just execute commands.
        
        if clear_existing:
            conn.execute('DELETE FROM rules')
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows_inserted = 0
            
            for row in reader:
                # Skip empty or invalid rows
                if not row.get('pattern') or not row.get('match_type') or not row.get('source_column'):
                    # print(f"Skipping invalid row: {row}")
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
                
                # Resolve category_id
                category_id = None
                if category:
                    # Try exact match first
                    if subcategory:
                        cur = conn.execute("""
                            SELECT c.category_id 
                            FROM categories c
                            JOIN categories p ON c.parent_id = p.category_id
                            WHERE c.category = ? AND p.category = ?
                        """, (subcategory, category))
                        res = cur.fetchone()
                        if res:
                            category_id = res[0]
                    
                    if not category_id:
                        # Try just parent category
                        cur = conn.execute("SELECT category_id FROM categories WHERE category = ? AND parent_id IS NULL", (category,))
                        res = cur.fetchone()
                        if res:
                            category_id = res[0]

                conn.execute(
                    """
                    INSERT INTO rules 
                    (pattern, match_type, source_column, merchant, category, subcategory, category_id, conditions, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pattern, match_type, source_column, merchant, category, subcategory, category_id, conditions, priority)
                )
                rows_inserted += 1
        
        # conn.commit() # Caller should commit
        return rows_inserted
        
    except Exception as e:
        # conn.rollback() # Caller should rollback
        raise e
