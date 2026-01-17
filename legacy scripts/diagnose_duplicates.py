import argparse
import os
import sqlite3
import sys

import pandas as pd

# Import transform from extract_transform
sys.path.insert(0, os.path.dirname(__file__))
from extract_transform import transform

def main():
    parser = argparse.ArgumentParser(description="Diagnose duplicate transaction_ids")
    parser.add_argument('--input', required=True, help='Path to input CSV')
    parser.add_argument('--db', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'expensior.db'))
    args = parser.parse_args()

    # Load and transform
    print(f"Loading CSV: {args.input}")
    df = pd.read_csv(args.input, encoding='latin2')
    df_std = transform(df)
    
    print(f"\nTotal rows in CSV: {len(df_std)}")
    
    # Check for duplicates in DataFrame
    print("\n" + "="*60)
    print("1. DUPLICATES IN SOURCE DATA")
    print("="*60)
    
    dup_mask = df_std['transaction_id'].duplicated(keep=False)
    duplicates_in_source = df_std[dup_mask].sort_values('transaction_id')
    
    if len(duplicates_in_source) > 0:
        print(f"Found {len(duplicates_in_source)} rows with duplicate transaction_ids in source")
        print(f"Unique duplicate transaction_ids: {df_std[dup_mask]['transaction_id'].nunique()}")
        print("\nSample duplicates:")
        print(duplicates_in_source[['transaction_id', 'date', 'transaction_type', 'amount', 'description']].head(10))
    else:
        print("No duplicates in source data")
    
    # Check against DB
    print("\n" + "="*60)
    print("2. DUPLICATES ALREADY IN DATABASE")
    print("="*60)
    
    conn = sqlite3.connect(args.db)
    
    # Get all transaction_ids from DB
    existing_ids = pd.read_sql_query("SELECT transaction_id FROM transactions", conn)
    existing_set = set(existing_ids['transaction_id'])
    
    print(f"Total transactions in DB: {len(existing_ids)}")
    
    # Find which IDs from CSV are already in DB
    df_std['already_in_db'] = df_std['transaction_id'].isin(existing_set)
    already_exists = df_std[df_std['already_in_db']]
    
    if len(already_exists) > 0:
        print(f"Found {len(already_exists)} rows that already exist in DB")
        print("\nSample existing transactions:")
        print(already_exists[['transaction_id', 'date', 'transaction_type', 'amount', 'description']].head(10))
        
        # Show which batches they came from
        existing_tx_ids = tuple(already_exists['transaction_id'].tolist()[:100])  # limit for SQL
        if len(existing_tx_ids) == 1:
            batch_query = f"SELECT DISTINCT import_batch_id FROM transactions WHERE transaction_id = '{existing_tx_ids[0]}'"
        else:
            batch_query = f"SELECT DISTINCT import_batch_id FROM transactions WHERE transaction_id IN {existing_tx_ids}"
        
        batches = pd.read_sql_query(batch_query, conn)
        print(f"\nThese transactions came from {len(batches)} batch(es):")
        for batch_id in batches['import_batch_id']:
            batch_info = pd.read_sql_query(
                "SELECT * FROM import_batches WHERE import_batch_id = ?", 
                conn, 
                params=(batch_id,)
            )
            print(f"  - {batch_id}")
            print(f"    File: {batch_info['source_file_name'].iloc[0]}")
            print(f"    Imported: {batch_info['imported_at'].iloc[0]}")
            print(f"    Row count: {batch_info['row_count'].iloc[0]}")
    else:
        print("No rows from CSV already exist in DB")
    
    # Summary
    print("\n" + "="*60)
    print("3. SUMMARY")
    print("="*60)
    print(f"Rows in CSV: {len(df_std)}")
    print(f"Duplicates within CSV: {len(duplicates_in_source)}")
    print(f"Already in DB: {len(already_exists)}")
    print(f"Would be inserted: {len(df_std) - len(duplicates_in_source.drop_duplicates('transaction_id')) - len(already_exists)}")
    
    # Check for empty/null transaction_ids
    null_ids = df_std[df_std['transaction_id'].isna() | (df_std['transaction_id'] == '')]
    if len(null_ids) > 0:
        print(f"\n⚠️  WARNING: {len(null_ids)} rows have empty/null transaction_id!")
        print(null_ids[['date', 'transaction_type', 'amount', 'description']].head(10))
    
    conn.close()


if __name__ == '__main__':
    main()
