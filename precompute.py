"""
Run this script ONCE locally before deploying to Streamlit Cloud:
    python3 precompute.py --data /path/to/f.xlsx

It analyses the data and saves default_results.pkl next to dashboard.py.
Commit default_results.pkl to git so the cloud app loads it instantly.
"""
import pickle
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from cfpb_intelligence import load_data, run_analysis
from cfpb_intelligence.loader import top_company_filter

OUT = Path(__file__).parent / "default_results.pkl"


def enrich(df):
    res    = run_analysis(df)
    df_top = top_company_filter(df)
    amex   = df_top[df_top["Is_Focus"]]
    amex_mr = (amex.groupby("Month_dt")
               .apply(lambda g: g["Is_Monetary"].mean() * 100)
               .reset_index(name="amex_mr"))
    ind_mr  = (df_top.groupby("Month_dt")
               .apply(lambda g: g["Is_Monetary"].mean() * 100)
               .reset_index(name="ind_mr"))
    merged  = amex_mr.merge(ind_mr, on="Month_dt")
    merged["rolling_3m"] = merged["amex_mr"].rolling(3, center=True).mean()
    res["amex_mr_trend"] = merged
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default=str(Path(__file__).parent.parent.parent / "f.xlsx"),
        help="Path to the CFPB Excel/CSV file",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: file not found: {data_path}")
        sys.exit(1)

    print(f"Loading {data_path} ...")
    df = load_data(data_path)
    print(f"  {len(df):,} rows loaded")

    print("Running analysis ...")
    results = enrich(df)

    with open(OUT, "wb") as f:
        pickle.dump(results, f, protocol=4)

    kb = OUT.stat().st_size / 1024
    print(f"Saved → {OUT}  ({kb:.0f} KB)")
    print("Commit default_results.pkl to git and push.")
