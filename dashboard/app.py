
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- Config ---
API_URL = "http://127.0.0.1:8000/api"

st.set_page_config(page_title="Expensior Dashboard", layout="wide")

# --- Initialize session state ---
if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

def refresh_data():
    st.session_state.refresh_key += 1

# --- API Functions ---
@st.cache_data(ttl=60)
def fetch_transactions(limit=2000, _refresh_key=0):
    try:
        response = requests.get(f"{API_URL}/transactions", params={"limit": limit})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching transactions: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_categories_tree():
    try:
        response = requests.get(f"{API_URL}/categories")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching categories: {e}")
    return []

# --- Views ---

def view_analytics():
    st.title("📊 Analytics Dashboard")
    
    # --- Load Data ---
    raw_data = fetch_transactions(limit=5000, _refresh_key=st.session_state.refresh_key)
    if not raw_data:
        st.info("No transactions found.")
        return

    df = pd.DataFrame(raw_data)
    df['date'] = pd.to_datetime(df['date'])

    # --- Date Filter & Control Panel ---
    
    # Initialize date state if not present (default to max range)
    if "filter_date_range" not in st.session_state:
        st.session_state.filter_date_range = (df['date'].min().date(), df['date'].max().date())

    # --- Period Manipulation Logic ---
    def adjust_period(direction: int):
        # direction: -1 (prev), 1 (next)
        period_type = st.session_state.get("period_selector", "Month")
        
        # We must use the key of the widget to get the current truth, 
        # or fall back to our manually tracked state.
        # Ideally, we bind everything to 'filter_date_range' key.
        
        current_val = st.session_state.get("filter_date_range")
        if not current_val or not isinstance(current_val, tuple) or len(current_val) != 2:
             current_val = (df['date'].min().date(), df['date'].max().date())
             
        current_start, current_end = current_val
        
        new_start, new_end = current_start, current_end
        
        if period_type == "Month":
            # Move to start of next/prev month
            # Calculate logic based on current_start
            # 1. Go to first day of current month
            base = current_start.replace(day=1) 
            # 2. Add/Sub month
            # Simple way: using pandas offsets or pure python
            # Let's use simple logic: next month is month+1
            
            year, month = base.year, base.month
            
            if direction == 1:
                # Next month
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            else:
                # Prev month
                month -= 1
                if month < 1:
                    month = 12
                    year -= 1
            
            new_start = base.replace(year=year, month=month, day=1)
            # End of new month
            next_m = month + 1
            next_y = year
            if next_m > 12:
                next_m = 1
                next_y += 1
            # Last day is first day of next month minus 1 day
            new_end = (new_start.replace(year=next_y, month=next_m, day=1) - timedelta(days=1))

        elif period_type == "Year":
            new_start = current_start.replace(year=current_start.year + direction, month=1, day=1)
            new_end = new_start.replace(year=new_start.year, month=12, day=31)

        elif period_type == "Week":
            # Just Shift by 7 days
            shift = timedelta(weeks=direction)
            new_start = current_start + shift
            new_end = current_end + shift
            
        st.session_state.filter_date_range = (new_start, new_end)


    # Layout: [ < ] [ Selector ] [ > ]  __________ [ Date Range Picker ]
    #         col1, col2,      col3     col4       col5
    
    # Top Row Container
    with st.container():
        # Define columns: Narrow controls on left, spacer, Wide picker on right
        c_nav_prev, c_nav_sel, c_nav_next, c_spacer, c_picker = st.columns([1, 4, 1, 1, 8])
        
        with c_nav_prev:
            st.markdown("###") # Vertical alignment spacer
            if st.button("◀", key="btn_prev", help="Previous Period"):
                adjust_period(-1)
        
        with c_nav_sel:
            # Period Type Selector
            st.selectbox(
                "Period Granularity",
                options=["Month", "Week", "Year"],
                key="period_selector",
                label_visibility="collapsed"
            )

        with c_nav_next:
            st.markdown("###") # Vertical alignment spacer
            if st.button("▶", key="btn_next", help="Next Period"):
                adjust_period(1)

        with c_picker:
            # Main Date Picker (Source of Truth)
            # It reads/writes directly to session_state.filter_date_range
            
            date_selection = st.date_input(
                "Filter Date Range",
                value=st.session_state.filter_date_range,
                min_value=None,
                max_value=None,
                key="filter_date_range" 
            )

    # Extract dates for filtering
    # Handle the case where range isn't fully picked yet
    if isinstance(st.session_state.filter_date_range, tuple) and len(st.session_state.filter_date_range) == 2:
        start_date, end_date = st.session_state.filter_date_range
    else:
        # Fallback
        start_date, end_date = df['date'].min().date(), df['date'].max().date() 

    # Extract dates for filtering
    # Handle the case where range isn't fully picked yet
    if isinstance(st.session_state.filter_date_range, tuple) and len(st.session_state.filter_date_range) == 2:
        start_date, end_date = st.session_state.filter_date_range
    else:
        # Fallback
        start_date, end_date = df['date'].min().date(), df['date'].max().date()

    # Apply Filters
    mask = (
        (df['date'].dt.date >= start_date) & 
        (df['date'].dt.date <= end_date)
    )
    df_filtered = df.loc[mask]

    # --- Metrics Calculation ---
    
    # Normalize category names for comparison (just in case)
    # But based on DB inspection, they are lowercase 'income' and 'savings'
    
    # 1. Income
    income_mask = df_filtered['category'] == 'income'
    val_income = df_filtered.loc[income_mask, 'amount'].sum()
    
    # 2. Savings
    savings_mask = df_filtered['category'] == 'savings'
    # Savings are usually negative (outflow), so we invert sign for display "Amount Saved"
    val_savings = df_filtered.loc[savings_mask, 'amount'].sum() * -1
    
    # 3. Expenses (Everything else)
    # Logic: Sum of ALL transactions that are NOT income and NOT savings.
    expenses_mask = ~df_filtered['category'].isin(['income', 'savings'])
    val_expenses_net = df_filtered.loc[expenses_mask, 'amount'].sum()
    
    # 4. Balance (Income - Expenses)
    # Since val_expenses_net is typically negative (e.g. -2000), we add it: 5000 + (-2000) = 3000
    val_balance = val_income + val_expenses_net
    
    # 5. Count
    val_count = len(df_filtered)

    # --- Display Metrics ---
    st.markdown("### Key Metrics")
    m1, m2, m3, m4, m5 = st.columns(5)
    
    m1.metric("Income", f"{val_income:,.2f} PLN")
    # Display Expenses as positive magnitude for readability, but mathematically we used the negative value for balance
    m2.metric("Expenses", f"{abs(val_expenses_net):,.2f} PLN", delta_color="inverse") 
    m3.metric("Balance", f"{val_balance:,.2f} PLN")
    m4.metric("Savings", f"{val_savings:,.2f} PLN")
    m5.metric("Transactions", val_count)

    st.markdown("---")



