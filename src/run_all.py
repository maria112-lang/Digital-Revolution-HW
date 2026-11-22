"""Run every question, verify the results, and print the findings.

Writes figures and tables to ``outputs/``, all results to
``outputs/results.json``, and copies the figures to ``docs/figures/``.
"""

import json
import shutil
import sys
from pathlib import Path

import q1_growth
import q2_concentration
import q3_discounts
import q4_at_risk
import verify
from db import FIG_DIR, ROOT, build_database

DOCS_FIG_DIR = ROOT / "docs" / "figures"


def publish_figures(src_dir=FIG_DIR, dest_dir=DOCS_FIG_DIR):
    """Copy chart images to the webpage's figure folder.

    Args:
        src_dir (pathlib.Path): Folder of generated ``.png`` charts.
        dest_dir (pathlib.Path): Webpage figure folder; created if
            missing. Same-named files are overwritten.

    Returns:
        list[pathlib.Path]: Paths of the copied images.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(p, dest_dir / p.name))
            for p in sorted(src_dir.glob("*.png"))]


def money(v):
    """Format a USD amount without cents.

    Args:
        v (float): Amount in USD.

    Returns:
        str: Amount such as ``$1,234``.
    """
    return f"${v:,.0f}"


def print_findings(r):
    """Print the main findings for each question.

    Args:
        r (dict): Results keyed ``q1``, ``q2``, ``q3``, and ``q4``.

    Returns:
        None. Writes to standard output.
    """
    q1, q2, q3, q4 = r["q1"], r["q2"], r["q3"], r["q4"]
    print("\n=== Q1. Where is growth coming from? ===")
    print(f"{q1['window']}: {money(q1['prior_revenue'])} -> "
          f"{money(q1['current_revenue'])} "
          f"(+{q1['total_growth_pct']}%)")
    for c in q1["by_category"]:
        print(f"  {c['category']:<15} +{money(c['revenue_added']):>9} "
              f"(+{c['growth_pct']:.0f}%, {c['share_of_growth_pct']:.0f}% "
              f"of growth)")
    print(f"Top 3 ({', '.join(q1['top3_categories'])}) = "
          f"{q1['top3_share_of_growth_pct']}% of all growth")

    print("\n=== Q2. How concentrated is revenue? ===")
    print(f"Top 10% ({q2['top10pct_count']} customers) = "
          f"{q2['top10pct_share']}% of revenue; top 20% "
          f"({q2['top20pct_count']}) = {q2['top20pct_share']}%; "
          f"{q2['customers_for_80pct']} of {q2['n_customers']} customers "
          f"make 80%. Top 3 = {q2['top3_share']}%.")
    for c in q2["top10_customers"]:
        chg = ("no orders" if c["current_window_revenue"] == 0
               else "new" if c["prior_window_revenue"] == 0
               else f"{c['change_pct']:+.0f}%")
        print(f"  {c['rank']:>2}. {c['CompanyName']:<30} "
              f"{money(c['lifetime_revenue']):>9} "
              f"({c['share_pct']}%)  Jan-Apr: {chg}")

    print("\n=== Q3. Do discounts buy volume? ===")
    print(f"{q3['pct_lines_discounted']}% of lines discounted. Avg units: "
          f"{q3['avg_units_full_price']} full price vs "
          f"{q3['avg_units_discounted']} discounted; "
          f"1-5% band {q3['avg_units_1_5pct']} vs >5% "
          f"{q3['avg_units_above_5pct']}.")
    print(f"Same-product check: discounted lines avg "
          f"+{q3['avg_units_lift_same_product']} units "
          f"({q3['pct_products_higher_when_discounted']}% of "
          f"{q3['products_compared']} products higher).")
    print(f"Revenue given up: {money(q3['revenue_given_up'])} "
          f"({q3['revenue_given_up_pct_of_gross']}% of gross); "
          f"{money(q3['given_up_above_5pct'])} of it is the part above 5% "
          f"on {q3['lines_above_5pct']} lines.")

    print("\n=== Q4. Which customers are at risk? ===")
    print(f"As of {q4['snapshot_date']}: {q4['at_risk_count']} at risk "
          f"({money(q4['at_risk_lifetime_revenue'])} lifetime, "
          f"{money(q4['at_risk_revenue_1997'])} in 1997), "
          f"{q4['watch_count']} on watch "
          f"({money(q4['watch_revenue_1997'])} in 1997).")
    for c in q4["flagged"]:
        print(f"  {c['status']:<8} {c['CompanyName']:<32} "
              f"{c['days_since_last']:>4} days since last order "
              f"(usual gap {c['avg_gap_days']:.0f}, "
              f"x{c['overdue_ratio']:.1f}); 1997 "
              f"{money(c['revenue_1997'])}")


def print_verification(table):
    """Print the SQL-vs-pandas comparison and the match count.

    Args:
        table (pandas.DataFrame): Output of ``verify.compare``.

    Returns:
        None. Writes to standard output.
    """
    print("\n=== Verification: SQL (sqlite3) vs pandas on raw CSVs ===")
    for _, row in table.iterrows():
        mark = "OK " if row["match"] else "MISMATCH"
        print(f"  {mark} {row['metric']:<30} "
              f"sql={verify.format_value(row['sql']):<22} "
              f"pandas={verify.format_value(row['pandas'])}")
    print(f"{int(table['match'].sum())}/{len(table)} metrics match.")


def main():
    """Build the database, run all questions, verify, and save results.

    Also copies the charts to ``docs/figures/`` for the webpage.

    Args:
        None.

    Returns:
        dict: Results for ``q1``, ``q2``, ``q3``, and ``q4`` plus a
        ``verification`` summary.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    build_database()
    results = {
        "q1": q1_growth.run(),
        "q2": q2_concentration.run(),
        "q3": q3_discounts.run(),
        "q4": q4_at_risk.run(),
    }
    check = verify.compare(results)
    results["verification"] = {
        "all_match": bool(check["match"].all()),
        "metrics": len(check),
    }
    out = ROOT / "outputs" / "results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False,
                              default=str), encoding="utf-8")
    publish_figures()
    print_findings(results)
    print_verification(check)
    return results


if __name__ == "__main__":
    main()
