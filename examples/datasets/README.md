# Sample Datasets — Weekly Business Signal Brief

Ten synthetic datasets for testing validation, metric calculation, and rule-firing across diverse business types and data quality conditions. Each CSV contains the 17 required input columns (no derived columns).

**12 consecutive weeks** per dataset, starting `2024-10-07`.

---

## Business Archetypes

| ID | Description | bookings/wk | rev/appt | gross_revenue/wk | ad_spend/wk | Ad mix |
|----|-------------|------------|---------|-----------------|------------|--------|
| A | High-ticket (naturopath/dentist) | 8–22 | $650–1000 | $6k–18k | $400–900 | Google-heavy |
| B | Medium-ticket (clinic/physio) | 35–68 | $145–250 | $5k–14k | $1000–2500 | Google+Meta |
| C | Low-ticket (nails/barber/spa) | 85–155 | $38–65 | $3.5k–8.5k | $200–700 | Meta-heavy |

---

## Dataset Index

| # | Filename | Archetype | Intentional Issue | Expected Pipeline Behaviour |
|---|----------|-----------|------------------|-----------------------------|
| 01 | `dataset_01_clean_baseline.csv` | B | None | Clean run; only `info` AuditEvent emitted |
| 02 | `dataset_02_missing_values.csv` | A | Week 4 `gross_revenue` empty; week 8 `leads_paid` empty | NaN propagated silently; affected metrics return `None`; no `coerce_warning` (empty is already NaN) |
| 03 | `dataset_03_negative_values.csv` | C | Week 3 `ad_spend_meta` = −330; week 7 `variable_cost` = −1430 | Values pass through as negative; metrics compute (negative gross_margin possible); no `coerce_warning` |
| 04 | `dataset_04_non_monday_dates.csv` | B | Week 1 = Wed 2024-10-09; week 6 = Thu 2024-11-14 | Loader normalises to midnight but does not enforce Monday alignment; off-day rows appear in output |
| 05 | `dataset_05_duplicate_week.csv` | A | Week 6 (`2024-11-11`) duplicated with slightly different values | Loader keeps both rows after sorting by date; 13 rows total in output; downstream comparison is ambiguous |
| 06 | `dataset_06_outlier_spike.csv` | B | Week 8: bookings 51→120, `gross_revenue` 9200→36800 (+300%, promo campaign) | Rule A2 fires (`net_revenue` >+25% WoW); Rule G1 may fire (bookings spike); `severity=warn` |
| 07 | `dataset_07_holiday_dip.csv` | C | Week 12 (2024-12-23, Christmas): bookings 125→38 (−70%), `gross_revenue` 6435→2252 (−65%) | Rule A1 fires (`net_revenue` <−15%); Rule F1 fires (bookings down >−20%) |
| 08 | `dataset_08_inconsistent_counts.csv` | A | Week 5: `appointments_completed` (25) > `bookings_total` (20) | No pipeline guard; `show_rate` > 1.0 silently passes through; data quality issue visible in metrics |
| 09 | `dataset_09_column_name_typo.csv` | C | Column `appointments_canceled` (one "l") instead of `appointments_cancelled` | Pipeline raises `ValueError: Missing required columns: ['appointments_cancelled']`; aborts |
| 10 | `dataset_10_mixed_number_formats.csv` | B | Weeks 3 & 7 `gross_revenue` = `"9.500,00"` (European comma decimal) | `pd.to_numeric(..., errors='coerce')` converts to NaN; `coerce_warning` AuditEvent fires for `gross_revenue` |

---

## Quick Verification Commands

```bash
# 01 — should complete with only info event
python -m wbsb.cli run examples/datasets/dataset_01_clean_baseline.csv

# 09 — should raise ValueError: Missing required columns
python -m wbsb.cli run examples/datasets/dataset_09_column_name_typo.csv

# 10 — should emit coerce_warning for gross_revenue
python -m wbsb.cli run examples/datasets/dataset_10_mixed_number_formats.csv

# 08 — check show_rate > 1.0 in week 5 metrics
python -m wbsb.cli run examples/datasets/dataset_08_inconsistent_counts.csv
```

---

## Column Reference

All datasets use these 17 raw input columns (derived columns such as `ad_spend_total`, `new_clients_total`, and `net_revenue` are computed by the pipeline):

```
week_start_date, ad_spend_google, ad_spend_meta, ad_spend_other,
impressions_total, clicks_total, leads_paid, leads_organic,
bookings_total, appointments_completed, appointments_cancelled,
new_clients_paid, new_clients_organic, returning_clients,
gross_revenue, refunds, variable_cost
```
