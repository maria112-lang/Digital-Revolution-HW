"""Q4: which repeat customers are overdue for their next order.

Run directly to save the Q4 chart and table to ``outputs/``.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import (ACCENT, BLUE, MUTED, ORANGE, despine, query, save_figure,
                save_table)

MIN_ORDERS = 3
WATCH_RATIO = 1.5
RISK_RATIO = 2.0
STATUS_COLORS = {"At risk": ACCENT, "Watch": ORANGE, "Active": BLUE}


def customer_history():
    """Fetch order history and revenue for every customer who ordered.

    Args:
        None.

    Returns:
        pandas.DataFrame: One row per customer with order count, first
        and last order dates, lifetime and 1997 net revenue (USD), and
        ``snapshot_date``, the latest order date in the data. Dates are
        ``YYYY-MM-DD`` text.
    """
    return query(
        """
        WITH order_totals AS (
            SELECT OrderID, CustomerID, CompanyName, Country, OrderDate,
                   SUM(net_revenue) AS order_revenue
            FROM order_lines
            GROUP BY OrderID
        )
        SELECT CustomerID, CompanyName, Country,
               COUNT(*) AS orders,
               MIN(OrderDate) AS first_order,
               MAX(OrderDate) AS last_order,
               SUM(order_revenue) AS lifetime_revenue,
               SUM(CASE WHEN substr(OrderDate, 1, 4) = '1997'
                        THEN order_revenue ELSE 0 END) AS revenue_1997,
               (SELECT MAX(OrderDate) FROM orders) AS snapshot_date
        FROM order_totals
        GROUP BY CustomerID
        """
    )


def classify(history):
    """Label each customer by how overdue their next order is.

    The overdue ratio is days since the last order divided by the
    customer's average days between orders, both measured to the
    snapshot date.

    Args:
        history (pandas.DataFrame): Output of ``customer_history``.

    Returns:
        pandas.DataFrame: Copy with parsed dates plus
        ``days_since_last``, ``avg_gap_days``, ``overdue_ratio``, and
        ``status``: "At risk" above ``RISK_RATIO``, "Watch" above
        ``WATCH_RATIO``, "Active", or "Under 3 orders" when below
        ``MIN_ORDERS``. Sorted by status, then revenue descending.
    """
    df = history.copy()
    for col in ("first_order", "last_order", "snapshot_date"):
        df[col] = pd.to_datetime(df[col])
    df["days_since_last"] = (df["snapshot_date"] - df["last_order"]).dt.days
    span = (df["last_order"] - df["first_order"]).dt.days
    df["avg_gap_days"] = span / (df["orders"] - 1).replace(0, np.nan)
    df["overdue_ratio"] = df["days_since_last"] / df["avg_gap_days"]
    df["status"] = np.select(
        [df["orders"] < MIN_ORDERS,
         df["overdue_ratio"] > RISK_RATIO,
         df["overdue_ratio"] > WATCH_RATIO],
        [f"Under {MIN_ORDERS} orders", "At risk", "Watch"],
        default="Active",
    )
    return df.sort_values(["status", "lifetime_revenue"],
                          ascending=[True, False], ignore_index=True)


def plot(df):
    """Draw overdue ratio against lifetime revenue for repeat customers.

    Args:
        df (pandas.DataFrame): Output of ``classify``.

    Returns:
        pathlib.Path: Path of the saved ``q4_at_risk.png``.
    """
    rated = df[df["orders"] >= MIN_ORDERS]
    fig, ax = plt.subplots(figsize=(9, 5))
    for status, color in STATUS_COLORS.items():
        s = rated[rated["status"] == status]
        ax.scatter(s["overdue_ratio"], s["lifetime_revenue"] / 1000,
                   s=36, color=color, alpha=0.85,
                   label=f"{status} ({len(s)})")
    ax.axvline(WATCH_RATIO, color=ORANGE, ls=":", lw=1,
               label=f"Watch threshold ({WATCH_RATIO:g}×)")
    ax.axvline(RISK_RATIO, color=ACCENT, ls="--", lw=1,
               label=f"At-risk threshold ({RISK_RATIO:g}×)")
    risk = rated[rated["status"] == "At risk"].sort_values("overdue_ratio")
    for i, (_, r) in enumerate(risk.iterrows()):
        ax.annotate(r["CompanyName"],
                    (r["overdue_ratio"], r["lifetime_revenue"] / 1000),
                    xytext=(-4, 10 if i % 2 else -14),
                    textcoords="offset points", fontsize=8.5,
                    ha="right" if r["overdue_ratio"] > 5 else "left")
    ax.set_xlim(-0.2, rated["overdue_ratio"].max() + 0.4)
    ax.set_xlabel("Days since last order ÷ customer's average days "
                  "between orders")
    ax.set_ylabel("Lifetime net revenue (USD thousands)")
    excluded = int((df["orders"] < MIN_ORDERS).sum())
    ax.set_title(f"Repeat customers overdue for their next order, as of "
                 f"{df['snapshot_date'].iloc[0]:%d %b %Y}",
                 loc="left", fontsize=11)
    ax.text(1, -0.16, f"{excluded} customers with fewer than {MIN_ORDERS} "
            "orders not shown.", transform=ax.transAxes, ha="right",
            fontsize=8, color="#555")
    ax.legend(title="Status (customers)", frameon=False,
              loc="upper right")
    ax.grid(alpha=0.3)
    despine(ax)
    fig.tight_layout()
    return save_figure(fig, "q4_at_risk.png")


def run():
    """Run Q4 and save its chart and table.

    Args:
        None.

    Returns:
        dict: Snapshot date; repeat-customer count; count and revenue
        (lifetime and 1997, USD) of at-risk and watch customers; at-risk
        share of revenue (%) and names; and ``flagged`` records.
    """
    df = classify(customer_history())
    out = df.drop(columns=["snapshot_date"]).copy()
    for col in ("first_order", "last_order"):
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    save_table(out.round(2), "q4_customer_recency.csv")
    plot(df)

    total = df["lifetime_revenue"].sum()
    risk = df[df["status"] == "At risk"]
    watch = df[df["status"] == "Watch"]
    cols = ["CompanyName", "Country", "orders", "last_order",
            "days_since_last", "avg_gap_days", "overdue_ratio",
            "lifetime_revenue", "revenue_1997"]
    flagged = out[out["status"].isin(["At risk", "Watch"])]
    return {
        "snapshot_date": f"{df['snapshot_date'].iloc[0]:%Y-%m-%d}",
        "repeat_customers": int((df["orders"] >= MIN_ORDERS).sum()),
        "at_risk_count": int(len(risk)),
        "at_risk_lifetime_revenue": round(risk["lifetime_revenue"].sum(), 2),
        "at_risk_revenue_1997": round(risk["revenue_1997"].sum(), 2),
        "at_risk_share_pct": round(
            risk["lifetime_revenue"].sum() / total * 100, 1),
        "at_risk_names": sorted(risk["CompanyName"]),
        "watch_count": int(len(watch)),
        "watch_lifetime_revenue": round(watch["lifetime_revenue"].sum(), 2),
        "watch_revenue_1997": round(watch["revenue_1997"].sum(), 2),
        "flagged": flagged[cols + ["status"]].round(1).to_dict("records"),
    }


if __name__ == "__main__":
    print(run())
