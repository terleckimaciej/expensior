import sqlite3

conn = sqlite3.connect("db/expensior.db")

with open("sql/schema.sql", "r", encoding="utf-8") as f:
    conn.executescript(f.read())

conn.commit()
conn.close()

print("DB initialized")
