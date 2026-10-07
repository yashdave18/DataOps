"""Olist dashboard. Run: python -m streamlit run dashboards/app.py."""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import metrics
from src.analytics.reports import load_data
from src.utils.paths import resolve_processed_dir

st.set_page_config(page_title='Olist commerce', page_icon='📦', layout='wide')


@st.cache_data(show_spinner='Loading commerce data…')
def cached_data(directory, signature):
    return load_data(directory)


def number(value, money=False, percent=False):
    if pd.isna(value):
        return 'Unknown'
    if money:
        return f'R$ {value:,.2f}'
    if percent:
        return f'{value:.1%}'
    return f'{value:,.0f}'


st.title('Olist commerce')
st.caption('Sales, customers, delivery, and reviews · Historical Brazilian marketplace data')
directory = resolve_processed_dir(os.environ.get('OLIST_PROCESSED_DIR', ROOT / 'data/processed'))
try:
    paths = [directory / name for name in [
        'analytical/orders.parquet', 'analytical/products.parquet',
        'olist_order_items_dataset.parquet', 'olist_sellers_dataset.parquet',
    ]]
    signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    data = cached_data(str(directory), signature)
except FileNotFoundError:
    st.error('The analytical data is not available yet. Ask the project owner to generate the curated datasets.')
    st.stop()

all_orders = data['orders']
if all_orders.empty:
    st.info('There are no orders in this dataset.')
    st.stop()

st.sidebar.header('Explore the data')
statuses = st.sidebar.multiselect('Order status', sorted(all_orders['order_status'].dropna().unique()), default=['delivered'])
first = all_orders['order_purchase_timestamp'].min().date()
last = all_orders['order_purchase_timestamp'].max().date()
dates = st.sidebar.date_input('Purchase dates', value=(first, last), min_value=first, max_value=last)
if len(dates) != 2:
    st.info('Select both a start and end date to explore this period.')
    st.stop()
orders = metrics.select_orders(all_orders, statuses=statuses, start=dates[0], end=dates[1])
page = st.sidebar.radio('View', ['Overview', 'Sales', 'Customers', 'Logistics', 'Reviews'])
st.sidebar.caption('Filters apply to every chart and download. Delivered orders are selected by default.')
if orders.empty:
    st.info('No orders match these filters. Try a wider date range or another order status.')
    st.stop()

summary = metrics.overview(orders).iloc[0]
st.caption(f'{dates[0]:%d %b %Y} – {dates[1]:%d %b %Y} · {len(orders):,} orders · BRL')

if page == 'Overview':
    columns = st.columns(4)
    for column, (label, value) in zip(columns, [
        ('Item revenue', number(summary['item_revenue'], money=True)),
        ('Orders', number(summary['order_count'])),
        ('Customers', number(summary['customer_count'])),
        ('Average order payment', number(summary['average_order_value'], money=True)),
    ]):
        column.metric(label, value)
    monthly = metrics.monthly_sales(orders)
    st.plotly_chart(px.line(monthly, x='month', y='item_revenue', markers=True, title='Item revenue by purchase month'), width='stretch')
    left, right = st.columns(2)
    left.metric('Late delivery rate', number(summary['late_delivery_rate'], percent=True))
    right.metric('Repeat customer rate', number(summary['repeat_customer_rate'], percent=True))
    st.caption(f"Late rate covers {summary['known_delivery_outcomes']:,.0f} known delivery outcomes. Repeat rate counts customers with more than one order in the selected period.")
    st.info('Item revenue excludes freight. Order payment includes recorded payment components. These gross amounts do not account for refunds or marketplace fees.')
elif page == 'Sales':
    monthly = metrics.monthly_sales(orders)
    st.plotly_chart(px.bar(monthly, x='month', y='order_count', title='Orders by purchase month'), width='stretch')
    categories = metrics.category_sales(orders, data['items'], data['products'])
    st.plotly_chart(px.bar(categories.head(15), x='item_revenue', y='category', orientation='h', title='Top categories by item revenue'), width='stretch')
    st.subheader('Product performance')
    st.dataframe(metrics.product_sales(orders, data['items'], data['products']).head(100), hide_index=True, width='stretch')
    st.download_button('Download category sales', categories.to_csv(index=False), 'category_sales.csv', 'text/csv')
elif page == 'Customers':
    activity = metrics.customer_activity(orders)
    st.plotly_chart(px.bar(activity, x='month', y=['new_customers', 'returning_customers'], title='New and returning customers'), width='stretch')
    st.caption('First purchase and repeat activity are measured within the selected status and date range; they are not lifetime acquisition dates.')
    cohorts = metrics.customer_cohorts(orders)
    if not cohorts.empty:
        matrix = cohorts.pivot(index='cohort_month', columns='month_offset', values='retention_rate')
        st.plotly_chart(px.imshow(matrix, aspect='auto', color_continuous_scale='Blues', zmin=0, zmax=1,
            labels={'x': 'Months since first observed purchase', 'y': 'Cohort', 'color': 'Retention'}, title='Monthly customer retention'), width='stretch')
    rfm = metrics.customer_rfm(orders)
    st.plotly_chart(px.histogram(rfm, x='frequency', title='Orders per customer'), width='stretch')
    st.subheader('Customer geography')
    st.dataframe(metrics.geography_performance(orders), hide_index=True, width='stretch')
    st.download_button('Download customer RFM', rfm.to_csv(index=False), 'customer_rfm.csv', 'text/csv')
elif page == 'Logistics':
    st.plotly_chart(px.histogram(orders, x='delivery_duration_days', nbins=60, title='Purchase to customer delivery (days)'), width='stretch')
    st.caption('Missing delivery dates are excluded from duration and late-rate calculations. Negative recorded durations remain visible.')
    st.subheader('Delivery by customer state')
    st.dataframe(metrics.geography_performance(orders), hide_index=True, width='stretch')
    sellers = metrics.seller_performance(orders, data['items'], data['sellers'])
    st.subheader('Seller performance')
    st.caption('Delivery and review metrics count each seller/order once, even when the order contains several units.')
    st.dataframe(sellers, hide_index=True, width='stretch')
    st.download_button('Download seller performance', sellers.to_csv(index=False), 'seller_performance.csv', 'text/csv')
else:
    scores = orders['review_score'].dropna().value_counts().sort_index().rename_axis('score').reset_index(name='orders')
    st.plotly_chart(px.bar(scores, x='score', y='orders', title='Review score distribution'), width='stretch')
    outcomes = metrics.review_delivery(orders)
    st.plotly_chart(px.bar(outcomes, x='delivery_outcome', y='average_review_score', title='Review score by delivery outcome'), width='stretch')
    st.dataframe(outcomes, hide_index=True, width='stretch')
    st.caption('Missing reviews are excluded from averages. Delivery comparisons show association, not causation. Product and category scores reflect whole-order reviews.')

st.download_button('Download selected order metrics', orders.to_csv(index=False), 'selected_orders.csv', 'text/csv')