def view_transactions_manager(mode: str = "all"):
    """
    Unified Transactions View.
    mode="all" -> Show all transactions (Analytics mode)
    mode="uncategorized" -> Show only uncategorized (Management mode), but adjustable via checkbox
    """
    st.title("📋 Transactions Manager")

    # --- 1. Fetch Categories for Dropdown ---
    cat_tree = fetch_categories_tree()
    flat_categories = []
    # Add an empty option to allow clearing? Or handle it via None.
    # Streamlit SelectboxColumn typically requires options.
    for c in cat_tree:
        flat_categories.append(c['category'])
        for s in c.get('subcategories', []):
            flat_categories.append(f"{c['category']}: {s['category']}")
    flat_categories.sort()

    # --- 1.5 Add Manual Transaction Form ---
    with st.expander("➕ Add New Transaction"):
        with st.form("manual_tx_form"):
            c_date, c_amount, c_curr = st.columns([1, 1, 1])
            f_date = c_date.date_input("Date", value=datetime.today())
            f_amount = c_amount.number_input("Amount (Negative for expense)", step=0.01, format="%.2f")
            f_curr = c_curr.selectbox("Currency", ["PLN", "EUR", "USD"], index=0)
            
            c_type, c_desc, c_merch = st.columns([1, 1.5, 1.5])
            f_type = c_type.selectbox("Transaction Type", [
                "card_payment", "cash", "transfer", "blik", "standing_order"
            ])
            f_desc = c_desc.text_input("Description")
            f_merch = c_merch.text_input("Merchant (for classification)")
            
            f_cat = st.selectbox("Category (Optional)", [""] + flat_categories)
            
            if st.form_submit_button("Add Transaction"):
                # Parse Category
                p_cat, p_sub = None, None
                if f_cat:
                    parts = f_cat.split(": ")
                    p_cat = parts[0]
                    if len(parts) > 1: p_sub = parts[1]

                payload = {
                    "date": f_date.isoformat(),
                    "amount": f_amount,
                    "currency": f_curr,
                    "transaction_type": f_type,
                    "merchant": f_merch,
                    "description": f_desc,
                    "category": p_cat,
                    "subcategory": p_sub
                }
                
                try:
                    r = requests.post(f"{API_URL}/transactions/", json=payload)
                    if r.status_code == 200:
                        st.success("Transaction added!")
                        refresh_data()
                        st.rerun()
                    elif r.status_code == 409:
                        st.warning("Duplicate transaction detected (same date, type, amount, currency, description).")
                    else:
                        st.error(f"Error: {r.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

    # --- 2. Controls & Filters ---
    
    # Date Filter (Integrated from view_transactions)
    # Using a simpler date picker for this view as it's more operational than analytical
    # But we can reuse state if we wanted. For now, separate state to avoid conflicts.
    
    # Layout for controls
    c_date, c_check = st.columns([2, 2])
    
    with c_date:
        # Default range: Last 90 days? Or Max?
        # Let's fetch data first to know bounds... but fetch_transactions fetches latest anyway.
        # We'll just fetch first.
        pass

    # Fetch Data
    # Ideally paginated API, but here we fetch 2000 or 5000
    tx_data = fetch_transactions(limit=5000, _refresh_key=st.session_state.refresh_key)
    
    if not tx_data:
        st.info("No transactions found.")
        return

    df_tx = pd.DataFrame(tx_data)
    df_tx['date'] = pd.to_datetime(df_tx['date'])

    # Determine Date Bounds
    min_date = df_tx['date'].min().date()
    max_date = df_tx['date'].max().date()
    
    with c_date:
         start_date, end_date = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="tx_mgr_date"
        )
    
    # Filter Date
    mask_date = (df_tx['date'].dt.date >= start_date) & (df_tx['date'].dt.date <= end_date)
    df_tx = df_tx.loc[mask_date].copy()

    # Mode Toggle
    with c_check:
        st.write("") # Spacing
        st.write("") 
        # Default value depends on mode passed
        default_show_all = (mode == "all")
        show_all = st.checkbox("Show Categorized Transactions", value=default_show_all)
    
    # Helper to create display string for category
    def make_display(row):
        if not row['category']: 
            return None
        if row['subcategory']:
            return f"{row['category']}: {row['subcategory']}"
        return row['category']
        
    df_tx['category_display'] = df_tx.apply(make_display, axis=1)

    # Filter by Categorization Status
    if not show_all:
        df_tx = df_tx[df_tx['category'].isna()]
        st.caption(f"Showing {len(df_tx)} uncategorized transactions.")
    else:
        st.caption(f"Showing {len(df_tx)} transactions.")

    if df_tx.empty:
        st.info("No transactions match the criteria.")
        return

    # --- 3. Editable Data Table ---
    # Prepare columns
    # We want: ID (hidden?), Date, Merchant, Desc, Amount, Category(Dropdown)
    
    # Ensure ID is string
    df_tx['transaction_id'] = df_tx['transaction_id'].astype(str)
    
    cols_to_show = ['transaction_id', 'date', 'merchant', 'description', 'amount', 'currency', 'category_display']
    
    # Editor Configuration
    edited_df = st.data_editor(
        df_tx[cols_to_show],
        key="tx_manager_editor",
        use_container_width=True,
        hide_index=True,
        num_rows="fixed", # No adding new rows
        column_config={
            "transaction_id": st.column_config.TextColumn(disabled=True),
            "date": st.column_config.DatetimeColumn(disabled=True, format="D MMM YYYY"),
            "merchant": st.column_config.TextColumn("Merchant", disabled=False), 
            "description": st.column_config.TextColumn("Description", disabled=True),
            "amount": st.column_config.NumberColumn("Amount", disabled=True, format="%.2f"),
            "currency": st.column_config.TextColumn("Curr", disabled=True),
            "category_display": st.column_config.SelectboxColumn(
                "Category",
                options=flat_categories,
                required=False,
                width="large"
            )
        }
    )

    # --- 4. Save Logic ---
    if st.button("Save Changes", type="primary"):
        changes = 0
        progress_bar = st.progress(0)
        
        # We iterate to find diffs.
        # edited_df has the current state of UI.
        # df_tx has the state before editing (filtered).
        
        # Optimization: iterate on edited_df, check against df_tx by ID
        # Converting to dict for faster lookup
        original_map = df_tx.set_index('transaction_id')[['category_display', 'merchant']].to_dict('index')
        
        total_rows = len(edited_df)
        processed = 0
        
        for index, row in edited_df.iterrows():
            tid = row['transaction_id']
            if tid not in original_map:
                continue # Should not happen unless row ID changed?
                
            orig = original_map[tid]
            
            new_cat_str = row['category_display']
            old_cat_str = orig['category_display']
            
            new_merch = row['merchant']
            old_merch = orig['merchant']
            
            # Compare
            # Handle None/NaN
            cat_changed = (new_cat_str != old_cat_str)
            if pd.isna(new_cat_str) and pd.isna(old_cat_str): cat_changed = False
            
            merch_changed = (new_merch != old_merch)
            if pd.isna(new_merch) and pd.isna(old_merch): merch_changed = False
            
            if cat_changed or merch_changed:
                # Prepare payload
                cat, sub = None, None
                
                if pd.notna(new_cat_str) and new_cat_str:
                    parts = new_cat_str.split(": ")
                    cat = parts[0]
                    if len(parts) > 1: sub = parts[1]
                
                try:
                    requests.put(f"{API_URL}/transactions/{tid}/categorize", json={
                        "category": cat,
                        "subcategory": sub,
                        "merchant": new_merch
                    })
                    changes += 1
                except Exception as e:
                    st.error(f"Error updating {tid}: {e}")
            
            processed += 1
            if processed % 10 == 0:
                progress_bar.progress(min(processed / total_rows, 1.0))
        
        progress_bar.empty()
        
        if changes > 0:
            st.success(f"Successfully updated {changes} transactions.")
            refresh_data() # Update global refresh key
            st.rerun()
        else:
            st.info("No changes detected to save.")


