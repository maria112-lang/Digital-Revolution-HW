"""Q3: whether discounts sell more units, and what they cost.

Run directly to save the Q3 chart and table to ``outputs/``.
"""

import matplotlib.pyplot as plt
import numpy as np

from db import ACCENT, MUTED, despine, query, save_figure, save_table

BAND_ORDER = ["0%", "1–5%", "6–10%", "11–15%", "16–20%", "21–25%"]
CAP = 0.05


def discount_lines():
    """Fetch every order line with its discount band.

    Args:
        None.

    Returns:
        pandas.DataFrame: One row per order line with ``Quantity``,
        ``Discount``, gross and net revenue (USD), and ``band``, one of
        ``BAND_ORDER``.
    """
    return query(
        """
        SELECT OrderID, ProductID, Quantity, Discount,
               gross_revenue, net_revenue,
               CASE
                   WHEN Discount = 0 THEN '0%'
                   WHEN Discount <= 0.05 THEN '1–5%'
                   WHEN Discount <= 0.10 THEN '6–10%'
                   WHEN Discount <= 0.15 THEN '11–15%'
                   WHEN Discount <= 0.20 THEN '16–20%'
                   ELSE '21–25%'
               END AS band
        FROM order_lines
        """
    )


def band_summary(lines):
    """Summarize units per order line for each discount band.

    Args:
        lines (pandas.DataFrame): Output of ``discount_lines``.

    Returns:
        pandas.DataFrame: One row per band in ``BAND_ORDER`` with
        ``lines``, ``avg_units``, ``median_units``, ``sd_units``, and
        ``ci95_units``, the half-width of a normal 95% confidence
        interval.
    """
    g = lines.groupby("band")["Quantity"]
    out = g.agg(lines="size", avg_units="mean", median_units="median",
                sd_units="std").reindex(BAND_ORDER)
    out["ci95_units"] = 1.96 * out["sd_units"] / np.sqrt(out["lines"])
    return out.reset_index()


def within_product_lift(lines):
    """Compare discounted and full-price units within each product.

    Args:
        lines (pandas.DataFrame): Output of ``discount_lines``.

    Returns:
        dict: Number of products sold both ways, mean per-product lift
        in average units, and percent of those products with higher
        average units when discounted.
    """
    lines = lines.assign(discounted=lines["Discount"] > 0)
    means = (lines.groupby(["ProductID", "discounted"])["Quantity"]
             .mean().unstack())
    both = means.dropna()
    diff = both[True] - both[False]
    return {
        "products_compared": int(len(both)),
        "avg_units_lift_same_product": round(diff.mean(), 1),
        "pct_products_higher_when_discounted": round(
            (diff > 0).mean() * 100, 1),
    }


def revenue_given_up():
    """Total the revenue given up to discounts.

    Args:
        None.

    Returns:
        pandas.Series: ``given_up`` and ``gross`` revenue (USD),
        ``above_cap``, the USD given up beyond a ``CAP`` discount, and
        ``lines_above_cap``.
    """
    return query(
        """
        SELECT SUM(gross_revenue - net_revenue) AS given_up,
               SUM(gross_revenue) AS gross,
               SUM(CASE WHEN Discount > ? THEN
                       gross_revenue * (Discount - ?) ELSE 0 END)
                   AS above_cap,
               SUM(CASE WHEN Discount > ? THEN 1 ELSE 0 END)
                   AS lines_above_cap
        FROM order_lines
        """,
        (CAP, CAP, CAP),
    ).iloc[0]


def plot(summary):
    """Draw average units per line by discount band with 95% CIs.

    Args:
        summary (pandas.DataFrame): Output of ``band_summary``; its
            first row must be the 0% band.

    Returns:
        pathlib.Path: Path of the saved ``q3_discounts.png``.
    """
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    colors = [MUTED] + [ACCENT] * (len(summary) - 1)
    ax.bar(summary["band"], summary["avg_units"], color=colors,
           yerr=summary["ci95_units"], capsize=4,
           error_kw={"elinewidth": 1, "ecolor": "#444"},
           label="Average units (bars: 95% confidence interval)")
    base = summary.loc[0, "avg_units"]
    ax.axhline(base, color=MUTED, ls="--", lw=1,
               label=f"Full-price average ({base:.1f} units)")
    for i, row in summary.iterrows():
        ax.text(i, row["avg_units"] + row["ci95_units"] + 0.6,
                f"{row['avg_units']:.1f}\nn={row['lines']}",
                ha="center", fontsize=8)
    ax.set_xlabel("Discount on the order line")
    ax.set_ylabel("Average units per order line")
    ax.set_title("Units sold per order line by discount level",
                 loc="left", fontsize=11)
    ax.set_ylim(0, (summary["avg_units"] + summary["ci95_units"]).max()
                * 1.25)
    ax.legend(frameon=False, loc="upper left", fontsize=8.5)
    despine(ax)
    fig.tight_layout()
    return save_figure(fig, "q3_discounts.png")


def run():
    """Run Q3 and save its chart and table.

    Args:
        None.

    Returns:
        dict: Share of lines discounted (%); average units at full
        price, discounted, at 1-5% and above 5%; revenue given up (USD
        and % of gross) and the part above 5%; the same-product lift;
        and ``bands`` records.
    """
    lines = discount_lines()
    summary = band_summary(lines)
    lift = within_product_lift(lines)
    money = revenue_given_up()
    save_table(summary.round(2), "q3_discount_bands.csv")
    plot(summary)

    full = lines[lines["Discount"] == 0]["Quantity"]
    disc = lines[lines["Discount"] > 0]["Quantity"]
    return {
        "lines": int(len(lines)),
        "pct_lines_discounted": round(len(disc) / len(lines) * 100, 1),
        "avg_units_full_price": round(full.mean(), 1),
        "avg_units_discounted": round(disc.mean(), 1),
        "avg_units_1_5pct": round(summary.loc[1, "avg_units"], 1),
        "avg_units_above_5pct": round(
            lines[lines["Discount"] > CAP]["Quantity"].mean(), 1),
        "revenue_given_up": round(money["given_up"], 2),
        "revenue_given_up_pct_of_gross": round(
            money["given_up"] / money["gross"] * 100, 1),
        "lines_above_5pct": int(money["lines_above_cap"]),
        "given_up_above_5pct": round(money["above_cap"], 2),
        **lift,
        "bands": summary.round(1).to_dict("records"),
    }


if __name__ == "__main__":
    print(run())
