"""Q1: where revenue growth comes from, by month and category.

Run directly to save the Q1 chart and tables to ``outputs/``.
"""

import matplotlib.pyplot as plt
import pandas as pd

from db import (ACCENT, MUTED, despine, last_complete_month, query,
                save_figure, save_table)


def monthly_revenue(through_month):
    """Sum net revenue and count orders per month.

    Args:
        through_month (pandas.Period): Last month to include.

    Returns:
        pandas.DataFrame: ``month`` (``YYYY-MM``), ``orders``, and
        ``net_revenue`` in USD, in month order.
    """
    df = query(
        """
        SELECT substr(OrderDate, 1, 7) AS month,
               COUNT(DISTINCT OrderID) AS orders,
               SUM(net_revenue) AS net_revenue
        FROM order_lines
        WHERE substr(OrderDate, 1, 7) <= ?
        GROUP BY month
        ORDER BY month
        """,
        (str(through_month),),
    )
    return df


def category_growth(through_month):
    """Compare category revenue, year to date vs a year earlier.

    Args:
        through_month (pandas.Period): Last month of the window; the
            window runs from January of the same year.

    Returns:
        pandas.DataFrame: One row per category with ``prior_revenue``,
        ``current_revenue``, ``revenue_added`` (USD), ``growth_pct``,
        and ``share_of_growth_pct``, largest revenue added first.
    """
    year = through_month.year
    df = query(
        """
        SELECT CategoryName AS category,
               CAST(substr(OrderDate, 1, 4) AS INTEGER) AS year,
               SUM(net_revenue) AS net_revenue
        FROM order_lines
        WHERE substr(OrderDate, 6, 2) <= ?
          AND CAST(substr(OrderDate, 1, 4) AS INTEGER) IN (?, ?)
        GROUP BY category, year
        """,
        (f"{through_month.month:02d}", year - 1, year),
    )
    wide = df.pivot(index="category", columns="year",
                    values="net_revenue").fillna(0)
    out = pd.DataFrame({
        "category": wide.index,
        "prior_revenue": wide[year - 1].values,
        "current_revenue": wide[year].values,
    })
    out["revenue_added"] = out["current_revenue"] - out["prior_revenue"]
    out["growth_pct"] = (out["current_revenue"] / out["prior_revenue"]
                         - 1) * 100
    out["share_of_growth_pct"] = (out["revenue_added"]
                                  / out["revenue_added"].sum() * 100)
    return out.sort_values("revenue_added", ascending=False,
                           ignore_index=True)


def plot(monthly, growth, through_month):
    """Draw the monthly trend and category growth chart.

    Args:
        monthly (pandas.DataFrame): Output of ``monthly_revenue``.
        growth (pandas.DataFrame): Output of ``category_growth``; its
            first 3 rows are highlighted.
        through_month (pandas.Period): Last month of the window.

    Returns:
        pathlib.Path: Path of the saved ``q1_growth.png``.
    """
    year = through_month.year
    window = f"Jan–{through_month.strftime('%b')}"
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.3, 1]}
    )

    x = pd.PeriodIndex(monthly["month"], freq="M").to_timestamp()
    ax1.plot(x, monthly["net_revenue"] / 1000, color=ACCENT, lw=2,
             marker="o", ms=3, label="Monthly net revenue")
    for y in (year - 1, year):
        ax1.axvspan(pd.Timestamp(f"{y}-01-01"),
                    pd.Timestamp(f"{y}-{through_month.month:02d}-28"),
                    color=MUTED, alpha=0.15,
                    label="Comparison window" if y == year else None)
    ax1.set_xlabel("Order month")
    ax1.set_ylabel("Net revenue (USD thousands)")
    ax1.set_title(f"Monthly net revenue, {monthly['month'].iloc[0]} to "
                  f"{monthly['month'].iloc[-1]}", loc="left", fontsize=11)
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(frameon=False, loc="upper left")
    despine(ax1)

    g = growth.iloc[::-1]
    top3_share = growth["share_of_growth_pct"].head(3).sum()
    colors = [MUTED] * (len(g) - 3) + [ACCENT] * 3
    bars = ax2.barh(g["category"], g["revenue_added"] / 1000, color=colors)
    ax2.legend([bars[-1], bars[0]],
               [f"Top 3 categories ({top3_share:.0f}% of growth)",
                "Other categories"],
               frameon=False, loc="lower right")
    for i, (added, pct) in enumerate(zip(g["revenue_added"],
                                         g["growth_pct"])):
        ax2.text(added / 1000 + 0.8, i, f"+${added / 1000:.1f}K "
                 f"(+{pct:.0f}%)", va="center", fontsize=9)
    ax2.set_xlim(0, growth["revenue_added"].max() / 1000 * 1.45)
    ax2.set_xlabel("Revenue added (USD thousands)")
    ax2.set_title(f"Revenue added by category, {window} {year} vs "
                  f"{year - 1}", loc="left", fontsize=11)
    despine(ax2)
    fig.tight_layout()
    return save_figure(fig, "q1_growth.png")


def run():
    """Run Q1 and save its chart and tables.

    Args:
        None.

    Returns:
        dict: Last complete month, window label, prior and current
        window revenue (USD), ``total_growth_pct``, the top 3 categories
        and their share of growth (%), and ``by_category`` records.
    """
    through = last_complete_month()
    monthly = monthly_revenue(through)
    growth = category_growth(through)
    save_table(monthly.round(2), "q1_monthly_revenue.csv")
    save_table(growth.round(2), "q1_category_growth.csv")
    plot(monthly, growth, through)

    prior = growth["prior_revenue"].sum()
    current = growth["current_revenue"].sum()
    top3 = growth.head(3)
    return {
        "through_month": str(through),
        "window": f"Jan–{through.strftime('%b')} {through.year} vs "
                  f"{through.year - 1}",
        "prior_revenue": round(prior, 2),
        "current_revenue": round(current, 2),
        "total_growth_pct": round((current / prior - 1) * 100, 1),
        "top3_categories": top3["category"].tolist(),
        "top3_share_of_growth_pct": round(
            top3["share_of_growth_pct"].sum(), 1),
        "by_category": growth.round(1).to_dict("records"),
    }


if __name__ == "__main__":
    print(run())
