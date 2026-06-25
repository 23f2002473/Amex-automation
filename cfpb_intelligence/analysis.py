"""
Core analytics — all computations return plain DataFrames/dicts.
No matplotlib or Plotly here; this layer is UI-agnostic.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from .config import FOCUS_COMPANY, THRESHOLDS
from .loader import top_company_filter


def run_analysis(df: pd.DataFrame) -> dict:
    """
    Run the full analysis suite and return a results dictionary.

    Keys
    ----
    meta            : basic dataset metadata
    scorecard       : per-company KPI table
    industry_avg    : dict of industry-average metrics
    monthly_volume  : monthly complaints by company
    amex_monthly    : AMEX monthly + rolling avg + QoQ
    share_trend     : AMEX share of industry over time
    product_cmp     : AMEX vs industry product share
    issue_cmp       : AMEX vs industry issue share + over/under index
    issue_heatmap   : AMEX issue × month pivot
    issue_growth    : H1 vs H2 growth by issue
    risk_matrix     : per-issue volume × monetary relief rate
    resolution_mix  : 100 % stacked resolution breakdown
    geo_cmp         : state-level AMEX vs industry share
    """
    df_top  = top_company_filter(df)
    amex    = df_top[df_top["Is_Focus"]].copy()
    peers   = df_top[~df_top["Is_Focus"]].copy()

    results: dict = {}
    results["meta"]          = _meta(df, df_top, amex)
    results["scorecard"]     = _scorecard(df_top)
    results["industry_avg"]  = _industry_avg(results["scorecard"])
    results["monthly_volume"]= _monthly_volume(df_top)
    results["amex_monthly"]  = _amex_monthly(amex)
    results["share_trend"]   = _share_trend(df_top, amex)
    results["product_cmp"]   = _product_cmp(amex, df_top)
    results["issue_cmp"]     = _issue_cmp(amex, df_top)
    results["issue_heatmap"] = _issue_heatmap(amex)
    results["issue_growth"]  = _issue_growth(amex)
    results["risk_matrix"]   = _risk_matrix(amex)
    results["resolution_mix"]= _resolution_mix(df_top)
    results["geo_cmp"]       = _geo_cmp(amex, df_top)
    return results


# ── Individual computations ───────────────────────────────────────────────────

def _meta(df, df_top, amex) -> dict:
    return {
        "total_all":      len(df),
        "total_top9":     len(df_top),
        "amex_count":     len(amex),
        "amex_share_pct": round(len(amex) / len(df_top) * 100, 1),
        "date_min":       df["Date received"].min().date(),
        "date_max":       df["Date received"].max().date(),
        "n_companies":    df_top["Company_Short"].nunique(),
    }


def _scorecard(df_top: pd.DataFrame) -> pd.DataFrame:
    def metrics(grp):
        n = len(grp)
        return pd.Series({
            "Total Complaints":      n,
            "Monetary Relief %":     round(grp["Is_Monetary"].sum() / n * 100, 1),
            "Non-Monetary Relief %": round(grp["Is_NonMonetary"].sum() / n * 100, 1),
            "Untimely Response %":   round(grp["Is_Untimely"].sum() / n * 100, 2),
            "Explanation Only %":    round(grp["Is_ExplanOnly"].sum() / n * 100, 1),
        })

    sc = df_top.groupby("Company_Short").apply(metrics).reset_index()
    return sc.sort_values("Total Complaints", ascending=False).reset_index(drop=True)


def _industry_avg(sc: pd.DataFrame) -> dict:
    return {
        "monetary_relief_pct": round(sc["Monetary Relief %"].mean(), 1),
        "untimely_pct":        round(sc["Untimely Response %"].mean(), 2),
        "non_monetary_pct":    round(sc["Non-Monetary Relief %"].mean(), 1),
        "explanation_pct":     round(sc["Explanation Only %"].mean(), 1),
    }


def _monthly_volume(df_top: pd.DataFrame) -> pd.DataFrame:
    return (df_top.groupby(["Month_dt", "Company_Short"])
            .size().reset_index(name="complaints"))


def _amex_monthly(amex: pd.DataFrame) -> pd.DataFrame:
    m = amex.groupby("Month_dt").size().reset_index(name="complaints")
    m["rolling_3m"] = m["complaints"].rolling(3, center=True).mean()

    q = amex.groupby("Quarter").size().reset_index(name="complaints")
    q["qoq_pct"] = q["complaints"].pct_change() * 100

    return {"monthly": m, "quarterly": q}


def _share_trend(df_top: pd.DataFrame, amex: pd.DataFrame) -> pd.DataFrame:
    total  = df_top.groupby("Month_dt").size().reset_index(name="total")
    focus  = amex.groupby("Month_dt").size().reset_index(name="focus")
    merged = total.merge(focus, on="Month_dt", how="left").fillna(0)
    merged["share_pct"]    = merged["focus"] / merged["total"] * 100
    merged["rolling_share"]= merged["share_pct"].rolling(3, center=True).mean()
    return merged


def _product_cmp(amex: pd.DataFrame, df_top: pd.DataFrame) -> pd.DataFrame:
    a = amex["Product"].value_counts(normalize=True).mul(100).rename("AMEX")
    i = df_top["Product"].value_counts(normalize=True).mul(100).rename("Industry")
    cmp = pd.concat([a, i], axis=1).fillna(0)
    cmp["diff"] = cmp["AMEX"] - cmp["Industry"]
    return cmp.sort_values("AMEX", ascending=False).head(10)


def _issue_cmp(amex: pd.DataFrame, df_top: pd.DataFrame) -> pd.DataFrame:
    a = amex["Issue"].value_counts(normalize=True).mul(100).rename("AMEX")
    i = df_top["Issue"].value_counts(normalize=True).mul(100).rename("Industry")
    cmp = pd.concat([a, i], axis=1).fillna(0)
    cmp["diff"] = cmp["AMEX"] - cmp["Industry"]
    top = cmp.nlargest(12, "AMEX")
    return top.sort_values("AMEX", ascending=True)


def _issue_heatmap(amex: pd.DataFrame) -> pd.DataFrame:
    from .config import ISSUE_SHORT_LABELS
    pivot = amex.groupby(["Year_Month", "Issue"]).size().unstack(fill_value=0)
    top_issues = amex["Issue"].value_counts().head(10).index
    pivot = pivot[top_issues]
    pivot.columns = [ISSUE_SHORT_LABELS.get(c, c[:28]) for c in pivot.columns]
    return pivot


def _issue_growth(amex: pd.DataFrame) -> pd.DataFrame:
    h1 = amex[(amex["Date received"].dt.month.between(1, 6)) & (amex["Year"] == 2025)]
    h2 = amex[(amex["Date received"].dt.month.between(7, 12)) & (amex["Year"] == 2025)]
    g = pd.DataFrame({
        "H1_2025": h1["Issue"].value_counts(),
        "H2_2025": h2["Issue"].value_counts(),
    }).fillna(0)
    g = g[g["H1_2025"] >= THRESHOLDS["min_issue_count"]]
    g["growth_pct"] = (g["H2_2025"] - g["H1_2025"]) / g["H1_2025"] * 100
    return g.sort_values("growth_pct", ascending=False)


def _risk_matrix(amex: pd.DataFrame) -> pd.DataFrame:
    stats = (amex.groupby("Issue")
             .agg(count=("Complaint ID", "count"),
                  monetary_pct=("Is_Monetary", lambda x: x.mean() * 100))
             .reset_index())
    return (stats[stats["count"] >= THRESHOLDS["min_issue_count"]]
            .sort_values("count", ascending=False)
            .head(14)
            .reset_index(drop=True))


def _resolution_mix(df_top: pd.DataFrame) -> pd.DataFrame:
    from .config import RESOLUTION_TYPES
    pivot = (df_top.groupby(["Company_Short", "Company response to consumer"])
             .size().unstack(fill_value=0))
    cols  = [c for c in RESOLUTION_TYPES if c in pivot.columns]
    norm  = pivot[cols].div(pivot[cols].sum(axis=1), axis=0) * 100
    sc_order = (df_top.groupby("Company_Short").size()
                .sort_values(ascending=False).index.tolist())
    return norm.reindex([c for c in sc_order if c in norm.index])


def _geo_cmp(amex: pd.DataFrame, df_top: pd.DataFrame) -> pd.DataFrame:
    a = amex["State"].value_counts(normalize=True).mul(100).rename("AMEX")
    i = df_top["State"].value_counts(normalize=True).mul(100).rename("Industry")
    cmp = pd.concat([a, i], axis=1).fillna(0)
    cmp["diff"] = cmp["AMEX"] - cmp["Industry"]
    return cmp.sort_values("AMEX", ascending=False).head(15)
