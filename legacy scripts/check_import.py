import sqlite3

conn = sqlite3.connect('d:/repos/expensior/data/expensior.db')

total = conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
synthetic = conn.execute('SELECT COUNT(*) FROM transactions WHERE transaction_id LIKE "synthetic-%"').fetchone()[0]
row_suffix = conn.execute('SELECT COUNT(*) FROM transactions WHERE transaction_id LIKE "%-row%"').fetchone()[0]

print(f"Total transactions: {total}")
print(f"Synthetic IDs: {synthetic}")
print(f"Row-suffixed IDs: {row_suffix}")
print(f"Natural IDs: {total - synthetic - row_suffix}")

conn.close()
