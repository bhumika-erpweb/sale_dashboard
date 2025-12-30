import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from sklearn.linear_model import LinearRegression
import numpy as np
import io

# ------------------------------
# CONFIG
# ------------------------------
st.set_page_config(page_title="Odoo Sales Dashboard", page_icon="📊", layout="wide")

# ------------------------------
# DATABASE CONNECTION
# ------------------------------
@st.cache_resource
def get_engine():
    password = quote_plus("admin")  # URL encode special chars
    return create_engine(f"postgresql+psycopg2://readonly_user:{password}@127.0.0.1:5432/aus_live")

engine = get_engine()

# ------------------------------
# LOAD DATA
# ------------------------------
@st.cache_data(ttl=600)
def load_sales_data():
    query = """
    SELECT
        so.id AS order_id,
        so.name AS order_number,
        so.date_order::date AS order_date,
        so.state,
        rp.name AS customer,
        ru.login AS salesperson,
        sol.product_uom_qty,
        sol.price_total,
        pt.name->>'en_US' AS product,
        c.name AS category
    FROM sale_order_line sol
    JOIN sale_order so ON so.id = sol.order_id
    JOIN res_partner rp ON rp.id = so.partner_id
    LEFT JOIN res_users ru ON ru.id = so.user_id
    JOIN product_product pp ON pp.id = sol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    LEFT JOIN product_category c ON c.id = pt.categ_id
    WHERE so.state IN ('sale', 'done','draft','sent','cancel')
    """
    return pd.read_sql(query, engine)

df = load_sales_data()
df["order_date"] = pd.to_datetime(df["order_date"])

# ------------------------------
# SIDEBAR FILTERS
# ------------------------------
st.sidebar.title("🔎 Filters")
min_date = df["order_date"].min().date()
max_date = df["order_date"].max().date()

