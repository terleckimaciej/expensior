import argparse
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

# -------------------------
# Helpers
# -------------------------

def sha256_12(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def make_batch_id(input_path: str, ts: datetime | None = None) -> str:
    ts = ts or datetime.now(timezone.utc)
    return f"{sha256_12(input_path)}-{ts.strftime('%Y%m%dT%H%M%SZ')}"


def find_column_with_prefix(row: pd.Series, prefix: str) -> str:
    row_str = row.astype(str)
    matches = row_str.str.startswith(prefix, na=False)
    if not matches.any():
        return ""
    return row_str[matches].iloc[0]


def short_hash(*values, length=4) -> str:
    base = "|".join(str(v) for v in values)
    h = hashlib.sha256(base.encode()).hexdigest()
    return h[:length]


# -------------------------
# Transform logic (mirrors notebook)
# -------------------------

transaction_type_map = {
    "Płatność kartą": "card_payment",
    "Płatnoć kartš": "card_payment",
    "Zakup w terminalu - kod mobilny": "terminal_payment_blik",
    "Autooszczędzanie": "auto_savings",
    "Płatność web - kod mobilny": "web_payment_blik",
    "Płatnoć web - kod mobilny": "web_payment_blik",
    "Przelew na telefon przychodz. zew.": "transfer_blik",
    "Przelew na telefon przychodz. wew.": "transfer_blik",
    "Przelew na konto": "transfer_to_account",
    "Przelew z rachunku": "transfer_from_account",
    "Opłata za użytkowanie karty": "card_fee",
    "Zwrot w terminalu": "refund",
    "Zwrot płatności kartą": "refund",
    "Zwrot płatnoci kartš": "refund",
    "Zlecenie stałe": "standing_order",
    "Wypłata z bankomatu": "atm_withdrawal",
    "Wypłata w bankomacie - kod mobilny": "atm_withdrawal",
    "Wypłata w bankomacie - czek": "atm_withdrawal",
    "Obciążenie": "pko_charge",
    "Obcišżenie": "pko_charge",
    "Uznanie": "pko_credit",
    "Naliczenie odsetek": "interest_accrued",
}


def normalize_transaction_type(value, mapping):
    if pd.isna(value):
        return "unknown"
    cleaned = str(value).strip()
    if cleaned in mapping:
        return mapping[cleaned]
    return cleaned


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df_std = pd.DataFrame(index=df.index)

    df_std["transaction_id"] = None
    df_std["date"] = df["Data waluty"]
    df_std["transaction_type"] = df["Typ transakcji"]
    df_std["amount"] = (
        df["Kwota"].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    )
    df_std["currency"] = df["Waluta"]
    df_std["description"] = None
    df_std["country"] = None
    df_std["city"] = None

    # Normalize transaction_type
    df_std["transaction_type"] = df["Typ transakcji"].apply(lambda x: normalize_transaction_type(x, transaction_type_map))

    # Card + terminal blik
    mask_card = df_std["transaction_type"].isin(["card_payment"])
    mask_blik = df_std["transaction_type"].isin(["terminal_payment_blik"])

    # transaction_id for card payments
    src_card = df.loc[mask_card].apply(lambda row: find_column_with_prefix(row, "Tytuł:"), axis=1)
    df_std.loc[mask_card, "transaction_id"] = (
        src_card.fillna("")
        .str.extract(r"Tytuł:\s*([\d\s]+)", expand=False)
        .fillna("")
        .str.replace(" ", "", regex=False)
        .str.strip()
    )

    # transaction_id for terminal blik
    src_blik = df.loc[mask_blik].apply(lambda row: find_column_with_prefix(row, "Numer referencyjny:"), axis=1)
    df_std.loc[mask_blik, "transaction_id"] = (
        src_blik.fillna("")
        .str.extract(r"Numer referencyjny:\s*([\d\s]+)", expand=False)
        .fillna("")
        .str.replace(" ", "", regex=False)
        .str.strip()
    )

    # Shared description/city/country extraction for both
    mask = mask_card | mask_blik
    df_std.loc[mask, "description"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Adres:\s*(.*?)\s*Miasto:", expand=False)
        .str.strip()
        .str.upper()
    )
    df_std.loc[mask, "city"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Miasto:\s*([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9\s]+?)\s*Kraj:", expand=False)
        .str.strip()
        .str.upper()
    )
    df_std.loc[mask, "country"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Kraj:\s*(.*)", expand=False)
        .str.strip()
        .str.upper()
    )

    # Web payment blik + refund
    mask = df_std["transaction_type"].isin(["web_payment_blik", "refund"])
    df_std.loc[mask, "transaction_id"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Numer referencyjny:"), axis=1)
        .fillna("")
        .str.extract(r"Numer referencyjny:\s*([\d\s]+)", expand=False)
        .fillna("")
        .str.replace(" ", "", regex=False)
        .str.strip()
    )
    df_std.loc[mask, "description"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Adres:\s*(.*)", expand=False)
        .str.strip()
        .str.upper()
    )

    # Transfers / standing orders
    mask = df_std["transaction_type"].isin([
        "transfer_blik",
        "standing_order",
        "transfer_to_account",
        "transfer_from_account",
    ])
    df_std.loc[mask, "description"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Tytuł:"), axis=1)
        .str.extract(r"Tytuł:\s*(.*?)(?:\s*OD:|$)", expand=False)
        .fillna("")
        .str.strip()
        .str.upper()
        .apply(lambda x: x if x == "PRZELEW NA TELEFON" else x.replace("PRZELEW NA TELEFON", "").strip())
    )
    account_numbers = df["Unnamed: 6"].astype(str).str.replace(" ", "", regex=False).str.strip()
    df_std.loc[mask, "transaction_id"] = df_std.loc[mask].apply(
        lambda row: account_numbers[row.name] + " " + short_hash(row["date"], row["amount"], row["description"], length=4),
        axis=1,
    )

    # ATM withdrawals
    mask = df_std["transaction_type"].isin(["atm_withdrawal"])
    source_text = df.loc[mask].apply(
        lambda row: (
            find_column_with_prefix(row, "Numer referencyjny:")
            if find_column_with_prefix(row, "Numer referencyjny:") != ""
            else find_column_with_prefix(row, "Tytuł:")
        ),
        axis=1,
    )
    df_std.loc[mask, "transaction_id"] = (
        source_text.fillna("").str.extract(r"(?:Numer referencyjny|Tytuł):\s*([\d\s]+)", expand=False).fillna("").str.replace(" ", "", regex=False).str.strip()
    )
    df_std.loc[mask, "description"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Adres:\s*(.*?)\s*Miasto:", expand=False)
        .str.strip()
        .str.upper()
    )
    df_std.loc[mask, "city"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Miasto:\s*([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9\s]+?)\s*Kraj:", expand=False)
        .str.strip()
        .str.upper()
    )
    df_std.loc[mask, "country"] = (
        df.loc[mask]
        .apply(lambda row: find_column_with_prefix(row, "Lokalizacja:"), axis=1)
        .str.extract(r"Kraj:\s*(.*)", expand=False)
        .str.strip()
        .str.upper()
    )

    # Auto-savings
    mask = df_std["transaction_type"].isin(["auto_savings"])
    df["Kwota_next"] = df["Kwota"].shift(-1)
    df_std.loc[mask, "transaction_id"] = df.loc[mask].apply(
        lambda row: short_hash(
            row["Data operacji"],
            row["Data waluty"],
            row["Typ transakcji"],
            row["Kwota"],
            row["Kwota_next"],
            length=6,
        ),
        axis=1,
    )
    df_std.loc[mask, "description"] = "auto_savings"

    # City fixes
    df_std['city'] = df_std['city'].replace({
        'MOSCISKA': 'WARSZAWA',
        'PIASTOW': 'WARSZAWA',
        'PLOCHOCIN': 'WARSZAWA',
        'STARE BABICE': 'WARSZAWA'
    })

    # -------------------------
    # FALLBACK: Handle missing/duplicate transaction_ids
    # -------------------------

    # 1. Fill empty/null transaction_ids with deterministic synthetic hash
    #    (no row index so the same logical transaction keeps the same ID across imports)
    missing_mask = df_std['transaction_id'].isna() | (df_std['transaction_id'] == '')
    if missing_mask.any():
        df_std.loc[missing_mask, 'transaction_id'] = df_std[missing_mask].apply(
            lambda row: 'synthetic-' + short_hash(
                row.get('date'),
                row.get('transaction_type'),
                row.get('amount'),
                row.get('currency'),
                row.get('description', ''),
                row.get('country', ''),
                row.get('city', ''),
                length=12
            ),
            axis=1
        )

    # 2. Handle duplicates within the current CSV deterministycznie (bez numeru wiersza)
    dup_mask = df_std['transaction_id'].duplicated(keep=False)
    if dup_mask.any():
        def dedup_row(row):
            base_id = row['transaction_id']
            suffix = short_hash(
                row.get('date'),
                row.get('transaction_type'),
                row.get('amount'),
                row.get('currency'),
                row.get('description', ''),
                row.get('country', ''),
                row.get('city', ''),
                base_id,
                length=8,
            )
            return f"{base_id}-dup-{suffix}"

        df_std.loc[dup_mask, 'transaction_id'] = df_std[dup_mask].apply(dedup_row, axis=1)

    return df_std


# -------------------------
# DB insert
# -------------------------

def insert_import_batch(conn: sqlite3.Connection, batch_id: str, source_file_name: str, row_count: int, status: str = 'ok') -> None:
    conn.execute(
        """
        INSERT INTO import_batches (import_batch_id, source_file_name, row_count, status)
        VALUES (?, ?, ?, ?)
        """,
        (batch_id, source_file_name, row_count, status),
    )


def insert_transactions(conn: sqlite3.Connection, df_std: pd.DataFrame, batch_id: str, on_conflict: str = 'ignore') -> dict:
    if on_conflict not in {'ignore', 'replace', 'abort'}:
        raise ValueError("on_conflict must be ignore|replace|abort")
    verb = {'ignore': 'OR IGNORE', 'replace': 'OR REPLACE', 'abort': ''}[on_conflict]

    # Ensure ISO date strings and required defaults
    def iso_or_none(x):
        try:
            return pd.to_datetime(x).date().isoformat() if pd.notna(x) else None
        except Exception:
            return None

    rows = [
        (
            r.get('transaction_id') or '',
            iso_or_none(r.get('date')),
            r.get('transaction_type') or 'unknown',
            float(r.get('amount')),
            (r.get('currency') or 'PLN'),
            (r.get('description') or ''),
            r.get('country'),
            r.get('city'),
            batch_id,
        )
        for _, r in df_std.iterrows()
    ]

    sql = f"""
        INSERT {verb} INTO transactions
        (transaction_id, date, transaction_type, amount, currency, description, country, city, import_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    cur = conn.executemany(sql, rows)
    return {'attempted': len(rows), 'changes': conn.total_changes}


# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract/Transform PKO CSV and load into SQLite DB")
    parser.add_argument('--input', required=True, help='Path to input CSV')
    parser.add_argument('--db', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'expensior.db'))
    parser.add_argument('--on-conflict', choices=['ignore', 'replace', 'abort'], default='ignore')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    # Load CSV
    df = pd.read_csv(args.input, encoding='latin2')
    df_std = transform(df)

    # Summary of ID types for visibility
    synthetic_count = df_std['transaction_id'].str.startswith('synthetic-').sum()
    dup_count = df_std['transaction_id'].str.contains('-dup-').sum()
    natural_count = len(df_std) - synthetic_count - dup_count

    batch_id = make_batch_id(args.input)
    source_file = os.path.basename(args.input)

    if args.dry_run:
        print(f"[DRY] rows={len(df_std)}, batch_id={batch_id}, file={source_file}")
        print(f"Natural IDs: {natural_count} | Synthetic: {synthetic_count} | Duplicates-in-file: {dup_count}")
        print(df_std.head(5))
        return

    conn = sqlite3.connect(args.db)
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN')

        # Guard: batch exists
        if conn.execute("SELECT 1 FROM import_batches WHERE import_batch_id=?", (batch_id,)).fetchone():
            raise RuntimeError(f"import_batch_id already exists: {batch_id}")

        insert_import_batch(conn, batch_id, source_file, len(df_std), status='ok')
        stats = insert_transactions(conn, df_std, batch_id, on_conflict=args.on_conflict)
        conn.commit()
        print(f"Batch {batch_id} inserted. {stats}")
        print(f"Natural IDs: {natural_count} | Synthetic: {synthetic_count} | Duplicates-in-file: {dup_count}")
    except Exception as e:
        conn.rollback()
        try:
            conn.execute("UPDATE import_batches SET status='failed' WHERE import_batch_id=?", (batch_id,))
            conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
