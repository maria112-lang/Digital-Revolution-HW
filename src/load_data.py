"""Download the Northwind Google Sheet tabs and load them as tables."""

from pathlib import Path

import pandas as pd

SHEET_ID = "1mD4Hn4NZdJlXMC4EJcSp27vg-_jbxUYJ95vQvMbSpVM"
TABS = {
    "categories": 2047671455,
    "customers": 667254992,
    "employees": 1244043231,
    "order_details": 1881541474,
    "orders": 885169187,
    "shippers": 806775973,
    "products": 2082189938,
    "suppliers": 1298325637,
}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def export_url(gid):
    """Build the CSV export URL for one tab of the Northwind sheet.

    Args:
        gid (int): Google Sheets tab ID, as listed in ``TABS``.

    Returns:
        str: Public CSV download URL for that tab.
    """
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )


def download_all(data_dir=DATA_DIR, force=False):
    """Save every sheet tab as a CSV, dropping fully empty rows/columns.

    Args:
        data_dir (pathlib.Path): CSV folder; created if missing.
        force (bool): Re-download tabs whose CSV already exists.

    Returns:
        list[pathlib.Path]: Path of every tab's CSV, whether downloaded
        now or already present.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, gid in TABS.items():
        path = data_dir / f"{name}.csv"
        if force or not path.exists():
            df = pd.read_csv(export_url(gid))
            df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
            df.to_csv(path, index=False)
        written.append(path)
    return written


def load_tables(data_dir=DATA_DIR):
    """Load all Northwind tables, downloading any missing CSVs first.

    Args:
        data_dir (pathlib.Path): Folder holding the tab CSVs.

    Returns:
        dict[str, pandas.DataFrame]: Raw table for each key in ``TABS``.
    """
    download_all(data_dir)
    return {name: pd.read_csv(data_dir / f"{name}.csv") for name in TABS}


if __name__ == "__main__":
    for p in download_all(force=True):
        print(p)