start_date = st.sidebar.date_input("Start Date", min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("End Date", max_date, min_value=min_date, max_value=max_date)

filtered_df = df[(df["order_date"] >= pd.to_datetime(start_date)) & (df["order_date"] <= pd.to_datetime(end_date))]

salesperson_options = filtered_df["salesperson"].dropna().unique()
salesperson_selected = st.sidebar.multiselect("Salesperson", salesperson_options)
if salesperson_selected:
    filtered_df = filtered_df[filtered_df["salesperson"].isin(salesperson_selected)]

customer_options = filtered_df["customer"].unique()
customer_selected = st.sidebar.multiselect("Customer", customer_options)
if customer_selected:
    filtered_df = filtered_df[filtered_df["customer"].isin(customer_selected)]

category_options = filtered_df["category"].dropna().unique()
category_selected = st.sidebar.multiselect("Product Category", category_options)
if category_selected:
    filtered_df = filtered_df[filtered_df["category"].isin(category_selected)]

# ------------------------------
# HEADER
# ------------------------------
st.title("📊 Odoo Sales Dashboard")
st.markdown("Interactive sales analytics from Odoo database")

# ------------------------------
# KPI METRICS
# ------------------------------
total_sales = filtered_df["price_total"].sum()
total_orders = filtered_df["order_number"].nunique()
avg_order_value = total_sales / total_orders if total_orders else 0
total_customers = filtered_df["customer"].nunique()
new_customers = (filtered_df.groupby("customer")["order_date"].min() >= pd.to_datetime(start_date)).sum()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Total Sales", f"₹ {total_sales:,.2f}")
col2.metric("📦 Orders", total_orders)
col3.metric("📊 Avg Order Value", f"₹ {avg_order_value:,.2f}")
col4.metric("🧑‍💼 Customers", total_customers)
col5.metric("🆕 New Customers", new_customers)

# ------------------------------
# SALES TREND
# ------------------------------
st.subheader("📈 Sales Trend Over Time")
daily_sales = filtered_df.groupby("order_date")["price_total"].sum().reset_index()
daily_sales["rolling_7"] = daily_sales["price_total"].rolling(7).mean()

fig_sales_trend = px.line(
    daily_sales,
    x="order_date",
    y=["price_total", "rolling_7"],
    labels={"value":"Sales", "order_date":"Date", "variable":"Metric"},
    title="Daily Sales with 7-day Rolling Average",
    markers=True
)
st.plotly_chart(fig_sales_trend, use_container_width=True)

# ------------------------------
# TOP CUSTOMERS
# ------------------------------
st.subheader("🏆 Top Customers")
top_customers = filtered_df.groupby("customer")["price_total"].sum().sort_values(ascending=False).head(10).reset_index()
fig_top_customers = px.bar(top_customers, x="customer", y="price_total", title="Top 10 Customers")
st.plotly_chart(fig_top_customers, use_container_width=True)

# ------------------------------
# TOP PRODUCTS
# ------------------------------
st.subheader("📦 Top Products")
top_products = filtered_df.groupby("product")["price_total"].sum().sort_values(ascending=False).head(10).reset_index()
fig_top_products = px.bar(top_products, x="product", y="price_total", title="Top 10 Products")
st.plotly_chart(fig_top_products, use_container_width=True)

# ------------------------------
# SALES BY CATEGORY
# ------------------------------
st.subheader("🗂 Sales by Category")
category_sales = filtered_df.groupby("category")["price_total"].sum().reset_index()
fig_category = px.treemap(category_sales, path=["category"], values="price_total", title="Sales by Category")
st.plotly_chart(fig_category, use_container_width=True)

# ------------------------------
# SALESPERSON PERFORMANCE
# ------------------------------
st.subheader("🧑‍💼 Salesperson Performance")
salesperson_perf = filtered_df.groupby("salesperson")["price_total"].sum().reset_index().sort_values("price_total", ascending=False)
fig_salesperson = px.bar(salesperson_perf, x="salesperson", y="price_total", title="Sales by Salesperson")
st.plotly_chart(fig_salesperson, use_container_width=True)

# ------------------------------
# SALES FUNNEL
# ------------------------------
st.subheader("🔄 Sales Funnel")
funnel_df = filtered_df.groupby("state")["order_id"].nunique().reset_index().rename(columns={"order_id": "count"})
stage_order = ["draft", "sent", "sale", "done", "cancel"]
funnel_df["state"] = pd.Categorical(funnel_df["state"], categories=stage_order, ordered=True)
funnel_df = funnel_df.sort_values("state")
fig_funnel = px.funnel(funnel_df, x="count", y="state", title="Sales Funnel by Stage")
st.plotly_chart(fig_funnel, use_container_width=True)

# ------------------------------
# MONTHLY / QUARTERLY SALES
# ------------------------------
st.subheader("📊 Monthly / Quarterly Sales Comparison")
monthly_sales = filtered_df.set_index("order_date").resample("M")["price_total"].sum()
quarterly_sales = filtered_df.set_index("order_date").resample("Q")["price_total"].sum()
compare_df = pd.DataFrame({"Monthly": monthly_sales, "Quarterly": quarterly_sales}).fillna(0)
fig_compare = px.line(compare_df, x=compare_df.index, y=["Monthly","Quarterly"], labels={"value":"Sales", "index":"Date"}, title="Monthly vs Quarterly Sales")
st.plotly_chart(fig_compare, use_container_width=True)

# ------------------------------
# SALES FORECASTING
# ------------------------------
st.subheader("📈 Sales Forecast (Next 30 Days)")
daily_sales_forecast = filtered_df.groupby("order_date")["price_total"].sum().reset_index()
daily_sales_forecast["day_number"] = (daily_sales_forecast["order_date"] - daily_sales_forecast["order_date"].min()).dt.days
X = daily_sales_forecast["day_number"].values.reshape(-1,1)
y = daily_sales_forecast["price_total"].values
model = LinearRegression()
model.fit(X, y)
future_days = np.arange(X[-1][0]+1, X[-1][0]+31).reshape(-1,1)
forecast = model.predict(future_days)
forecast_dates = pd.date_range(daily_sales_forecast["order_date"].max()+pd.Timedelta(days=1), periods=30)
forecast_df = pd.DataFrame({"date": forecast_dates, "forecast_sales": forecast})
fig_forecast = px.line(daily_sales_forecast, x="order_date", y="price_total", title="Sales Forecast (Next 30 Days)")
fig_forecast.add_scatter(x=forecast_df["date"], y=forecast_df["forecast_sales"], mode="lines", name="Forecast")
st.plotly_chart(fig_forecast, use_container_width=True)

# ------------------------------
# DATA TABLE
# ------------------------------
st.subheader("📄 Detailed Sales Data")
st.dataframe(filtered_df.sort_values("order_date", ascending=False), use_container_width=True)
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    filtered_df.to_excel(writer, index=False, sheet_name='Sales')

# Seek to the beginning of the stream
output.seek(0)

# Streamlit download button
st.download_button(
    label="⬇️ Export Excel",
    data=output,
    file_name="sales_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
# ------------------------------
# EXPORT OPTIONS
# ------------------------------
st.download_button("⬇️ Export CSV", filtered_df.to_csv(index=False), file_name="sales_report.csv", mime="text/csv")


