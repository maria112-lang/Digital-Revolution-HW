"""Recompute key results with pandas on the raw CSVs.

Shares no cleaning code with the SQLite pipeline, so it
cross-checks the SQL results.
"""

import pandas as pd

from db import query
from load_data import load_tables

RAW_DATE_FMT = "%m/%d/%Y"


def raw_order_lines(tables):
    """Join raw order lines to orders and categories using pandas only.

    Args:
        tables (dict[str, pandas.DataFrame]): Raw tables from
            ``load_tables``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Orders with parsed
        ``OrderDate``, and order lines with rounded ``disc``, ``gross``
        and ``net`` revenue (USD), customer, order date, and category.
    """
    orders = tables["orders"].copy()
    orders["OrderDate"] = pd.to_datetime(orders["OrderDate"],
                                         format=RAW_DATE_FMT)
    details = tables["order_details"].copy()
    details["disc"] = details["Discount"].round(2)
    details["gross"] = details["UnitPrice"] * details["Quantity"]
    details["net"] = details["gross"] * (1 - details["disc"])
    products = tables["products"][["ProductID", "CategoryID"]]
    lines = (details
             .merge(orders[["OrderID", "CustomerID", "OrderDate"]],
                    on="OrderID")
             .merge(products, on="ProductID")
             .merge(tables["categories"][["CategoryID", "CategoryName"]],
                    on="CategoryID"))
    return orders, lines


def pandas_metrics(tables, current_year, through_month):
    """Compute the key metrics from the raw tables with pandas.

    Args:
        tables (dict[str, pandas.DataFrame]): Raw tables from
            ``load_tables``.
        current_year (int): Later year of the Q1 comparison.
        through_month (int): Last month number (1-12) of the window.

    Returns:
        dict: Unrounded metric values, keyed like ``sql_metrics``.
    """
    orders, lines = raw_order_lines(tables)
    m = {"total_net_revenue": lines["net"].sum()}

    window = lines[lines["OrderDate"].dt.month <= through_month]
    year = window["OrderDate"].dt.year
    prior = window.loc[year == current_year - 1, "net"].sum()
    current = window.loc[year == current_year, "net"].sum()
    bev = window[window["CategoryName"] == "Beverages"]
    bev_year = bev["OrderDate"].dt.year
    m.update({
        "q1_prior_revenue": prior,
        "q1_current_revenue": current,
        "q1_total_growth_pct": (current / prior - 1) * 100,
        "q1_beverages_added": (bev.loc[bev_year == current_year, "net"]
                               .sum()
                               - bev.loc[bev_year == current_year - 1,
                                         "net"].sum()),
    })

    by_cust = (lines.groupby("CustomerID")["net"].sum()
               .sort_values(ascending=False))
    share = by_cust / by_cust.sum() * 100
    m.update({
        "q2_top20pct_share": share.head(round(len(share) * 0.2)).sum(),
        "q2_customers_for_80pct": int(
            (share.cumsum() < 80).sum() + 1),
        "q2_top3_share": share.head(3).sum(),
    })

    full = lines.loc[lines["disc"] == 0, "Quantity"]
    disc = lines.loc[lines["disc"] > 0, "Quantity"]
    excess = (lines["disc"] - 0.05).clip(lower=0)
    m.update({
        "q3_avg_units_full_price": full.mean(),
        "q3_avg_units_discounted": disc.mean(),
        "q3_revenue_given_up": (lines["gross"] - lines["net"]).sum(),
        "q3_given_up_above_5pct": (lines["gross"] * excess).sum(),
    })

    snapshot = orders["OrderDate"].max()
    hist = orders.groupby("CustomerID")["OrderDate"].agg(
        ["count", "min", "max"])
    gap = (hist["max"] - hist["min"]).dt.days / (hist["count"] - 1)
    ratio = (snapshot - hist["max"]).dt.days / gap
    at_risk = hist.index[(hist["count"] >= 3) & (ratio > 2)]
    names = tables["customers"].set_index("CustomerID")["CompanyName"]
    m.update({
        "q4_at_risk_count": len(at_risk),
        "q4_at_risk_lifetime_revenue": by_cust[at_risk].sum(),
        "q4_at_risk_names": sorted(names[at_risk]),
    })
    return m


def sql_metrics(results):
    """Collect the same key metrics from the SQL-based results.

    Args:
        results (dict): Question results keyed ``q1``, ``q2``, ``q3``,
            and ``q4``, from each module's ``run``.

    Returns:
        dict: Metric values as reported (mostly rounded), keyed like
        ``pandas_metrics``.
    """
    q1, q2, q3, q4 = (results[k] for k in ("q1", "q2", "q3", "q4"))
    bev = next(r for r in q1["by_category"] if r["category"] == "Beverages")
    total = query("SELECT SUM(net_revenue) AS t FROM order_lines")["t"][0]
    return {
        "total_net_revenue": total,
        "q1_prior_revenue": q1["prior_revenue"],
        "q1_current_revenue": q1["current_revenue"],
        "q1_total_growth_pct": q1["total_growth_pct"],
        "q1_beverages_added": bev["revenue_added"],
        "q2_top20pct_share": q2["top20pct_share"],
        "q2_customers_for_80pct": q2["customers_for_80pct"],
        "q2_top3_share": q2["top3_share"],
        "q3_avg_units_full_price": q3["avg_units_full_price"],
        "q3_avg_units_discounted": q3["avg_units_discounted"],
        "q3_revenue_given_up": q3["revenue_given_up"],
        "q3_given_up_above_5pct": q3["given_up_above_5pct"],
        "q4_at_risk_count": q4["at_risk_count"],
        "q4_at_risk_lifetime_revenue": q4["at_risk_lifetime_revenue"],
        "q4_at_risk_names": q4["at_risk_names"],
    }


def values_match(a, b):
    """Check whether two metric values agree.

    Numbers match within 0.051, allowing for results rounded to 1
    decimal; lists must be equal element by element.

    Args:
        a (float | int | list): Value from one method.
        b (float | int | list): Value from the other method.

    Returns:
        bool: True if the values agree.
    """
    if isinstance(a, list) or isinstance(b, list):
        return list(a) == list(b)
    return abs(float(a) - float(b)) <= max(0.051, abs(float(b)) * 1e-9)


def compare(results):
    """Recompute key metrics in pandas and compare with the SQL results.

    Args:
        results (dict): Question results keyed ``q1``, ``q2``, ``q3``,
            and ``q4``.

    Returns:
        pandas.DataFrame: One row per metric with ``metric``, ``sql``,
        ``pandas``, and ``match``.
    """
    through = pd.Period(results["q1"]["through_month"], freq="M")
    py = pandas_metrics(load_tables(), through.year, through.month)
    sq = sql_metrics(results)
    rows = []
    for key, sql_value in sq.items():
        pd_value = py[key]
        rows.append({"metric": key, "sql": sql_value, "pandas": pd_value,
                     "match": values_match(sql_value, pd_value)})
    return pd.DataFrame(rows)


def format_value(v):
    """Format a metric value for printing.

    Args:
        v (float | int | list[str]): Value to format.

    Returns:
        str: List items joined by "; ", whole numbers under 1,000
        without decimals, other numbers with separators and 2 decimals.
    """
    if isinstance(v, list):
        return "; ".join(v)
    if float(v).is_integer() and abs(v) < 1000:
        return f"{int(v)}"
    return f"{v:,.2f}"
