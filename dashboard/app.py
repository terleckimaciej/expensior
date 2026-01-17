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

# --- API Interaction ---
@st.cache_data(ttl=60)  # Cache data for 60 seconds to avoid spamming the API manually on every interaction
def fetch_transactions(limit=1000):
    try:
        # We fetch a larger limit for dashboard purposes
        response = requests.get(f"{API_URL}/transactions", params={"limit": limit})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return []

# --- Main Layout ---
st.title("💸 Expensior Dashboard")

# Check if Backend is alive
try:
    health = requests.get(f"http://127.0.0.1:8000/").json()
    st.sidebar.success(f"Backend Connected: {health.get('Hello')}")
except:
    st.sidebar.error("Backend Disconnected! Is uvicorn running?")
    st.stop()

# --- Load Data ---
raw_data = fetch_transactions(limit=10000)
if not raw_data:
    st.info("No transactions found.")
    st.stop()

df = pd.DataFrame(raw_data)
# Convert date
df['date'] = pd.to_datetime(df['date'])

# --- Sidebar Filters ---
st.sidebar.header("Filters")

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

# 1. Load Categories Tree
cat_tree = []
try:
    cat_resp = requests.get(f"{API_URL}/categories")
    if cat_resp.status_code == 200:
        cat_tree = cat_resp.json()
except:
    pass

# Map category names to their dict for easy lookup
cat_map = {c['name']: c for c in cat_tree}
all_main_cats = sorted(cat_map.keys())

# 2. Main Category Selection
selected_main = st.sidebar.multiselect("Main Category", all_main_cats, default=all_main_cats)

# 3. Subcategory Selection (Dynamic)
available_subs = []
for m in selected_main:
    if m in cat_map:
        subs = [s['name'] for s in cat_map[m].get('subcategories', [])]
        available_subs.extend(subs)

# If no main category selected, show no subcategories? Or all? 
# Usually if parent not selected, children are irrelevant.
# But here we want to allow selecting specific subcategories if they belong to selected parents.
selected_subs = st.sidebar.multiselect("Subcategory", sorted(list(set(available_subs))), default=available_subs)

# Apply Filters
# We need to filter by 'category' (main) OR 'subcategory' columns in DF.
# Note: In DF, 'category' corresponds to our Main Category.
# 'subcategory' corresponds to our Subcategory.

mask = (
    (df['date'].dt.date >= start_date) & 
    (df['date'].dt.date <= end_date)
)

# Logic:
# If user selects specific main categories, we include rows where category is in that list.
# REFINEMENT: If user selects specific subcategories, we must also respect that.
# A transaction matches if:
#   Main Category is in selected_main 
#   AND (Subcategory is in selected_subs OR Subcategory is Empty/NaN)

# However, the simple approach often used is:
# Filter by Main Category first. Then if Subcategory filter is used, refine further.
# But 'selected_subs' defaults to ALL available subs for selected parents. So it works naturally.

if selected_main:
    mask &= df['category'].isin(selected_main)

if selected_subs:
    # We only filter by subcategory if it's not None
    # Transactions with NO subcategory should be kept if their Parent is selected?
    # Let's say: if a user unchecks a subcategory, they want to hide it.
    # What about transactions with NULL subcategory? Usually we keep them if parent is selected.
    
    # Complex logic: 
    # Keep if (subcategory IN selected_subs) OR (subcategory is NULL and Keep Nulls?)
    # For simplicity:
    mask &= (df['subcategory'].isin(selected_subs) | df['subcategory'].isna())

df_filtered = df.loc[mask]

# --- KPI Metrics ---
col1, col2, col3 = st.columns(3)
total_spent = df_filtered[df_filtered['amount'] < 0]['amount'].sum()
total_income = df_filtered[df_filtered['amount'] > 0]['amount'].sum()
tx_count = len(df_filtered)

col1.metric("Total Spent", f"{total_spent:,.2f} PLN")
col2.metric("Total Income", f"{total_income:,.2f} PLN")
col3.metric("Transactions", tx_count)

# --- Charts ---
st.subheader("Spending by Category")
if not df_filtered.empty:
    spending_by_cat = (
        df_filtered[df_filtered['amount'] < 0]
        .groupby('category')['amount']
        .sum()
        .abs()
        .reset_index()
        .sort_values('amount', ascending=False)
    )
    
    fig_bar = px.bar(
        spending_by_cat, 
        x='category', 
        y='amount', 
        title="Expenses by Category",
        text_auto='.2s'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Time Series
    st.subheader("Cash Flow Over Time")
    # Group by Month
    df_filtered['month'] = df_filtered['date'].dt.to_period("M").astype(str)
    cash_flow = df_filtered.groupby(['month']).agg(
        income=('amount', lambda x: x[x > 0].sum()),
        expense=('amount', lambda x: x[x < 0].sum())
    ).reset_index()
    
    fig_line = px.bar(
        cash_flow.melt(id_vars='month', value_vars=['income', 'expense']),
        x='month',
        y='value',
        color='variable',
        barmode='group',
        title="Monthly Income vs Expenses"
    )
    st.plotly_chart(fig_line, use_container_width=True)

# --- Data Table ---
st.subheader("Recent Transactions")
st.dataframe(
    df_filtered[['date', 'description', 'category', 'amount', 'currency']]
    .sort_values('date', ascending=False)
    .head(50),
    use_container_width=True
)
