
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

    # --- Sidebar Filters (Analytics specific) ---
    st.sidebar.markdown("---")
    st.sidebar.header("Analytics Filters")

    # Date Range
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()

    start_date, end_date = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Category Filter
    st.sidebar.subheader("Filter by Category")
    cat_tree = fetch_categories_tree()
    
    cat_map = {c['category']: c for c in cat_tree}
    all_main_cats = sorted(cat_map.keys())

    selected_main = st.sidebar.multiselect("Main Category", all_main_cats, default=all_main_cats)

    available_subs = []
    for m in selected_main:
        if m in cat_map:
            subs = [s['category'] for s in cat_map[m].get('subcategories', [])]
            available_subs.extend(subs)

    selected_subs = st.sidebar.multiselect("Subcategory", sorted(list(set(available_subs))), default=available_subs)

    # Apply Filters
    mask = (
        (df['date'].dt.date >= start_date) & 
        (df['date'].dt.date <= end_date)
    )

    if selected_main:
        mask &= df['category'].isin(selected_main)

    if selected_subs:
        mask &= (df['subcategory'].isin(selected_subs) | df['subcategory'].isna())

    df_filtered = df.loc[mask]

    # --- KPI Metrics ---
    # Calc totals
    total_spent = df_filtered[df_filtered['amount'] < 0]['amount'].sum()
    total_income = df_filtered[df_filtered['amount'] > 0]['amount'].sum()
    tx_count = len(df_filtered)

    # Display KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Spent", f"{total_spent:,.2f} PLN", delta_color="inverse")
    c2.metric("Total Income", f"{total_income:,.2f} PLN")
    c3.metric("Transactions", tx_count)

    st.markdown("---")

    # --- Charts ---
    c_chart1, c_chart2 = st.columns(2)
    
    with c_chart1:
        st.subheader("Expenses by Category")
        if not df_filtered.empty:
            spending = (
                df_filtered[df_filtered['amount'] < 0]
                .groupby('category')['amount']
                .sum()
                .abs()
                .reset_index()
                .sort_values('amount', ascending=False)
            )
            fig = px.bar(spending, x='category', y='amount', text_auto='.2s', color='category')
            st.plotly_chart(fig, use_container_width=True)

    with c_chart2:
        st.subheader("Income vs Expenses Over Time")
        if not df_filtered.empty:
            df_filtered['month'] = df_filtered['date'].dt.to_period("M").astype(str)
            cash_flow = df_filtered.groupby(['month']).agg(
                income=('amount', lambda x: x[x > 0].sum()),
                expense=('amount', lambda x: x[x < 0].sum())
            ).reset_index()
            
            fig2 = px.bar(
                cash_flow.melt(id_vars='month', value_vars=['income', 'expense']),
                x='month',
                y='value',
                color='variable',
                barmode='group'
            )
            st.plotly_chart(fig2, use_container_width=True)

    # --- Data Table ---
    st.subheader("Detailed Transactions")
    st.dataframe(
        df_filtered[['date', 'description', 'category', 'subcategory', 'amount', 'currency']]
        .sort_values('date', ascending=False),
        use_container_width=True,
        hide_index=True
    )


def view_management():
    st.title("🛠 Management")
    
    # Subsection Navigation in Sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("Management Tools")
    
    tool = st.sidebar.radio("Select Tool:", [
        "Upload CSV", 
        "Rules Editor", 
        "Categories",
        "Bulk Categorization"
    ])
    
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

    elif tool == "Bulk Categorization":
        st.header("Manual Categorization")
        st.markdown("Assign categories to transactions manually.")
        
        # 1. Fetch Categories & Prepare Options
        cat_tree = fetch_categories_tree()
        flat_categories = []
        for c in cat_tree:
            flat_categories.append(c['category'])
            for s in c.get('subcategories', []):
                flat_categories.append(f"{c['category']}: {s['category']}")
        flat_categories.sort()

        # 2. Fetch Transactions
        show_all = st.checkbox("Show all transactions (including categorized)", value=False)
        
        tx_data = fetch_transactions(limit=2000, _refresh_key=st.session_state.refresh_key)
        
        if tx_data:
            df_tx = pd.DataFrame(tx_data)
            
            # Helper to create display string
            def make_display(row):
                if not row['category']: 
                    return None
                if row['subcategory']:
                    return f"{row['category']}: {row['subcategory']}"
                return row['category']
                
            df_tx['category_display'] = df_tx.apply(make_display, axis=1)
            
            # Filter
            if not show_all:
                df_tx = df_tx[df_tx['category'].isna()]
                st.caption(f"Showing {len(df_tx)} uncategorized transactions.")
            else:
                st.caption(f"Showing {len(df_tx)} transactions.")

            if not df_tx.empty:
                # Select columns
                # Ensure date is string for display or datetime
                df_tx['date_str'] = df_tx['date'].astype(str)
                
                cols = ['transaction_id', 'date', 'merchant', 'description', 'amount', 'category_display']
                
                # Editor
                edited_df = st.data_editor(
                    df_tx[cols],
                    key="tx_editor",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "transaction_id": st.column_config.TextColumn(disabled=True),
                        "date": st.column_config.TextColumn(disabled=True),
                        "merchant": st.column_config.TextColumn("Merchant (Editable)", disabled=False), 
                        "description": st.column_config.TextColumn(disabled=True),
                        "amount": st.column_config.NumberColumn(disabled=True, format="%.2f"),
                        "category_display": st.column_config.SelectboxColumn(
                            "Category",
                            options=flat_categories,
                            required=False,
                            width="large"
                        )
                    }
                )
                
                if st.button("Save Categorization Changes"):
                    changes = 0
                    
                    # We iterate the edited dataframe.
                    # We need to compare specific fields for changes.
                    
                    for index, row in edited_df.iterrows():
                        tid = row['transaction_id']
                        # Find original in the currently loaded dataframe
                        # (Ideally we tracked changes via session state, but this is stateless 'brute check')
                        orig_rows = df_tx[df_tx['transaction_id'] == tid]
                        if orig_rows.empty: continue
                        
                        orig = orig_rows.iloc[0]
                        
                        new_cat_str = row['category_display']
                        old_cat_str = orig['category_display']
                        
                        new_merch = row['merchant']
                        old_merch = orig['merchant']
                        
                        # Compare (handling NaNs)
                        cat_changed = (new_cat_str != old_cat_str) and not (pd.isna(new_cat_str) and pd.isna(old_cat_str))
                        merch_changed = (new_merch != old_merch)
                        
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
                    
                    if changes > 0:
                        st.success(f"Updated {changes} transactions.")
                        refresh_data()
                        st.rerun()
                    else:
                        st.info("No changes detected.")
            else:
                st.info("No transactions match the filter.")


# --- Main Router ---
def main():
    # Sidebar Navigation
    st.sidebar.title("Expensior")
    section = st.sidebar.radio("Section", ["Analytics", "Management"])
    
    # Check Backend Status
    try:
        health = requests.get(f"{API_URL.replace('/api', '')}/").json()
        st.sidebar.success(f"Backend Connected")
    except:
        st.sidebar.error("Backend Disconnected")

    if section == "Analytics":
        view_analytics()
    elif section == "Management":
        view_management()

if __name__ == "__main__":
    main()
