# Northwind Traders: Business Data Analysis

Business analysis of the Northwind sample database. It answers four
questions for a sales or general manager, each with a chart, a finding, and a
recommendation. The results are reproducible with Python code, which was
written with help from an AI coding assistant.

**Webpage:** [`docs/index.html`](docs/index.html), published with GitHub Pages
at <https://maria112-lang.github.io/Digital-Revolution-HW/>

## Questions and findings

| # | Question | Main finding |
|---|----------|--------------|
| 1 | Where is revenue growth coming from? | Jan–Apr 1998 revenue was up **120.7%** on Jan–Apr 1997. Beverages, Dairy and Seafood delivered **65%** of the growth. |
| 2 | How dependent are we on a few customers? | The top 20% of customers (18 of 89) bring in **60.1%** of revenue, and the top 3 bring in **25.2%**. Mère Paillarde (#9) has placed no orders in 1998. |
| 3 | Do discounts sell more, or just give away revenue? | A 1–5% discount sells as many units as deeper ones (**27.1** units per line either way). Discounts above 5% gave away **$58,484**. |
| 4 | Which customers are we at risk of losing? | **5** repeat customers are at risk and **4** are on a watch list, about **$77K** of 1997 revenue. |

The scripts for question 4 are named `q5_*` because it was question 5 in the
original list of candidate questions.

## Reproduce

Requires Python 3.12+ (tested on 3.13). The pinned numpy version does not
install on older Pythons.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python src/run_all.py
```

`run_all.py` does the following:

1. Downloads the 8 Northwind tables from the public Google Sheet into `data/`
   as CSV files. If the CSVs are already there, it uses them.
2. Builds `data/northwind.db` (SQLite) with cleaned types and an
   `order_lines` view.
3. Runs each question script. They write charts to `outputs/figures/` and
   tables to `outputs/tables/`.
4. Recomputes 15 key numbers independently with pandas on the raw CSVs and
   checks that they match the SQL results (all 15 match).
5. Saves everything to `outputs/results.json`, copies the charts to
   `docs/figures/`, and prints the findings.

### Running the scripts one at a time

Instead of `run_all.py`, you can run the scripts individually from the
project folder, in this order:

| Order | Command | Produces |
|---|---|---|
| 1 | `python src/load_data.py` | `data/*.csv` (8 tables, re-downloaded) |
| 2 | `python src/q1_growth.py` | `outputs/figures/q1_growth.png`, `outputs/tables/q1_monthly_revenue.csv`, `outputs/tables/q1_category_growth.csv` |
| 3 | `python src/q2_concentration.py` | `outputs/figures/q2_pareto.png`, `outputs/figures/q2_top10_trend.png`, `outputs/tables/q2_customer_revenue.csv`, `outputs/tables/q2_top10_trend.csv` |
| 4 | `python src/q3_discounts.py` | `outputs/figures/q3_discounts.png`, `outputs/tables/q3_discount_bands.csv` |
| 5 | `python src/q5_at_risk.py` | `outputs/figures/q5_at_risk.png`, `outputs/tables/q5_customer_recency.csv` |

The first question script also builds `data/northwind.db` if it doesn't
exist. Each script prints its key numbers. Only `run_all.py` runs the
verification, writes `outputs/results.json`, and copies the charts to
`docs/figures/` for the webpage.

### Where the data goes

You don't need to download anything by hand: the scripts fetch the data from
the public Google Sheet. To work offline, or with your own copy of
Northwind, put these 8 CSV files in `data/` before running:
`categories.csv`, `customers.csv`, `employees.csv`, `order_details.csv`,
`orders.csv`, `products.csv`, `shippers.csv`, `suppliers.csv`. The columns
must match the Google Sheet's. The repository already includes them, so a
fresh clone works offline. If you replace the CSVs, delete
`data/northwind.db` so it gets rebuilt.

## Project structure

```
data/                  Northwind tables as CSV (northwind.db is generated)
src/
  load_data.py         Download the Google Sheet tabs to data/
  db.py                Build the SQLite database; query and chart helpers
  q1_growth.py         Q1: revenue trend and growth by category
  q2_concentration.py  Q2: customer concentration and top-10 trend
  q3_discounts.py      Q3: discount level vs units sold, revenue given up
  q5_at_risk.py        Q4 (originally Q5): overdue repeat customers
  verify.py            Recompute the key numbers with pandas only
  run_all.py           Run everything and print the findings
outputs/
  figures/             Charts (PNG)
  tables/              Result tables (CSV)
  results.json         All key numbers
docs/
  index.html           The webpage (GitHub Pages root)
  figures/             Copies of the charts used by the page
```

## Definitions and assumptions

- **Net revenue** = `UnitPrice × Quantity × (1 − Discount)` per order line.
  It uses the price charged on that order, not the current list price, and
  excludes freight.
- **Growth** compares January–April 1998 with January–April 1997. May 1998
  is left out because the data ends on 6 May.
- **At risk:** a customer with 3 or more orders whose days since their last
  order are more than 2× their average gap between orders. **Watch:** 1.5–2×.
  "Today" is the last order date in the data, 6 May 1998.
- **Discounts vs volume** is a correlation. The same-product comparison rules
  out product mix but not the possibility that reps discount orders that
  were already large.

## Data quality notes

All primary keys are unique, every foreign key resolves, and there are no
zero or negative quantities or prices and no shipped-before-ordered dates.
Fixes applied:
- One freight value stored as `"1,007.64"` is converted to a number.
- Floating-point noise in discounts (e.g. 0.0500000007) is rounded to 2
  decimals.

The products tab has extra spreadsheet columns (`Cheap`, `NewPrice`, …)
that are not used. 21 orders placed after 8 April 1998 have not shipped
yet; they still count toward revenue.

## Code documentation

All Python code is in `src/` and documented with Google-style docstrings,
written using the course's `python-docstrings` skill (PEP 8 / PEP 257). Each
docstring has one line per parameter and a `Returns:` section.

## Tools

Python only: pandas, matplotlib, sqlite3 (standard library). An AI coding
assistant (Claude Code) helped with data processing, code, and charts.
