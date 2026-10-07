"""Compare Spark joins, aggregation, filtering and windows with Pandas."""

import argparse
from pathlib import Path
import time

import pandas as pd

from src.utils.paths import resolve_processed_dir
from src.utils.parquet import write_verified_parquet

ROOT = Path(__file__).resolve().parents[1]


def order_features(orders, items, payments, customers):
    """ONE ROW = ONE ORDER; child aggregates precede joins, as in Pandas."""
    from pyspark.sql import functions as F, Window
    for frame, keys in [(orders, ['order_id']), (customers, ['customer_id']),
                        (items, ['order_id', 'order_item_id']), (payments, ['order_id', 'payment_sequential'])]:
        if frame.groupBy(*keys).count().filter(F.col('count') > 1).limit(1).count():
            raise ValueError(f'Duplicate Spark source keys: {keys}')
        condition = F.col(keys[0]).isNull()
        for key in keys[1:]:
            condition = condition | F.col(key).isNull()
        if frame.filter(condition).limit(1).count():
            raise ValueError(f'Null Spark source keys: {keys}')
    for child, parent, key in [(items, orders, 'order_id'), (payments, orders, 'order_id'),
                               (orders, customers, 'customer_id')]:
        if child.join(parent.select(key), key, 'left_anti').limit(1).count():
            raise ValueError(f'Unmatched Spark relationship: {key}')
    item_totals = items.groupBy('order_id').agg(
        F.sum('price').alias('total_item_value'), F.sum('freight_value').alias('total_freight'),
        F.count('*').alias('item_count'),
    )
    payment_totals = payments.groupBy('order_id').agg(
        F.sum('payment_value').alias('total_payment'), F.count('*').alias('payment_count'),
    )
    result = orders.select('order_id', 'customer_id', 'order_status', 'order_purchase_timestamp').join(
        customers.select('customer_id', 'customer_unique_id'), 'customer_id', 'left',
    ).join(item_totals, 'order_id', 'left').join(payment_totals, 'order_id', 'left')
    result = result.fillna(0, subset=['item_count', 'payment_count'])
    window = Window.partitionBy('customer_unique_id').orderBy('order_purchase_timestamp', 'order_id')
    return result.withColumn('customer_order_number', F.row_number().over(window)).withColumn(
        'customer_running_payment', F.sum('total_payment').over(window.rowsBetween(Window.unboundedPreceding, Window.currentRow)),
    )


def delivered_monthly(orders):
    """ONE ROW = ONE PURCHASE MONTH among delivered orders."""
    from pyspark.sql import functions as F, Window
    grouped = orders.filter(F.col('order_status') == 'delivered').groupBy(
        F.date_trunc('month', 'order_purchase_timestamp').alias('month')
    ).agg(F.count('*').alias('order_count'), F.sum('total_item_value').alias('item_revenue'),
          F.sum('total_payment').alias('payments'))
    return grouped.withColumn('running_item_revenue', F.sum('item_revenue').over(
        Window.orderBy('month').rowsBetween(Window.unboundedPreceding, Window.currentRow)))


def run_comparison(processed_dir, output_dir, master='local[2]'):
    from pyspark.sql import SparkSession
    processed = resolve_processed_dir(processed_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    spark = SparkSession.builder.master(master).appName('olist-comparison').config(
        'spark.sql.session.timeZone', 'UTC'
    ).config('spark.sql.shuffle.partitions', '4').config('spark.ui.enabled', 'false').getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')
    try:
        started = time.perf_counter()
        frames = [spark.read.parquet((processed / f'olist_{name}_dataset.parquet').as_posix())
                  for name in ['orders', 'order_items', 'order_payments', 'customers']]
        orders = order_features(*frames).cache()
        actual = orders.toPandas()
        monthly = delivered_monthly(orders).toPandas()
        spark_seconds = time.perf_counter() - started
        from src.analytics.metrics import monthly_sales
        expected = pd.read_parquet(processed / 'analytical/orders.parquet')
        expected = expected.sort_values(['customer_unique_id', 'order_purchase_timestamp', 'order_id']).copy()
        grouped = expected.groupby('customer_unique_id', sort=False)
        expected['customer_order_number'] = grouped.cumcount() + 1
        expected['customer_running_payment'] = grouped['total_payment'].transform(lambda s: s.cumsum().ffill())
        columns = list(actual.columns)
        pd.testing.assert_frame_equal(
            actual.sort_values('order_id').reset_index(drop=True),
            expected[columns].sort_values('order_id').reset_index(drop=True),
            check_dtype=False, check_exact=False, rtol=0, atol=0.01,
        )
        expected_monthly = monthly_sales(expected[expected.order_status == 'delivered'])
        pd.testing.assert_frame_equal(
            monthly.sort_values('month').reset_index(drop=True),
            expected_monthly[list(monthly.columns)].sort_values('month').reset_index(drop=True),
            check_dtype=False, check_exact=False, rtol=0, atol=0.01,
        )
        # This small learning dataset fits on the driver. Distributed production
        # output would use DataFrame.write.parquet to shared/object storage.
        write_verified_parquet(actual, output / 'orders.parquet')
        write_verified_parquet(monthly, output / 'delivered_monthly.parquet')
        report = pd.DataFrame([
            {'check': 'order values and customer windows', 'rows': len(actual), 'passed': True},
            {'check': 'delivered monthly values and running totals', 'rows': len(monthly), 'passed': True},
        ])
        report.to_csv(output / 'reconciliation.csv', index=False)
        print(report.to_string(index=False))
        print(f'Spark read, contracts, joins, windows and collection: {spark_seconds:.2f}s (not a controlled benchmark)')
        return report
    finally:
        spark.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--processed-dir', type=Path, default=ROOT / 'data/processed')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/processed/spark')
    parser.add_argument('--master', default='local[2]')
    args = parser.parse_args()
    run_comparison(args.processed_dir, args.output_dir, args.master)
