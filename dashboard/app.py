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
categories = sorted([str(x) for x in df['category'].unique() if x])
selected_categories = st.sidebar.multiselect("Categories", categories, default=categories)

# Apply Filters
mask = (
    (df['date'].dt.date >= start_date) & 
    (df['date'].dt.date <= end_date) &
    (df['category'].isin(selected_categories) | df['category'].isna()) 
    # Note: Handle None categories logic if needed, currently sidebar multiselect might filter none out
)
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
