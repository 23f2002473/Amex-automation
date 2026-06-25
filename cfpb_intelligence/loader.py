"""
Data loader — accepts any CFPB-format Excel or CSV file.
Returns a fully enriched DataFrame ready for analysis.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
from .config import COMPANY_LABELS, FOCUS_COMPANY

REQUIRED_COLUMNS = {
    "Date received",
    "Product",
    "Sub-product",
    "Issue",
    "Company",
    "State",
    "Company response to consumer",
    "Timely response?",
    "Complaint ID",
}


def load_data(path: str | Path) -> pd.DataFrame:
    """
    Load a CFPB complaints file (Excel or CSV), validate it,
    and return an enriched DataFrame.

    Parameters
    ----------
    path : str or Path
        Path to the .xlsx or .csv file.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame with derived columns added.

    Raises
    ------
    ValueError
        If required columns are missing.
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    print(f"[loader] Reading {path.name} …")
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    _validate(df)
    df = _enrich(df)
    print(f"[loader] Loaded {len(df):,} complaints | "
          f"{df['Date received'].min().date()} → {df['Date received'].max().date()}")
    return df


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Data file is missing required columns: {sorted(missing)}\n"
            f"Available columns: {sorted(df.columns.tolist())}"
        )


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Datetime
    df["Date received"] = pd.to_datetime(df["Date received"], utc=True, errors="coerce")
    df.dropna(subset=["Date received"], inplace=True)

    # Time dimensions
    df["Year_Month"] = df["Date received"].dt.to_period("M")
    df["Month_dt"]   = df["Year_Month"].dt.to_timestamp()
    df["Quarter"]    = df["Date received"].dt.to_period("Q")
    df["Year"]       = df["Date received"].dt.year

    # Short company names
    df["Company_Short"] = df["Company"].map(COMPANY_LABELS).fillna(df["Company"])

    # Boolean convenience flags
    df["Is_Focus"]         = df["Company_Short"] == FOCUS_COMPANY
    df["Is_Monetary"]      = df["Company response to consumer"] == "Closed with monetary relief"
    df["Is_NonMonetary"]   = df["Company response to consumer"] == "Closed with non-monetary relief"
    df["Is_Untimely"]      = df["Timely response?"] == "No"
    df["Is_ExplanOnly"]    = df["Company response to consumer"] == "Closed with explanation"

    return df


def top_company_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows belonging to the configured top companies."""
    return df[df["Company_Short"].isin(COMPANY_LABELS.values())].copy()
