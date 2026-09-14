| Planted error | Planted | Flagged | Right category | Total = original | Hospitals | Extra categories seen |
|---|---|---|---|---|---|---|
| `unit_price_mismatch` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `wrong_unit_plus_price` | 100 | 97 | 0 | 0 | H1, H2, H3, H4, H5 | unknown_service (22) |
| `line_total_arithmetic` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `invoice_total_mismatch` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `contract_number_mismatch` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `duplicate_invoice_id` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `malformed_service_date` | 100 | 100 | 100 | 90 | H1, H2, H3, H4, H5 | unit_price_mismatch (10) |
| `service_date_out_of_window` | 100 | 100 | 100 | 84 | H1, H2, H3, H4, H5 | unit_price_mismatch (9), volume_discount_omitted (7) |
| `service_date_after_invoice_date` | 100 | 100 | 100 | 93 | H1, H2, H3, H4, H5 | unit_price_mismatch (5), volume_discount_omitted (1), exclusion_window_violation (1) |
| `wrong_unit_basis` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `unknown_service` | 100 | 100 | 100 | 96 | H1, H2, H3, H4, H5 | unit_price_mismatch (4) |
| `unknown_service_lookalike` | 100 | 87 | 67 | 76 | H1, H2, H3, H4, H5 | unit_price_mismatch (23), exclusion_window_violation (2), cross_invoice_duplicate (1) |
| `daily_cap_exceeded` | 100 | 100 | 100 | 10 | H1, H2, H3, H4, H5 | — |
| `cross_invoice_duplicate` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `exclusion_window_violation` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `bundle_not_applied` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `premium_omitted` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `premium_incorrectly_applied` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `volume_discount_omitted` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `volume_discount_incorrectly_applied` | 100 | 100 | 100 | 100 | H1, H2, H3, H4, H5 | — |
| `amendment_rate_by_invoice_date` | 20 | 20 | 20 | 20 | H3 | — |
| `wrong_multiplier` | 20 | 20 | 20 | 20 | H5 | — |

| Hospital | Planted | Flagged | Right category |
|---|---|---|---|
| H1 | 400 | 396 (99.0%) | 376 (94.0%) |
| H2 | 400 | 400 (100.0%) | 376 (94.0%) |
| H3 | 420 | 417 (99.3%) | 390 (92.9%) |
| H4 | 400 | 395 (98.8%) | 371 (92.8%) |
| H5 | 420 | 416 (99.0%) | 394 (93.8%) |

**Missed plants (16), by the planted line's match after the error:** ambiguous: 16
**Missed plants that land in the review queue (confidence < 0.85):** 16/16

**Tier of each planted invoice after the run** (C = called clean, i.e. missed): C5: 16, F1: 700, F2: 1218, F3: 106
