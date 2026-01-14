PRAGMA foreign_keys = ON;

-- ============================================================
-- 1) Import batches (import audit)
-- ============================================================
CREATE TABLE IF NOT EXISTS import_batches (
  import_batch_id   TEXT PRIMARY KEY,                -- e.g. file-hash+timestamp
  source_name       TEXT NOT NULL,                   
  source_file_name  TEXT,                            
  imported_at       TEXT NOT NULL DEFAULT (datetime('now')),
  row_count         INTEGER,                         
  status            TEXT NOT NULL DEFAULT 'ok'        -- 'ok' | 'partial' | 'failed'
);

CREATE INDEX IF NOT EXISTS idx_import_batches_imported_at
  ON import_batches(imported_at);

-- ============================================================
-- 2) Transactions (facts)
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
  transaction_id     TEXT PRIMARY KEY,               -- stable logical id
  date               TEXT NOT NULL,                  -- ISO 'YYYY-MM-DD'
  transaction_type   TEXT NOT NULL,                  -- e.g. 'CARD', 'TRANSFER', etc.
  amount             REAL NOT NULL,                  
  currency           TEXT NOT NULL DEFAULT 'PLN',
  description        TEXT NOT NULL,
  country            TEXT,                           -- optional bank reference 
  city               TEXT,                           -- optional bank reference
  import_batch_id    TEXT NOT NULL,
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (import_batch_id) REFERENCES import_batches(import_batch_id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_transactions_booking_date
  ON transactions(date);

CREATE INDEX IF NOT EXISTS idx_transactions_import_batch
  ON transactions(import_batch_id);

CREATE INDEX IF NOT EXISTS idx_transactions_amount
  ON transactions(amount);

-- ============================================================
-- 3) Rules (configuration)
--    Rules for automatic transaction classification
-- ============================================================
CREATE TABLE IF NOT EXISTS rules (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern          TEXT NOT NULL,                    -- text pattern to match
  match_type       TEXT NOT NULL,                    -- 'contains' | 'regex'
  source_column    TEXT NOT NULL,                    -- 'description' | 'transaction_type'
  merchant         TEXT,                             -- merchant name (nullable)
  category         TEXT,                             -- main category (nullable)
  subcategory      TEXT,                             -- subcategory (nullable)
  conditions       TEXT,                             -- JSON object for extra conditions (nullable)
  priority         INTEGER NOT NULL DEFAULT 10,      -- higher number = higher priority

  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_rules_match_type
  ON rules(match_type);

-- ============================================================
-- 4) Transaction classifications (category interpretation)
--    Supports history + manual overrides.
--    Exactly one is_current=1 per transaction should be maintained by app logic.
-- ============================================================
CREATE TABLE IF NOT EXISTS transaction_classifications (
  classification_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_id     TEXT NOT NULL,
  category           TEXT NOT NULL,
  subcategory        TEXT,                           -- optional
  merchant           TEXT,                           -- optional  
  method             TEXT NOT NULL,                  -- 'rule' | 'manual'
  rule_id            INTEGER,                        -- nullable when manual
  is_current         INTEGER NOT NULL DEFAULT 1,      -- 1=current, 0=historical
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,

  FOREIGN KEY (rule_id) REFERENCES rules(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_classif_tx_current
  ON transaction_classifications(transaction_id, is_current);

CREATE INDEX IF NOT EXISTS idx_tx_classif_current
  ON transaction_classifications(is_current);

CREATE INDEX IF NOT EXISTS idx_tx_classif_category_current
  ON transaction_classifications(category, is_current);

-- ============================================================
-- 5) Transaction flags (flag interpretation)
--    Flags are snake_case strings (e.g. 'is_reimbursement', 'is_savings').
--    A transaction can have multiple flags.
--    is_current allows history if you decide to version flags; otherwise keep current only.
-- ============================================================
CREATE TABLE IF NOT EXISTS transaction_flags (
  flag_row_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_id     TEXT NOT NULL,
  flag              TEXT NOT NULL,                   -- snake_case label
  method            TEXT NOT NULL,                   -- 'rule' | 'manual'
  rule_id           INTEGER,                         -- nullable when manual
  is_current        INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,

  FOREIGN KEY (rule_id) REFERENCES rules(rule_id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_flags_tx_current
  ON transaction_flags(transaction_id, is_current);

CREATE INDEX IF NOT EXISTS idx_tx_flags_flag_current
  ON transaction_flags(flag, is_current);

CREATE INDEX IF NOT EXISTS idx_tx_flags_current
  ON transaction_flags(is_current);

-- Optional: prevent exact duplicates of the same current flag per transaction
-- (still allows history when is_current=0)
CREATE UNIQUE INDEX IF NOT EXISTS ux_tx_flags_unique_current
  ON transaction_flags(transaction_id, flag, is_current);

-- ============================================================
-- End of schema
-- ============================================================
