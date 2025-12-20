CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    date TEXT,
    amount REAL,
    currency TEXT,
    transaction_type TEXT,
    description TEXT,
    merchant TEXT,
    category TEXT,
    subcategory TEXT,
    rule_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    match_type TEXT NOT NULL,
    source_column TEXT NOT NULL,
    merchant TEXT,
    category TEXT,
    subcategory TEXT,
    priority INTEGER NOT NULL,
    conditions TEXT
);
