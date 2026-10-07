# Analytics findings: delivered-order population

These findings use the executed `notebooks/05_analytics.ipynb` and the CSVs
in `data/processed/reports/delivered/`. They describe the historical Olist
snapshot, not current market performance. All-status reports live one directory above.

- Delivered orders: **96,478**, from **93,358** unique customer identities.
- Gross recorded item value: **R$ 13,221,498.11**. Freight is separate; refunds and marketplace fees are not modeled.
- Average known order payment: **R$ 159.86**, across **96,477** orders with known payment totals.
- Late delivery rate: **6.77%**, using **96,470** orders with both actual and estimated delivery dates.
- Repeat customer rate: **3.00%** within the delivered-order population. This is not a lifetime repeat rate.
- Mean retained review score: **4.16**, across **95,832** scored orders.

## Leading categories by item value

| Category | Recorded item value (BRL) | Units |
| --- | ---: | ---: |
| health_beauty | 1,233,131.72 | 9,465 |
| watches_gifts | 1,166,176.98 | 5,859 |
| bed_bath_table | 1,023,434.76 | 10,953 |
| sports_leisure | 954,852.55 | 8,431 |
| computers_accessories | 888,724.61 | 7,644 |

## Delivery and reviews

| Outcome | Reviewed orders | Mean score |
| --- | ---: | ---: |
| late | 6,381 | 2.27 |
| on_time | 89,443 | 4.29 |
| unknown | 8 | 4.50 |

The review comparison is descriptive and does not establish causation. Ratings
describe whole orders and may reflect several products, sellers, and delivery
experiences. Missing reviews remain excluded rather than becoming zero.

## Interpretation limits

Monthly charts retain partial boundary months. Cohorts use first observed
purchase within the selected population; future months are absent, while
observed inactive months are zero. Customers generally have few observed
purchases, so retention patterns should be read with cohort sizes. RFM uses
the day after the final selected purchase, not the current date. Negative
recorded durations and existing quality flags remain in the data.
