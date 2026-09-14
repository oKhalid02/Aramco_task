| Configuration | Evidence for the fix | H1 false alarms | H1 missed | H1 category errors | H1 totals wrong | H2–H5 invoices that change | …of which flag flips |
|---|---|---|---|---|---|---|---|
| Final pipeline |  | 0 | 0 | 0 | 4 | 0 | 0 |
| without: A wrong-unit line still counts as delivered (bundles, history) | H1 labels | 0 | 0 | 1 | 5 | 11 | 5 |
| without: A date past the term end is reported as out of window only | H1 labels | 0 | 0 | 2 | 4 | 9 | 0 |
| without: Loose match whose unit and price fit nothing -> unknown service | H1 labels | 0 | 0 | 2 | 4 | 0 | 0 |
| without: Several services fit a description -> tie (not fewest dropped words) | LLM second opinion | 0 | 0 | 0 | 4 | 0 | 0 |
| without: Wrong-unit lines count toward volume-discount utilisation | H3/H5 data majority | 0 | 0 | 0 | 4 | 5 | 5 |
| First Phase 3 run (all five off) |  | 0 | 0 | 5 | 5 | 20 | 5 |
