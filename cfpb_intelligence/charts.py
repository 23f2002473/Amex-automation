"""
Static chart generator — saves all figures as PNG files for the HTML report.
Matplotlib only; no Plotly dependency here.
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
import seaborn as sns
import numpy as np
from pathlib import Path

from .config import COLORS, COMPANY_PALETTE, FOCUS_COMPANY, ISSUE_SHORT_LABELS

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "#F7F9FC",
    "axes.grid": True, "grid.alpha": 0.35, "grid.linestyle": "--",
    "font.family": "DejaVu Sans", "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.labelsize": 11, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
})

A  = COLORS["amex"]
P  = COLORS["peer"]
R  = COLORS["risk_red"]
G  = COLORS["safe_green"]
W  = COLORS["warn_amber"]


def generate_all_charts(results: dict, out_dir: str | Path) -> dict[str, Path]:
    """
    Generate all analysis charts and save as PNGs in out_dir.
    Returns a dict mapping chart name → file path.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    fns = [
        ("industry_volume",       _industry_volume),
        ("complaint_trends",      _complaint_trends),
        ("resolution_type",       _resolution_type),
        ("resolution_benchmarks", _resolution_benchmarks),
        ("product_mix",           _product_mix),
        ("issues_comparison",     _issues_comparison),
        ("issue_heatmap",         _issue_heatmap),
        ("amex_trend",            _amex_trend),
        ("share_trend",           _share_trend),
        ("geo_risk",              _geo_risk),
        ("monetary_relief_risk",  _monetary_relief_risk),
        ("issue_growth",          _issue_growth),
        ("risk_matrix",           _risk_matrix),
        ("exec_dashboard",        _exec_dashboard),
    ]
    for name, fn in fns:
        p = out_dir / f"fig_{name}.png"
        print(f"  [chart] {name} …")
        fn(results, p)
        paths[name] = p

    return paths


# ── Individual chart functions ────────────────────────────────────────────────

def _bar_colors(index, focus=FOCUS_COMPANY):
    return [A if c == focus else P for c in index]