def view_management(tool):
    st.title("🛠 Management")
    
    if tool == "Upload CSV":
        st.header("Import Transactions")
        st.info("Upload bank statement CSV files here.")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
        if uploaded_file is not None:
            st.write("Preview:")
            try:
                df_preview = pd.read_csv(uploaded_file)
                st.dataframe(df_preview.head())
                if st.button("Simulate Import (Not implemented in UI yet)"):
                    st.warning("Backend upload endpoint is not yet connected to UI.")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    elif tool == "Rules Editor":
        st.header("Manage Rules")
        
        # 1. Fetch Data
        rules_data = []
        try:
            r = requests.get(f"{API_URL}/rules")
            if r.status_code == 200:
                rules_data = r.json()
        except Exception as e:
            st.error(f"Failed to load rules: {e}")

        df_rules = pd.DataFrame(rules_data)
        
        # Prepare Dropdown Lists
        cat_tree = fetch_categories_tree()
        cat_map = {c['category']: c for c in cat_tree}
        
        all_categories = sorted(list(cat_map.keys()))
        # Flatten subcategories for the second dropdown
        all_subcategories = []
        for c in cat_tree:
            for s in c.get('subcategories', []):
                all_subcategories.append(s['category'])
        all_subcategories = sorted(list(set(all_subcategories)))

        # 2. Display Editor
        if not df_rules.empty:
            # We must designate ID column to track edits, but hide it usually
            # But st.data_editor needs 'id' if we want to handle updates specifically?
            # Ideally we rely on row index matching if we sort strictly.
            # Best way: keep 'id' visible or use it for matching.
            
            edited_df = st.data_editor(
                df_rules,
                num_rows="dynamic",
                key="rules_editor",
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "category": st.column_config.SelectboxColumn(
                        "Category",
                        help="Main Category",
                        width="medium",
                        options=all_categories,
                        required=True,
                    ),
                    "subcategory": st.column_config.SelectboxColumn(
                        "Subcategory",
                        help="Subcategory (Optional)",
                        width="medium",
                        options=all_subcategories,
                    ),
                    "match_type": st.column_config.SelectboxColumn(
                        "Match Type",
                        options=["contains", "regex"],
                        required=True,
                        default="contains"
                    ),
                    "source_column": st.column_config.SelectboxColumn(
                        "Source",
                        options=["description", "transaction_type"],
                        required=True,
                        default="description"
                    ),
                    "priority": st.column_config.NumberColumn(
                        "Priority",
                        min_value=1,
                        max_value=100,
                        default=10
                    ),
                    # Hide internal columns
                    "category_id": None
                },
                use_container_width=True,
                hide_index=True
            )
            
            # 3. Handle Changes
            if st.button("Save Changes"):
                # Detect Added Rows
                # data_editor state is complex.
                # A simpler approach for MVP: Iterate rows and upsert.
                # But 'edited_df' contains the FINAL state.
                # Which rows are new? Those with NaN/None/0 ID.
                
                progress_text = st.empty()
                updated_count = 0
                created_count = 0
                
                for index, row in edited_df.iterrows():
                    rule_payload = {
                        "pattern": row['pattern'],
                        "match_type": row['match_type'],
                        "source_column": row['source_column'],
                        "merchant": row['merchant'],
                        "category": row['category'],
                        "subcategory": row['subcategory'],
                        "conditions": row['conditions'],
                        "priority": int(row['priority']) if pd.notna(row['priority']) else 10
                    }
                    
                    # Logic: If 'id' is present and valid (>0), it's an update.
                    # If 'id' is missing/NaN (new row in Editor), it's a create.
                    
                    try:
                        is_existing = pd.notna(row.get('id')) and row.get('id') > 0
                        
                        if is_existing:
                            # Update
                            rid = int(row['id'])
                            # Compare with original to avoid spamming API? 
                            # For MVP, we can just PUT all, or try to diff.
                            # Let's PUT all for safety.
                            requests.put(f"{API_URL}/rules/{rid}", json=rule_payload)
                            updated_count += 1
                        else:
                            # Create - Check if pattern exists?
                            if rule_payload['pattern']:
                                requests.post(f"{API_URL}/rules/", json=rule_payload)
                                created_count += 1
                    except Exception as e:
                        st.error(f"Error saving rule: {row['pattern']} - {e}")
                
                st.success(f"Saved! Updated: {updated_count}, Created: {created_count}")
                st.rerun() # Refresh to get new IDs
        else:
            st.info("No rules found. Add one manually?")

    elif tool == "Categories":
        st.header("Category Management")
        
        # 1. VISUALIZATION (Sunburst)
        st.subheader("Structure Visualization")
        cat_tree = fetch_categories_tree()
        
        if cat_tree:
            # Flatten for Plotly Sunburst
            # Columns: [id, label, parent]
            sunburst_data = []
            
            # Root node
            sunburst_data.append({"id": "ROOT", "label": "Expenses", "parent": ""})
            
            for main_cat in cat_tree:
                mid = f"M_{main_cat['category_id']}"
                sunburst_data.append({
                    "id": mid, 
                    "label": main_cat['category'], 
                    "parent": "ROOT"
                })
                
                for sub in main_cat.get('subcategories', []):
                    sid = f"S_{sub['category_id']}"
                    sunburst_data.append({
                        "id": sid,
                        "label": sub['category'],
                        "parent": mid
                    })
            
            df_sun = pd.DataFrame(sunburst_data)
            fig = px.sunburst(
                df_sun,
                names='label',
                parents='parent',
                ids='id',
            )
            fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        
        # 2. MANAGEMENT INTERFACE
        st.subheader("Manage Categories")
        
        # Add New Main Category
        with st.form("new_main_cat"):
            c1, c2 = st.columns([3, 1])
            new_main_name = c1.text_input("New Main Category Name")
            if c2.form_submit_button("Add Group"):
                if new_main_name:
                    try:
                        requests.post(f"{API_URL}/categories/", json={"category": new_main_name})
                        st.success("Created!")
                        fetch_categories_tree.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Iterate Main Categories
        for main_cat in cat_tree:
            with st.expander(f"📁 {main_cat['category']} ({len(main_cat.get('subcategories', []))} items)"):
                
                # A. Rename Main Category
                with st.popover("Rename Group"):
                    new_name = st.text_input("New Name", value=main_cat['category'], key=f"ren_{main_cat['category_id']}")
                    if st.button("Update Name", key=f"btn_ren_{main_cat['category_id']}"):
                         requests.put(f"{API_URL}/categories/{main_cat['category_id']}", json={"category": new_name})
                         fetch_categories_tree.clear()
                         st.rerun()
                
                # B. Subcategories Editor
                subs = main_cat.get('subcategories', [])
                df_subs = pd.DataFrame(subs)
                
                if df_subs.empty:
                    # Initialize empty frame if needed for editor to show up specifically for adding
                    df_subs = pd.DataFrame(columns=["category_id", "category", "parent_id"])
                
                # Display Editor
                # We only allow editing the name.
                edited_subs = st.data_editor(
                    df_subs,
                    key=f"editor_{main_cat['category_id']}",
                    column_config={
                        "category_id": None,
                        "parent_id": None,
                        "category": st.column_config.TextColumn("Subcategory Name", required=True)
                    },
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True
                )
                
                # C. Save Changes
                if st.button("Save Changes", key=f"save_{main_cat['category_id']}"):
                    # Logic to detect diffs is hard with dynamic rows.
                    # Simplified: 
                    # 1. Existing rows (have ID) -> Update
                    # 2. New rows (no ID) -> Create
                    # 3. Deleted rows -> Delete (This is tricky with data_editor, as it returns the FINAL state)
                    # To handle deletions, we need to know what WAS there.
                    
                    current_ids = {row['category_id'] for row in subs}
                    final_ids = set()
                    
                    for index, row in edited_subs.iterrows():
                        # Handle New
                        if pd.isna(row.get('category_id')):
                             requests.post(f"{API_URL}/categories/", json={
                                 "category": row['category'],
                                 "parent_id": main_cat['category_id']
                             })
                        else:
                            # Handle Update
                            cid = int(row['category_id'])
                            final_ids.add(cid)
                            # Check if name changed to save API calls
                            orig = next((x for x in subs if x['category_id'] == cid), None)
                            if orig and orig['category'] != row['category']:
                                requests.put(f"{API_URL}/categories/{cid}", json={"category": row['category']})
                    
                    # Handle Deletions
                    # If ID was in current but not in final, it was deleted.
                    to_delete = current_ids - final_ids
                    for did in to_delete:
                        requests.delete(f"{API_URL}/categories/{did}")
                    
                    st.success("Saved!")
                    fetch_categories_tree.clear()
                    st.rerun()


    # elif tool == "Manual Categorization":
    #    # Deprecated: Merged into unified View Transactions Manager
    #    pass



