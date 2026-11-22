"""Q2: how concentrated revenue is among customers.

Run directly to save the Q2 charts and tables to ``outputs/``.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import (ACCENT, BLUE, MUTED, despine, last_complete_month, query,
                save_figure, save_table)


def customer_revenue():
    """Rank customers by lifetime net revenue.

    Args:
        None.

    Returns:
        pandas.DataFrame: One row per customer with ``orders``,
        ``net_revenue`` (USD), ``share_pct``, ``cumulative_share_pct``,
        and ``rank`` (1 = largest), sorted by revenue.
    """
    df = query(
        """
        SELECT CustomerID, CompanyName, Country,
               COUNT(DISTINCT OrderID) AS orders,
               SUM(net_revenue) AS net_revenue
        FROM order_lines
        GROUP BY CustomerID
        ORDER BY net_revenue DESC
        """
    )
    df["share_pct"] = df["net_revenue"] / df["net_revenue"].sum() * 100
    df["cumulative_share_pct"] = df["share_pct"].cumsum()
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def concentration(customers):
    """Summarize how much revenue the top customers hold.

    Args:
        customers (pandas.DataFrame): Output of ``customer_revenue``.

    Returns:
        dict: Customer count; count and revenue share (%) of the top
        10% and 20% of customers; customers needed to reach 80% of
        revenue; and the top 3 customers' share (%).
    """
    n = len(customers)

    def top_share(frac):
        """Return the revenue share of the top fraction of customers.

        Args:
            frac (float): Fraction of customers, 0 to 1; rounded to at
                least one customer.

        Returns:
            tuple[float, int]: Share of net revenue (%) and the
            number of customers counted.
        """
        k = max(1, round(n * frac))
        return customers["share_pct"].head(k).sum(), k

    top10, k10 = top_share(0.10)
    top20, k20 = top_share(0.20)
    return {
        "n_customers": n,
        "top10pct_count": k10,
        "top10pct_share": round(top10, 1),
        "top20pct_count": k20,
        "top20pct_share": round(top20, 1),
        "customers_for_80pct": int(
            (customers["cumulative_share_pct"] < 80).sum() + 1),
        "top3_share": round(customers["share_pct"].head(3).sum(), 1),
    }


def top_account_trend(customers, through_month, n=10):
    """Compare top customers' revenue, year to date vs a year earlier.

    Args:
        customers (pandas.DataFrame): Output of ``customer_revenue``.
        through_month (pandas.Period): Last month of the window; the
            window runs from January of the same year.
        n (int): Number of top customers to include.

    Returns:
        pandas.DataFrame: Top ``n`` customers with ``lifetime_revenue``,
        ``share_pct``, ``prior_window_revenue`` and
        ``current_window_revenue`` (USD), and ``change_pct`` (NaN when
        the prior window is 0).
    """
    year = through_month.year
    df = query(
        """
        SELECT CustomerID,
               CAST(substr(OrderDate, 1, 4) AS INTEGER) AS year,
               SUM(net_revenue) AS net_revenue
        FROM order_lines
        WHERE substr(OrderDate, 6, 2) <= ?
          AND CAST(substr(OrderDate, 1, 4) AS INTEGER) IN (?, ?)
        GROUP BY CustomerID, year
        """,
        (f"{through_month.month:02d}", year - 1, year),
    )
    wide = df.pivot(index="CustomerID", columns="year",
                    values="net_revenue").fillna(0)
    top = customers.head(n)[["rank", "CustomerID", "CompanyName",
                             "Country", "net_revenue", "share_pct"]]
    top = top.merge(wide, left_on="CustomerID", right_index=True,
                    how="left").fillna(0)
    top = top.rename(columns={year - 1: "prior_window_revenue",
                              year: "current_window_revenue",
                              "net_revenue": "lifetime_revenue"})
    top["change_pct"] = (top["current_window_revenue"]
                         / top["prior_window_revenue"].replace(0, np.nan)
                         - 1) * 100
    return top


def plot_pareto(customers, stats):
    """Draw the cumulative revenue (Pareto) curve.

    Args:
        customers (pandas.DataFrame): Output of ``customer_revenue``.
        stats (dict): Output of ``concentration``.

    Returns:
        pathlib.Path: Path of the saved ``q2_pareto.png``.
    """
    n = stats["n_customers"]
    x = customers["rank"] / n * 100
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.plot(np.r_[0, x], np.r_[0, customers["cumulative_share_pct"]],
            color=ACCENT, lw=2.2, label="Northwind customers")
    ax.plot([0, 100], [0, 100], color=MUTED, ls="--", lw=1,
            label="Equal revenue per customer (reference)")
    ax.scatter([20], [stats["top20pct_share"]], color=ACCENT, zorder=3)
    ax.annotate(f"Top 20% ({stats['top20pct_count']} customers)\n"
                f"= {stats['top20pct_share']:.0f}% of revenue",
                xy=(20, stats["top20pct_share"]), xytext=(32, 45),
                arrowprops={"arrowstyle": "->", "color": "#333"},
                fontsize=9)
    ax.set_xlabel(f"Customers ranked by net revenue (% of {n} customers)")
    ax.set_ylabel("Cumulative share of net revenue (%)")
    ax.set_title("Customer revenue concentration (Jul 1996 – May 1998)",
                 loc="left", fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, loc="lower right")
    despine(ax)
    fig.tight_layout()
    return save_figure(fig, "q2_pareto.png")


def plot_top_trend(top, through_month):
    """Draw paired bars of top customers' window revenue by year.

    Args:
        top (pandas.DataFrame): Output of ``top_account_trend``.
        through_month (pandas.Period): Last month of the window.

    Returns:
        pathlib.Path: Path of the saved ``q2_top10_trend.png``.
    """
    year = through_month.year
    window = f"Jan–{through_month.strftime('%b')}"
    t = top.iloc[::-1]
    y = np.arange(len(t))
    h = 0.38
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.barh(y - h / 2, t["prior_window_revenue"] / 1000, h, color=MUTED,
            label=f"{window} {year - 1}")
    ax.barh(y + h / 2, t["current_window_revenue"] / 1000, h, color=BLUE,
            label=f"{window} {year}")
    for yi, prior, current in zip(y, t["prior_window_revenue"],
                                  t["current_window_revenue"]):
        if current == 0:
            ax.text(0.5, yi + h / 2, "no orders", va="center",
                    fontsize=8.5, color=ACCENT, fontweight="bold")
        if prior == 0:
            ax.text(0.5, yi - h / 2, "no orders", va="center",
                    fontsize=8.5, color="#555")
    ax.set_yticks(y, [f"{r}. {c}" for r, c in zip(t["rank"],
                                                   t["CompanyName"])])
    ax.set_xlabel("Net revenue in window (USD thousands)")
    ax.set_title(f"Top 10 customers by lifetime revenue: {window} "
                 f"{year - 1} vs {year}", loc="left", fontsize=11)
    ax.legend(frameon=False, loc="lower right")
    despine(ax)
    fig.tight_layout()
    return save_figure(fig, "q2_top10_trend.png")


def run():
    """Run Q2 and save its charts and tables.

    Args:
        None.

    Returns:
        dict: Output of ``concentration`` plus ``top10_customers``
        records and ``top10_declining``, the names whose window revenue
        fell.
    """
    through = last_complete_month()
    customers = customer_revenue()
    stats = concentration(customers)
    top = top_account_trend(customers, through)
    save_table(customers.round(2), "q2_customer_revenue.csv")
    save_table(top.round(2), "q2_top10_trend.csv")
    plot_pareto(customers, stats)
    plot_top_trend(top, through)

    declining = top[top["current_window_revenue"]
                    < top["prior_window_revenue"]]
    stats.update({
        "top10_customers": top[["rank", "CompanyName", "Country",
                                "lifetime_revenue", "share_pct",
                                "prior_window_revenue",
                                "current_window_revenue",
                                "change_pct"]]
        .round(1).to_dict("records"),
        "top10_declining": declining["CompanyName"].tolist(),
    })
    return stats


if __name__ == "__main__":
    print(run())
