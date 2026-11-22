"""Build the Northwind SQLite database and share query/plot helpers."""

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from load_data import DATA_DIR, load_tables

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = DATA_DIR / "northwind.db"
FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"

ACCENT = "#a31f34"
BLUE = "#2f6db5"
ORANGE = "#e08a1e"
MUTED = "#8a8f98"
DATE_FMT = "%m/%d/%Y"

ORDER_LINES_VIEW = """
CREATE VIEW order_lines AS
SELECT
    od.OrderID,
    od.ProductID,
    od.UnitPrice,
    od.Quantity,
    od.Discount,
    od.UnitPrice * od.Quantity AS gross_revenue,
    od.UnitPrice * od.Quantity * (1 - od.Discount) AS net_revenue,
    o.CustomerID,
    o.EmployeeID,
    o.OrderDate,
    c.CompanyName,
    c.Country,
    p.ProductName,
    cat.CategoryName
FROM order_details AS od
JOIN orders AS o ON o.OrderID = od.OrderID
JOIN customers AS c ON c.CustomerID = o.CustomerID
JOIN products AS p ON p.ProductID = od.ProductID
JOIN categories AS cat ON cat.CategoryID = p.CategoryID
"""


def build_database(db_path=DB_PATH):
    """Create a fresh SQLite database from the sheet CSVs.

    Converts order dates to ISO ``YYYY-MM-DD`` text, parses ``Freight``
    as a number, rounds discounts to 2 decimals, and adds the
    ``order_lines`` view with gross and net revenue per line.

    Args:
        db_path (pathlib.Path): Database file; deleted and rebuilt if it
            exists.

    Returns:
        pathlib.Path: ``db_path``.
    """
    tables = load_tables()

    orders = tables["orders"].copy()
    orders["Freight"] = pd.to_numeric(
        orders["Freight"].astype(str).str.replace(",", "")
    )
    for col in ["OrderDate", "RequiredDate", "ShippedDate"]:
        orders[col] = (pd.to_datetime(orders[col], format=DATE_FMT)
                       .dt.strftime("%Y-%m-%d"))
    tables["orders"] = orders

    details = tables["order_details"].copy()
    details["Discount"] = details["Discount"].round(2)
    tables["order_details"] = details

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as con:
        for name, df in tables.items():
            df.to_sql(name, con, index=False)
        con.execute(ORDER_LINES_VIEW)
    return db_path


def query(sql, params=(), db_path=DB_PATH):
    """Run a SQL query and return the result as a DataFrame.

    Builds the database first if ``db_path`` does not exist.

    Args:
        sql (str): SQLite query with ``?`` placeholders.
        params (tuple): Values for the placeholders.
        db_path (pathlib.Path): Database file.

    Returns:
        pandas.DataFrame: Query result.
    """
    if not db_path.exists():
        build_database(db_path)
    with sqlite3.connect(db_path) as con:
        return pd.read_sql_query(sql, con, params=params)


def last_complete_month(db_path=DB_PATH):
    """Return the latest month with a full month of orders.

    The month of the last order counts only if that order falls on the
    month's final day.

    Args:
        db_path (pathlib.Path): Database file.

    Returns:
        pandas.Period: Monthly period, e.g. ``1998-04``.
    """
    last = pd.Timestamp(
        query("SELECT MAX(OrderDate) AS d FROM orders", db_path=db_path)
        ["d"][0]
    )
    month = last.to_period("M")
    if last != last + pd.offsets.MonthEnd(0):
        month -= 1
    return month


def despine(ax):
    """Hide the top and right borders of a chart.

    Args:
        ax (matplotlib.axes.Axes): Axes to restyle in place.

    Returns:
        None.
    """
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def save_figure(fig, name):
    """Save a figure to ``FIG_DIR`` at 160 dpi and close it.

    Args:
        fig (matplotlib.figure.Figure): Figure to save.
        name (str): File name, including extension.

    Returns:
        pathlib.Path: Path of the saved image.
    """
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def save_table(df, name):
    """Write a table to ``TABLE_DIR`` as UTF-8 CSV, without the index.

    Args:
        df (pandas.DataFrame): Table to save.
        name (str): File name, including ``.csv``.

    Returns:
        pathlib.Path: Path of the saved CSV.
    """
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLE_DIR / name
    df.to_csv(path, index=False, encoding="utf-8")
    return path