# --- Main Router ---
def main():
    # Deprecated main wrapper, logic moved to __main__ block for sidebar simplicity
    pass

if __name__ == "__main__":
    st.sidebar.title("Expensior")
    
    # --- Navigation State ---
    if "current_view" not in st.session_state:
        st.session_state.current_view = "Dashboard"

    def update_view():
        # Callback to update view based on widget state
        # We need to determine which widget triggered the callback?
        # Actually, we can just sync the state.
        pass

    # --- Sidebar ---
    
    # 1. ANALYTICS
    st.sidebar.caption("ANALYTICS")
    
    analytics_opts = ["Dashboard", "Transactions"]
    try:
        idx_analytics = analytics_opts.index(st.session_state.current_view)
    except ValueError:
        idx_analytics = None
    
    def on_analytics_change():
        st.session_state.current_view = st.session_state.nav_analytics
        st.session_state.nav_management = None

    st.sidebar.radio(
        "Analytics Nav",
        options=analytics_opts,
        index=idx_analytics,
        key="nav_analytics",
        label_visibility="collapsed",
        on_change=on_analytics_change
    )

    st.sidebar.markdown("") # Spacer

    # 2. MANAGEMENT
    st.sidebar.caption("MANAGEMENT")
    
    management_opts = ["Upload CSV", "Categories", "Rules Editor", "Manual Categorization"]
    
    # Determine index for Management radio
    try:
        idx_mgmt = management_opts.index(st.session_state.current_view)
    except ValueError:
        idx_mgmt = None

    def on_mgmt_change():
        st.session_state.current_view = st.session_state.nav_management
        st.session_state.nav_analytics = None
        st.session_state.current_view = st.session_state.nav_management

    st.sidebar.radio(
        "Management Nav",
        options=management_opts,
        index=idx_mgmt,
        key="nav_management",
        label_visibility="collapsed",
        on_change=on_mgmt_change
    )
    
    # Check Backend Status (moved to bottom)
    st.sidebar.markdown("---")
    try:
        health = requests.get(f"{API_URL.replace('/api', '')}/").json()
        st.sidebar.caption(f"✅ Backend Connected")
    except:
        st.sidebar.error("Backend Disconnected")

    # --- Routing ---
    if st.session_state.current_view == "Dashboard":
        view_analytics()
    elif st.session_state.current_view == "Transactions":
        view_transactions_manager(mode="all")
    elif st.session_state.current_view == "Manual Categorization":
        view_transactions_manager(mode="uncategorized")
    else:
        view_management(st.session_state.current_view)

