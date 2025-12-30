import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Odoo Sales Dashboard",
    page_icon="📊",
    layout="wide"
)

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
@st.cache_resource
def get_engine():
    return create_engine(
        "postgresql+psycopg2://readonly_user:admin@localhost:5432/aus_live"
    )

engine = get_engine()

# --------------------------------------------------
# DATA LOADERS
# --------------------------------------------------
@st.cache_data(ttl=600)
def load_sales_data():
    query = """
    SELECT
        so.id AS order_id,
        so.name AS order_number,
        so.date_order::date AS order_date,
        rp.name AS customer,
        ru.login AS salesperson,
        sol.product_uom_qty,
        sol.price_total
    FROM sale_order_line sol
    JOIN sale_order so ON so.id = sol.order_id
    JOIN res_partner rp ON rp.id = so.partner_id
    LEFT JOIN res_users ru ON ru.id = so.user_id
    WHERE so.state IN ('sale', 'done')
    """
    return pd.read_sql(query, engine)


@st.cache_data(ttl=600)
def load_product_data():
    query = """
    SELECT
        pt.name->>'en_US' AS product,
        SUM(sol.product_uom_qty) AS quantity,
        SUM(sol.price_total) AS sales
    FROM sale_order_line sol
    JOIN product_product pp ON pp.id = sol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN sale_order so ON so.id = sol.order_id
    WHERE so.state IN ('sale', 'done')
    GROUP BY product
    ORDER BY sales DESC
    """
    return pd.read_sql(query, engine)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
df = load_sales_data()
df_products = load_product_data()

df["order_date"] = pd.to_datetime(df["order_date"])

# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.title("🔎 Filters")

start_date = st.sidebar.date_input(
    "Start Date", df.order_date.min().date()
)
end_date = st.sidebar.date_input(
    "End Date", df.order_date.max().date()
)

salesperson = st.sidebar.multiselect(
    "Salesperson",
    options=df["salesperson"].dropna().unique()
)

filtered_df = df[
    (df.order_date >= pd.to_datetime(start_date)) &
    (df.order_date <= pd.to_datetime(end_date))
]

if salesperson:
    filtered_df = filtered_df[
        filtered_df["salesperson"].isin(salesperson)
    ]

# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.title("📊 Odoo Sales Dashboard")
st.markdown("Real-time sales insights from Odoo database")

# --------------------------------------------------
# KPI METRICS
# --------------------------------------------------
total_sales = filtered_df["price_total"].sum()
total_orders = filtered_df["order_number"].nunique()
avg_order_value = total_sales / total_orders if total_orders else 0

col1, col2, col3 = st.columns(3)

col1.metric("💰 Total Sales", f"₹ {total_sales:,.2f}")
col2.metric("📦 Orders", total_orders)
col3.metric("📊 Avg Order Value", f"₹ {avg_order_value:,.2f}")

# --------------------------------------------------
# SALES TREND
# --------------------------------------------------
st.subheader("📈 Sales Trend")

daily_sales = (
    filtered_df
    .groupby("order_date")["price_total"]
    .sum()
    .reset_index()
)

fig = px.line(
    daily_sales,
    x="order_date",
    y="price_total",
    markers=True
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# TOP CUSTOMERS
# --------------------------------------------------
st.subheader("🏆 Top Customers")

top_customers = (
    filtered_df
    .groupby("customer")["price_total"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

fig = px.bar(
    top_customers,
    x="customer",
    y="price_total"
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# TOP PRODUCTS
# --------------------------------------------------
st.subheader("📦 Top Products")

fig = px.bar(
    df_products.head(10),
    x="product",
    y="sales"
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# SALESPERSON PERFORMANCE
# --------------------------------------------------
st.subheader("🧑‍💼 Salesperson Performance")

salesperson_perf = (
    filtered_df
    .groupby("salesperson")["price_total"]
    .sum()
    .reset_index()
    .sort_values(by="price_total", ascending=False)
)

fig = px.bar(
    salesperson_perf,
    x="salesperson",
    y="price_total"
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# DATA TABLE
# --------------------------------------------------
st.subheader("📄 Sales Details")

st.dataframe(
    filtered_df.sort_values("order_date", ascending=False),
    use_container_width=True
)

# --------------------------------------------------
# EXPORT
# --------------------------------------------------
st.download_button(
    "⬇️ Export to CSV",
    filtered_df.to_csv(index=False),
    file_name="sales_report.csv",
    mime="text/csv"
)

