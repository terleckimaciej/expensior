
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
def fetch_transactions(limit=2000):
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
    raw_data = fetch_transactions(limit=5000)
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
        st.markdown("Here you can edit categorization rules.")
        
        # Placeholder for Rules CRUD
        st.warning("Rules management UI coming soon.")
        
        # Maybe show current rules?
        # df_rules = ... fetch rules ...
        # st.data_editor(df_rules)

    elif tool == "Bulk Categorization":
        st.header("Bulk Edit Transactions")
        st.markdown("Filter and update multiple transactions at once.")
        st.info("Feature under construction.")


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
