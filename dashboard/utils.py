
@st.cache_data(ttl=300)
def fetch_categories_tree():
    try:
        response = requests.get(f"{API_URL}/categories")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching categories: {e}")
        return []
