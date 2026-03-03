# Example Datasets

Synthetic weekly datasets for testing the WBSB pipeline. Each covers a specific scenario — clean baseline, edge cases, and deliberate anomalies.

Base date series: 12 consecutive Mondays from 2024-01-01 to 2024-03-18.

## Dataset Index

| Dataset | Valid | Description | Expected Validator Behavior | Expected Rules Behavior |
|---------|-------|-------------|----------------------------|------------------------|
| `dataset_01_clean_baseline.csv` | Yes | Healthy, steadily growing business across 12 weeks. All 17 columns, positive integer counts, no anomalies. | Single `info` AuditEvent; no coercion warnings. | No anomaly signals expected; business is growing healthily. |
| `dataset_02_missing_values.csv` | Yes (columns) | All 17 columns present. Rows 3, 7, and 11 have blank cells in `leads_paid`, `bookings_total`, and `gross_revenue` respectively. | `coerce_warning` AuditEvents for INT columns with NaN coercion (rows 3 and 7). Float column blank (row 11) coerced to NaN. | Affected-week metrics use NaN; downstream rules see missing data for those weeks. |
| `dataset_03_negative_values.csv` | Yes (columns) | All 17 columns present. W05 `refunds`=−200, W08 `ad_spend_other`=−50, W10 `gross_revenue`=−1500, W11 `leads_paid`=−3. | Validator passes — no negativity check in schema. | Negative values flow into metrics; may produce anomalous ROAS, CPL, and revenue signals. |
| `dataset_04_duplicate_weeks.csv` | Yes (columns) | 13 rows — W06 (2024-02-05) appears twice as an identical duplicate. | Validator passes; 13 rows reach the pipeline unchanged. | Pipeline sees duplicate row; metrics/rules process both. Duplicate may skew deltas. |
| `dataset_05_misaligned_dates.csv` | Yes (columns) | 12 rows with three non-7-day gaps: W03=2024-01-16 (8-day), W07=2024-02-14 (9-day), W10=2024-03-06 (9-day). | Validator passes — no date-gap check in schema. | Pipeline uses provided dates; no gap-detection signals. |
| `dataset_06_float_in_int_columns.csv` | Yes (columns) | 12 rows. Four INT cells have fractional values: W02 `leads_paid`=20.5, W05 `bookings_total`=47.5, W08 `appointments_completed`=46.7, W11 `new_clients_paid`=22.3. | `non_integer_value` AuditEvents for each affected cell (Task 7 feature). Values coerced to int. | Metrics computed from coerced integer values. |
| `dataset_07_extreme_ad_spend.csv` | Yes | 12 weeks where ad spend (Google 5000–10500, Meta 4000–9500) massively exceeds gross revenue (3000–4100). | Single `info` AuditEvent; no coercion warnings. | Very high CPL and extremely poor ROAS; efficiency anomaly signals expected to fire. |
| `dataset_08_zero_revenue_week.csv` | Yes | 12 rows. W06 (2024-02-05) has `gross_revenue`=0, `leads_paid`=0, `bookings_total`=0, `appointments_completed`=0, `new_clients_paid`=0, `new_clients_organic`=0. All other weeks normal. | Single `info` AuditEvent; no coercion warnings. | `absolute_lt` revenue rules fire for W06; `safe_div` handles division-by-zero. |
| `dataset_09_low_volume.csv` | Yes | Very low counts throughout: `leads_paid` 1–3, `bookings_total` 2–5, `gross_revenue` 400–600, `ad_spend_google` 200–310. | Single `info` AuditEvent; no coercion warnings. | Hybrid rules use absolute-change branch due to low volume. Some guardrails skip rules when prior-week revenue/lead counts fall below thresholds. |
| `dataset_10_missing_required_column.csv` | No | 16 columns — `refunds` column omitted. Otherwise valid-looking data for 12 rows. | `ValueError: Missing required columns: ['refunds']` raised immediately. | Pipeline never reaches rules evaluation. |

## Column Reference

All valid datasets contain these 17 columns:

```
week_start_date, ad_spend_google, ad_spend_meta, ad_spend_other,
impressions_total, clicks_total, leads_paid, leads_organic,
bookings_total, appointments_completed, appointments_cancelled,
new_clients_paid, new_clients_organic, returning_clients,
gross_revenue, refunds, variable_cost
```

**INT columns** (must be whole numbers): `impressions_total`, `clicks_total`, `leads_paid`, `leads_organic`, `bookings_total`, `appointments_completed`, `appointments_cancelled`, `new_clients_paid`, `new_clients_organic`, `returning_clients`.

**FLOAT columns**: `ad_spend_google`, `ad_spend_meta`, `ad_spend_other`, `gross_revenue`, `refunds`, `variable_cost`.
