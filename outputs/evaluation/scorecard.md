**Invoice level (H1, 913 invoices):** 58 erroneous found, 0 false alarms, 0 missed, 855 clean confirmed. Expected total exact: erroneous 54/58, clean 855/855.

| Category | Labelled | Found | False alarms | Missed | Precision | Recall | Expected total exact |
|---|---|---|---|---|---|---|---|
| `bundle_not_applied` | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 5/5 |
| `contract_number_mismatch` | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 5/5 |
| `cross_invoice_duplicate` | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 4/4 |
| `daily_cap_exceeded` | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 0/4 |
| `duplicate_invoice_id` | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 5/5 |
| `exclusion_window_violation` | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 4/4 |
| `invoice_total_mismatch` | 6 | 6 | 0 | 0 | 1.00 | 1.00 | 5/6 |
| `line_total_arithmetic` | 6 | 6 | 0 | 0 | 1.00 | 1.00 | 6/6 |
| `malformed_service_date` | 6 | 6 | 0 | 0 | 1.00 | 1.00 | 6/6 |
| `premium_incorrectly_applied` | 6 | 6 | 0 | 0 | 1.00 | 1.00 | 5/6 |
| `premium_omitted` | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 3/3 |
| `service_date_after_invoice_date` | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 5/5 |
| `service_date_out_of_window` | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 5/5 |
| `unit_price_mismatch` | 10 | 10 | 0 | 0 | 1.00 | 1.00 | 10/10 |
| `unknown_service` | 12 | 12 | 0 | 0 | 1.00 | 1.00 | 12/12 |
| `volume_discount_incorrectly_applied` | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 4/4 |
| `volume_discount_omitted` | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 4/4 |
| `wrong_unit_basis` | 11 | 11 | 0 | 0 | 1.00 | 1.00 | 11/11 |