def _industry_volume(r, path):
    vol = r["scorecard"].set_index("Company_Short")["Total Complaints"].sort_values()
    pct = vol / vol.sum() * 100
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for ax, data, xlabel, fmt in [
        (axes[0], vol,  "Number of Complaints", "{:,}"),
        (axes[1], pct,  "% of Total Complaints", "{:.1f}%"),
    ]:
        bars = ax.barh(data.index, data.values, color=_bar_colors(data.index), edgecolor="white")
        for bar, v in zip(bars, data.values):
            ax.text(v + data.max()*0.01, bar.get_y()+bar.get_height()/2,
                    fmt.format(v), va="center", fontsize=8.5, color="#444")
        ax.set_xlabel(xlabel); ax.set_xlim(0, data.max()*1.18)
    axes[0].set_title("Complaint Volume by Company\n(Jan 2025 – Mar 2026)", pad=10)
    axes[1].set_title("Share of Industry Complaints (%)", pad=10)
    axes[0].legend(handles=[mpatches.Patch(color=A, label=FOCUS_COMPANY),
                             mpatches.Patch(color=P, label="Competitors")], loc="lower right")
    plt.suptitle("Industry Complaint Distribution", fontsize=15, fontweight="bold", y=1.01)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _complaint_trends(r, path):
    mv = r["monthly_volume"]
    fig, ax = plt.subplots(figsize=(16, 6))
    for co, grp in mv.groupby("Company_Short"):
        ax.plot(grp["Month_dt"], grp["complaints"], label=co,
                color=COMPANY_PALETTE.get(co, "#999"),
                linewidth=3.0 if co == FOCUS_COMPANY else 1.0,
                zorder=10 if co == FOCUS_COMPANY else 1,
                alpha=1.0 if co == FOCUS_COMPANY else 0.5,
                marker="o" if co == FOCUS_COMPANY else None, markersize=4)
    ax.set_title(f"Monthly Complaint Volume — Top 9 Institutions\n({FOCUS_COMPANY} highlighted)", pad=10)
    ax.set_xlabel("Month"); ax.set_ylabel("Complaints")
    ax.legend(ncol=2, fontsize=8, framealpha=0.9)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    plt.xticks(rotation=35, ha="right"); plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _resolution_type(r, path):
    rm = r["resolution_mix"]
    from .config import RESOLUTION_TYPES
    res_colors = ["#C62828","#EF9A9A","#CFD8DC","#FFA000","#37474F"]
    fig, ax = plt.subplots(figsize=(14, 7))
    bottom = np.zeros(len(rm))
    for col, color in zip(RESOLUTION_TYPES, res_colors):
        if col in rm.columns:
            vals = rm[col].values
            bars = ax.bar(rm.index, vals, bottom=bottom, color=color,
                          label=col.replace("Closed with ","").title(),
                          edgecolor="white", linewidth=0.5)
            for i, (bar, val) in enumerate(zip(bars, vals)):
                if val > 5:
                    ax.text(bar.get_x()+bar.get_width()/2, bottom[i]+val/2,
                            f"{val:.0f}%", ha="center", va="center",
                            fontsize=7.5, color="white", fontweight="bold")
            bottom += vals
    ax.set_title("Resolution Type by Company (% of complaints)", pad=10)
    ax.set_ylabel("% of Complaints"); ax.set_ylim(0, 110)
    ax.set_xticklabels(rm.index, rotation=30, ha="right")
    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _resolution_benchmarks(r, path):
    sc   = r["scorecard"].set_index("Company_Short")
    iavg = r["industry_avg"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for ax, col, avg_key, title, xlabel, good_low in [
        (axes[0], "Monetary Relief %",   "monetary_relief_pct",
         "Monetary Relief Rate (%)\n(Higher = more costly)", "% Monetary Relief", False),
        (axes[1], "Untimely Response %", "untimely_pct",
         "Untimely Response Rate (%)\n(Lower is better)",     "% Untimely",       True),
    ]:
        data   = sc[col].sort_values(ascending=True)
        colors = _bar_colors(data.index)
        bars   = ax.barh(data.index, data.values, color=colors, edgecolor="white")
        avg    = iavg[avg_key]
        ax.axvline(avg, color=R, linestyle="--", linewidth=1.5, label=f"Industry avg: {avg}")
        for bar, val in zip(bars, data.values):
            ax.text(val + data.max()*0.01, bar.get_y()+bar.get_height()/2,
                    f"{val:.2f}%" if col == "Untimely Response %" else f"{val:.1f}%",
                    va="center", fontsize=8.5)
        ax.set_title(title, pad=10); ax.set_xlabel(xlabel); ax.legend(fontsize=9)
    plt.suptitle("Resolution Quality Benchmarking", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _product_mix(r, path):
    cmp = r["product_cmp"].sort_values("AMEX", ascending=True)
    fig, ax = plt.subplots(figsize=(14, 7))
    y = np.arange(len(cmp)); h = 0.35
    ax.barh(y+h/2, cmp["AMEX"],     h, color=A, label=FOCUS_COMPANY, alpha=0.9)
    ax.barh(y-h/2, cmp["Industry"], h, color=P, label="Industry Avg", alpha=0.9)
    ax.set_yticks(y); ax.set_yticklabels(cmp.index, fontsize=9)
    ax.set_title(f"Product Mix — {FOCUS_COMPANY} vs Industry Average\n(% of complaints)", pad=10)
    ax.set_xlabel("% of Complaints"); ax.legend(fontsize=10)
    for i, (a, b) in enumerate(zip(cmp["AMEX"], cmp["Industry"])):
        ax.text(a+0.3, i+h/2, f"{a:.1f}%", va="center", fontsize=8)
        ax.text(b+0.3, i-h/2, f"{b:.1f}%", va="center", fontsize=8)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _issues_comparison(r, path):
    cmp  = r["issue_cmp"]
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    y = np.arange(len(cmp)); h = 0.35
    axes[0].barh(y+h/2, cmp["AMEX"],     h, color=A, label=FOCUS_COMPANY, alpha=0.9)
    axes[0].barh(y-h/2, cmp["Industry"], h, color=P, label="Industry",     alpha=0.9)
    axes[0].set_yticks(y); axes[0].set_yticklabels(cmp.index, fontsize=9)
    axes[0].set_title(f"Top Issues — {FOCUS_COMPANY} vs Industry Average\n(% of complaints)", pad=10)
    axes[0].set_xlabel("% of Complaints"); axes[0].legend(fontsize=9)

    diff = cmp["diff"].sort_values()
    axes[1].barh(diff.index, diff.values,
                 color=[R if v > 0 else G for v in diff.values], alpha=0.85)
    axes[1].axvline(0, color="black", linewidth=1)
    axes[1].set_title(f"{FOCUS_COMPANY} Over/Under-Index vs Industry\n(Red = higher than peers)", pad=10)
    axes[1].set_xlabel("Percentage Point Difference")
    for i, val in enumerate(diff.values):
        axes[1].text(val+(0.1 if val >= 0 else -0.1), i, f"{val:+.1f}pp",
                     va="center", ha="left" if val >= 0 else "right", fontsize=8)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _issue_heatmap(r, path):
    pivot = r["issue_heatmap"]
    fig, ax = plt.subplots(figsize=(16, 7))
    sns.heatmap(pivot.T, ax=ax, cmap="YlOrRd", linewidths=0.3,
                fmt="d", annot=True, annot_kws={"size": 7},
                cbar_kws={"label": "Complaints"})
    ax.set_title(f"{FOCUS_COMPANY} — Monthly Issue Heatmap (Darker = more complaints)", pad=10)
    ax.set_xticklabels([str(p) for p in pivot.index], rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("")
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _amex_trend(r, path):
    m = r["amex_monthly"]["monthly"]
    q = r["amex_monthly"]["quarterly"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 10))
    axes[0].fill_between(m["Month_dt"], m["complaints"], alpha=0.2, color=A)
    axes[0].plot(m["Month_dt"], m["complaints"], color=A, alpha=0.5, linewidth=1,
                 marker="o", markersize=4, label="Monthly")
    axes[0].plot(m["Month_dt"], m["rolling_3m"], color=A, linewidth=2.5, label="3-Month Rolling Avg")
    axes[0].set_title(f"{FOCUS_COMPANY} — Monthly Complaint Volume with Trend", pad=10)
    axes[0].set_ylabel("Complaints"); axes[0].legend()
    axes[0].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    axes[0].tick_params(axis="x", rotation=30)

    qoq_colors = [G if v < 0 else R for v in q["qoq_pct"].fillna(0)]
    axes[1].bar(q["Quarter"].astype(str), q["qoq_pct"].fillna(0),
                color=qoq_colors, edgecolor="white", alpha=0.85)
    axes[1].axhline(0, color="black", linewidth=1)
    for i, val in enumerate(q["qoq_pct"].fillna(0)):
        if i > 0:
            axes[1].text(i, val+(1 if val >= 0 else -2.5), f"{val:+.1f}%",
                         ha="center", fontsize=9, fontweight="bold",
                         color=R if val > 0 else G)
    axes[1].set_title(f"{FOCUS_COMPANY} — Quarter-over-Quarter Complaint Change (%)", pad=10)
    axes[1].set_ylabel("QoQ Change (%)"); axes[1].set_xlabel("Quarter")
    axes[1].tick_params(axis="x", rotation=20)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _share_trend(r, path):
    s    = r["share_trend"]
    avg  = s["share_pct"].mean()
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.fill_between(s["Month_dt"], s["share_pct"], alpha=0.15, color=A)
    ax.plot(s["Month_dt"], s["share_pct"], color=A, alpha=0.5, linewidth=1, marker="o", markersize=4)
    ax.plot(s["Month_dt"], s["rolling_share"], color=A, linewidth=2.5, label="3M Rolling Share")
    ax.axhline(avg, color=W, linestyle="--", linewidth=1.5, label=f"Average: {avg:.1f}%")
    ax.set_title(f"{FOCUS_COMPANY} Share of Industry Complaints\n(Rising = growing faster than peers)", pad=10)
    ax.set_ylabel("% of Industry Complaints"); ax.set_xlabel("Month"); ax.legend()
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _geo_risk(r, path):
    geo  = r["geo_cmp"].head(12)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    y = np.arange(len(geo)); h = 0.35
    axes[0].barh(y+h/2, geo["AMEX"],     h, color=A, label=FOCUS_COMPANY, alpha=0.9)
    axes[0].barh(y-h/2, geo["Industry"], h, color=P, label="Industry",     alpha=0.9)
    axes[0].set_yticks(y); axes[0].set_yticklabels(geo.index)
    axes[0].invert_yaxis()
    axes[0].set_title(f"Top States — {FOCUS_COMPANY} vs Industry (%)", pad=10)
    axes[0].set_xlabel("% of Complaints"); axes[0].legend()

    diff = geo["diff"].sort_values()
    axes[1].barh(diff.index, diff.values,
                 color=[R if v > 0 else G for v in diff.values], alpha=0.85)
    axes[1].axvline(0, color="black", linewidth=1)
    axes[1].set_title(f"{FOCUS_COMPANY} Geographic Over/Under-Index\n(Red = higher than industry)", pad=10)
    axes[1].set_xlabel("Percentage Point Difference")
    for i, val in enumerate(diff.values):
        axes[1].text(val+(0.05 if val >= 0 else -0.05), i, f"{val:+.1f}pp",
                     va="center", ha="left" if val >= 0 else "right", fontsize=8)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _monetary_relief_risk(r, path):
    from .loader import top_company_filter
    m_amex = r["share_trend"].copy()
    # recompute amex monetary trend from analysis results
    amex_mr_trend = r.get("amex_mr_trend")
    if amex_mr_trend is None:
        plt.figure(figsize=(8,4))
        plt.text(0.5,0.5,"Monetary relief trend not available", ha="center", va="center")
        plt.savefig(path, dpi=100); plt.close(); return

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].fill_between(amex_mr_trend["Month_dt"], amex_mr_trend["amex_mr"], alpha=0.15, color=R)
    axes[0].plot(amex_mr_trend["Month_dt"], amex_mr_trend["amex_mr"],
                 color=R, alpha=0.5, linewidth=1, marker="o", markersize=4, label="Monthly")
    axes[0].plot(amex_mr_trend["Month_dt"], amex_mr_trend["rolling_3m"],
                 color=R, linewidth=2.5, label="3M Rolling Avg")
    axes[0].set_title(f"{FOCUS_COMPANY} — Monetary Relief Rate Over Time", pad=10)
    axes[0].set_ylabel("% Monetary Relief"); axes[0].legend()
    axes[0].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    axes[0].tick_params(axis="x", rotation=30)

    axes[1].plot(amex_mr_trend["Month_dt"], amex_mr_trend["amex_mr"],
                 color=A, linewidth=2, label=FOCUS_COMPANY, marker="o", markersize=4)
    axes[1].plot(amex_mr_trend["Month_dt"], amex_mr_trend["ind_mr"],
                 color=P, linewidth=2, label="Industry Avg", linestyle="--")
    axes[1].set_title(f"Monetary Relief Rate — {FOCUS_COMPANY} vs Industry", pad=10)
    axes[1].set_ylabel("% Monetary Relief Rate"); axes[1].legend()
    axes[1].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    axes[1].tick_params(axis="x", rotation=30)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _issue_growth(r, path):
    ig   = r["issue_growth"]
    grow = ig.head(8)
    decl = ig.tail(8).sort_values("growth_pct")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    for ax, data, title in [
        (axes[0], grow[::-1], f"Fastest-Growing {FOCUS_COMPANY} Issues\n(H2 vs H1 2025)"),
        (axes[1], decl[::-1], f"Most-Improved {FOCUS_COMPANY} Issues\n(H2 vs H1 2025)"),
    ]:
        ax.barh(data.index, data["growth_pct"],
                color=[R if v > 0 else G for v in data["growth_pct"]], alpha=0.85)
        ax.axvline(0, color="black", linewidth=1)
        ax.set_title(title, pad=10); ax.set_xlabel("% Change in Complaint Volume")
        for i, val in enumerate(data["growth_pct"]):
            ax.text(val+(0.5 if val >= 0 else -0.5), i, f"{val:+.0f}%",
                    va="center", ha="left" if val >= 0 else "right", fontsize=9)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _risk_matrix(r, path):
    rm   = r["risk_matrix"]
    fig, ax = plt.subplots(figsize=(13, 8))
    sc   = ax.scatter(rm["count"], rm["monetary_pct"],
                      s=rm["count"]/3, c=rm["monetary_pct"],
                      cmap="RdYlGn_r", alpha=0.75, edgecolors="white", linewidths=0.8,
                      vmin=0, vmax=rm["monetary_pct"].max())
    med_c = rm["count"].median(); med_m = rm["monetary_pct"].median()
    ax.axvline(med_c, color="gray", linestyle="--", alpha=0.5)
    ax.axhline(med_m, color="gray", linestyle="--", alpha=0.5)
    for _, row in rm.iterrows():
        label = row["Issue"][:35]+"…" if len(row["Issue"]) > 35 else row["Issue"]
        ax.annotate(label, (row["count"], row["monetary_pct"]),
                    textcoords="offset points", xytext=(6,3), fontsize=7.5, alpha=0.85)
    plt.colorbar(sc, ax=ax, label="Monetary Relief Rate (%)")
    ax.set_title(f"{FOCUS_COMPANY} Risk Matrix — Complaint Frequency vs Financial Impact\n"
                 "(Bubble size = complaint count | Top-right = highest priority)", pad=12)
    ax.set_xlabel("Number of Complaints"); ax.set_ylabel("Monetary Relief Rate (%)")
    xl, yl = ax.get_xlim(), ax.get_ylim()
    ax.text(xl[1]*0.98, yl[1]*0.97, "HIGH FREQ\nHIGH COST",  ha="right", va="top",    fontsize=9, color=R, fontweight="bold", alpha=0.6)
    ax.text(xl[0]*1.02, yl[1]*0.97, "LOW FREQ\nHIGH COST",   ha="left",  va="top",    fontsize=9, color=W, fontweight="bold", alpha=0.6)
    ax.text(xl[1]*0.98, yl[0]*1.02, "HIGH FREQ\nLOW COST",   ha="right", va="bottom", fontsize=9, color=W, fontweight="bold", alpha=0.6)
    ax.text(xl[0]*1.02, yl[0]*1.02, "LOW FREQ\nLOW COST",    ha="left",  va="bottom", fontsize=9, color=G, fontweight="bold", alpha=0.6)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _exec_dashboard(r, path):
    sc   = r["scorecard"].set_index("Company_Short")
    iavg = r["industry_avg"]
    meta = r["meta"]
    m    = r["amex_monthly"]["monthly"]

    amex_mr  = sc.loc[FOCUS_COMPANY, "Monetary Relief %"]   if FOCUS_COMPANY in sc.index else 0
    amex_ur  = sc.loc[FOCUS_COMPANY, "Untimely Response %"] if FOCUS_COMPANY in sc.index else 0

    fig  = plt.figure(figsize=(20, 14))
    fig.patch.set_facecolor("white")
    gs   = GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.4)

    kpi_data = [
        (f"{meta['amex_count']:,}",  "Total AMEX Complaints",    f"{meta['date_min']} – {meta['date_max']}", A),
        (f"#{_rank(r)}  of 9",       "Industry Rank (volume)",   "Lower is better",                          G),
        (f"{amex_mr:.1f}%",          "Monetary Relief Rate",     f"Industry avg {iavg['monetary_relief_pct']:.1f}%", W),
        (f"{amex_ur:.2f}%",          "Untimely Response Rate",   f"Industry avg {iavg['untimely_pct']:.2f}%", R),
    ]
    for i, (val, label, sub, color) in enumerate(kpi_data):
        ax = fig.add_subplot(gs[0, i])
        ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
        ax.add_patch(plt.Rectangle((0,0),1,1, transform=ax.transAxes,
                                    facecolor=color+"22", edgecolor=color, linewidth=2, clip_on=False))
        ax.text(0.5,0.72, val,   ha="center", va="center", fontsize=22, fontweight="bold", color=color, transform=ax.transAxes)
        ax.text(0.5,0.42, label, ha="center", va="center", fontsize=10, fontweight="bold", color="#333", transform=ax.transAxes)
        ax.text(0.5,0.18, sub,   ha="center", va="center", fontsize=8,  color="#666",      transform=ax.transAxes)

    ax_t = fig.add_subplot(gs[1, :2])
    ax_t.fill_between(m["Month_dt"], m["complaints"], alpha=0.2, color=A)
    ax_t.plot(m["Month_dt"], m["complaints"], color=A, alpha=0.5, linewidth=1)
    ax_t.plot(m["Month_dt"], m["rolling_3m"], color=A, linewidth=2.5, label="3M Avg")
    ax_t.set_title(f"{FOCUS_COMPANY} Monthly Complaint Trend", fontsize=11, fontweight="bold")
    ax_t.set_ylabel("Complaints")
    ax_t.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %y"))
    ax_t.tick_params(axis="x", rotation=30, labelsize=8); ax_t.legend(fontsize=8)

    ax_p = fig.add_subplot(gs[1, 2:])
    amex_res = r["resolution_mix"].loc[FOCUS_COMPANY] if FOCUS_COMPANY in r["resolution_mix"].index else None
    if amex_res is not None:
        wedges, texts, autotexts = ax_p.pie(
            amex_res.values, labels=None,
            colors=["#C62828","#EF9A9A","#CFD8DC","#FFA000","#37474F"][:len(amex_res)],
            autopct="%1.1f%%", startangle=90, pctdistance=0.75,
            wedgeprops={"edgecolor": "white", "linewidth":1.5})
        for at in autotexts: at.set_fontsize(8)
        ax_p.legend(amex_res.index, loc="lower center", bbox_to_anchor=(0.5,-0.2),
                    ncol=2, fontsize=7.5, framealpha=0.9)
    ax_p.set_title(f"{FOCUS_COMPANY} Resolution Breakdown", fontsize=11, fontweight="bold")

    ax_i = fig.add_subplot(gs[2, :2])
    top6  = r["risk_matrix"].nlargest(6,"count")
    ax_i.barh(top6["Issue"].str[:40][::-1], top6["count"][::-1],
              color=[R if i < 2 else W if i < 4 else P for i in range(5,-1,-1)], alpha=0.85)
    ax_i.set_title(f"{FOCUS_COMPANY} Top 6 Complaint Issues", fontsize=11, fontweight="bold")
    ax_i.set_xlabel("Complaints"); ax_i.tick_params(axis="y", labelsize=8)

    ax_r = fig.add_subplot(gs[2, 2:])
    cv   = r["scorecard"].set_index("Company_Short")["Total Complaints"].sort_values()
    ax_r.barh(cv.index, cv.values, color=_bar_colors(cv.index), alpha=0.85)
    ax_r.set_title("Complaint Volume Rank — All Peers", fontsize=11, fontweight="bold")
    ax_r.set_xlabel("Total Complaints"); ax_r.tick_params(axis="y", labelsize=8)

    fig.suptitle(f"{FOCUS_COMPANY} — CFPB Complaint Intelligence\n"
                 f"Executive Summary | {meta['date_min']} – {meta['date_max']}",
                 fontsize=16, fontweight="bold", y=1.01)
    plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _rank(r) -> int:
    names = r["scorecard"]["Company_Short"].tolist()
    return names.index(FOCUS_COMPANY) + 1 if FOCUS_COMPANY in names else 0
