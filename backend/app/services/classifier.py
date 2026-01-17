import json
import re
import sqlite3
import pandas as pd

# -------------------------
# Conditions Engine
# -------------------------

def apply_conditions(mask, dft, conditions):
    """
    Apply additional conditions to narrow down the mask.
    Returns modified mask based on JSON conditions.
    """
    if not conditions:
        return mask

    # --- amount ---
    if "min_amount" in conditions:
        mask &= dft["amount"] >= conditions["min_amount"]

    if "max_amount" in conditions:
        mask &= dft["amount"] <= conditions["max_amount"]

    if "amount_range" in conditions:
        lo, hi = conditions["amount_range"]
        mask &= dft["amount"].between(lo, hi)

    if "amount_sign" in conditions:
        if conditions["amount_sign"] == "negative":
            mask &= dft["amount"] < 0
        elif conditions["amount_sign"] == "positive":
            mask &= dft["amount"] > 0

    # --- date (datetime-safe) ---
    if "effective_from" in conditions:
        mask &= dft["date"] >= pd.to_datetime(conditions["effective_from"])

    if "effective_to" in conditions:
        mask &= dft["date"] <= pd.to_datetime(conditions["effective_to"])

    # --- simple IN conditions ---
    for col in ["transaction_type", "country", "city", "currency"]:
        if col in conditions and col in dft.columns:
            mask &= dft[col].isin(conditions[col])

    # --- text exclusions ---
    if "not_contains" in conditions:
        for val in conditions["not_contains"]:
            mask &= ~dft["description"].str.contains(val, case=False, na=False)

    # --- OR logic ---
    if "must_contain_any" in conditions:
        any_mask = pd.Series(False, index=dft.index)
        for val in conditions["must_contain_any"]:
            any_mask |= dft["description"].str.contains(val, case=False, na=False)
        mask &= any_mask

    # --- AND logic ---
    if "must_contain_all" in conditions:
        for val in conditions["must_contain_all"]:
            mask &= dft["description"].str.contains(val, case=False, na=False)

    return mask


# -------------------------
# Rules Engine
# -------------------------

def apply_rules(dft: pd.DataFrame, dfr: pd.DataFrame) -> pd.DataFrame:
    """
    Apply classification rules to transactions DataFrame.
    Rules are applied in priority order (highest first).
    Once a transaction is matched, it's not re-matched by lower priority rules.
    """
    # --- ensure output columns exist ---
    for col in ["merchant", "category", "subcategory", "rule_id"]:
        if col not in dft.columns:
            dft[col] = None

    # --- ensure datetime ---
    dft["date"] = pd.to_datetime(dft["date"], errors="coerce")

    # --- sort rules by priority ---
    dfr = dfr.sort_values("priority", ascending=False)

    # --- iterate rules ---
    for _, rule in dfr.iterrows():
        src_col = rule["source_column"]
        if src_col not in dft.columns:
            continue

        # --- base pattern match ---
        if rule["match_type"] == "contains":
            mask = dft[src_col].str.contains(
                re.escape(str(rule["pattern"])),
                case=False,
                na=False
            )
        elif rule["match_type"] == "regex":
            try:
                mask = dft[src_col].str.contains(
                    rule["pattern"],
                    case=False,
                    na=False,
                    regex=True
                )
            except re.error:
                continue
        else:
            continue

        # --- parse conditions safely ---
        conditions = None
        raw_conditions = rule.get("conditions")
        if isinstance(raw_conditions, str) and raw_conditions.strip():
            try:
                conditions = json.loads(raw_conditions)
            except json.JSONDecodeError:
                continue

        # --- apply conditions ---
        mask = apply_conditions(mask, dft, conditions)

        # --- apply only where not yet classified ---
        assign_mask = mask & dft["rule_id"].isna()
        if not assign_mask.any():
            continue

        dft.loc[assign_mask, "merchant"] = rule["merchant"]
        dft.loc[assign_mask, "category"] = rule["category"]
        dft.loc[assign_mask, "subcategory"] = rule["subcategory"]
        dft.loc[assign_mask, "rule_id"] = rule["id"]

    return dft


# -------------------------
# DB Operations
# -------------------------

def load_unclassified_transactions(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load transactions that don't have a current classification.
    """
    query = """
    SELECT 
        t.transaction_id,
        t.date,
        t.transaction_type,
        t.amount,
        t.currency,
        t.description,
        t.country,
        t.city
    FROM transactions t
    LEFT JOIN transaction_classifications tc 
        ON t.transaction_id = tc.transaction_id 
        AND tc.is_current = 1
    WHERE tc.classification_id IS NULL
    ORDER BY t.date DESC
    """
    return pd.read_sql_query(query, conn)


def load_rules(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load all active rules from database.
    """
    query = """
    SELECT 
        id,
        pattern,
        match_type,
        source_column,
        merchant,
        category,
        subcategory,
        conditions,
        priority
    FROM rules
    ORDER BY priority DESC
    """
    return pd.read_sql_query(query, conn)


def save_classifications(conn: sqlite3.Connection, df: pd.DataFrame) -> dict:
    """
    Save classifications to transaction_classifications table.
    Returns stats about what was saved.
    """
    classified = df[df["rule_id"].notna()].copy()
    
    if len(classified) == 0:
        return {"classified": 0, "unclassified": len(df)}
    
    # Filter out rows where category is None/null (required field in DB)
    classified = classified[classified["category"].notna()]
    
    if len(classified) == 0:
        return {"classified": 0, "unclassified": len(df)}
    
    rows = []
    for _, row in classified.iterrows():
        rows.append((
            row["transaction_id"],
            row["category"],
            row["subcategory"],
            row["merchant"],
            "method", # Just a placeholder since it was strict in original
            int(row["rule_id"]),
            1,  # is_current
        ))
    
    # Original script had 'method'='rule' hardcoded in loop, let's fix that
    # The previous code had: "rule",  # method
    # Let's rebuild rows properly
    rows = []
    for _, row in classified.iterrows():
         rows.append((
            row["transaction_id"],
            row["category"],
            row["subcategory"],
            row["merchant"],
            "rule",  # method
            int(row["rule_id"]),
            1,  # is_current
        ))

    sql = """
    INSERT INTO transaction_classifications 
    (transaction_id, category, subcategory, merchant, method, rule_id, is_current)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    conn.executemany(sql, rows)
    
    return {
        "classified": len(classified),
        "unclassified": len(df) - len(classified)
    }

def run_classification(conn: sqlite3.Connection, dry_run: bool = False):
    """
    Main entry point for classification service
    """
    df_transactions = load_unclassified_transactions(conn)
    
    if len(df_transactions) == 0:
        return {"status": "no_transactions"}
    
    df_rules = load_rules(conn)
    df_classified = apply_rules(df_transactions, df_rules)
    
    classified_count = df_classified["rule_id"].notna().sum()
    unclassified_count = df_classified["rule_id"].isna().sum()
    
    result = {
        "found": len(df_transactions),
        "classified": int(classified_count),
        "unclassified": int(unclassified_count),
    }

    if dry_run:
        result["dry_run_sample"] = df_classified[df_classified["rule_id"].notna()][
                ["transaction_id", "description", "category", "subcategory", "merchant", "rule_id"]
            ].head(10).to_dict(orient="records")
        return result
    
    if classified_count > 0:
        conn.execute('BEGIN')
        stats = save_classifications(conn, df_classified)
        conn.commit()
        result["saved"] = stats
    
    return result
