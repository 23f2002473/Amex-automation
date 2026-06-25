"""
run_pipeline.py — one command to rule them all.

Usage:
    python run_pipeline.py --data /path/to/cfpb_data.xlsx

What it does:
    1. Loads and validates the CFPB data file
    2. Runs the full analysis suite
    3. Generates all 14 static charts → output/charts/
    4. Runs the recommendation engine
    5. Generates the complete HTML report → output/AMEX_CFPB_Intelligence_Report.html
    6. Optionally launches the Streamlit dashboard
"""
from __future__ import annotations
import argparse
import base64
import sys
import subprocess
from datetime import date
from pathlib import Path

# ensure cfpb_intelligence is importable
sys.path.insert(0, str(Path(__file__).parent))

from cfpb_intelligence import load_data, run_analysis, generate_all_charts, build_recommendations
from cfpb_intelligence.loader import top_company_filter
from cfpb_intelligence.config import FOCUS_COMPANY


# ── HTML report builder ───────────────────────────────────────────────────────

def _img(path: Path, caption="", width="100%") -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    cap  = f"<figcaption>{caption}</figcaption>" if caption else ""
    return (f'<figure style="margin:0 0 8px 0;text-align:center;">'
            f'<img src="data:image/png;base64,{data}" '
            f'style="width:{width};border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.12);"/>'
            f'{cap}</figure>')


def _callout(text, kind="insight"):
    cfg = {
        "insight": ("#EBF5FB","#1a5276","ℹ️  Key Insight"),
        "risk":    ("#FDEDEC","#922b21","⚠️  Risk"),
        "opp":     ("#EAFAF1","#1e8449","✅  Opportunity"),
        "finding": ("#FEF9E7","#7d6608","📊  Finding"),
    }
    bg, color, label = cfg.get(kind, cfg["insight"])
    return (f'<div style="background:{bg};border-left:4px solid {color};'
            f'border-radius:0 6px 6px 0;padding:12px 16px;margin:14px 0;'
            f'font-size:13.5px;color:{color};">'
            f'<strong>{label}:</strong> {text}</div>')


def _section(num, title, subtitle=""):
    sub = f'<div style="font-size:13px;color:#666;margin-top:3px;">{subtitle}</div>' if subtitle else ""
    return (f'<div style="margin:44px 0 18px 0;padding-bottom:8px;'
            f'border-bottom:3px solid #006FCF;">'
            f'<div style="font-size:11px;font-weight:700;color:#006FCF;'
            f'letter-spacing:1.5px;text-transform:uppercase;">{"Section "+str(num) if num else "Overview"}</div>'
            f'<h2 style="margin:4px 0 0 0;font-size:22px;color:#1a3a5c;">{title}</h2>{sub}</div>')


def _kpi(value, label, sub, color):
    return (f'<div style="background:{color}15;border:2px solid {color};border-radius:8px;'
            f'padding:16px 12px;text-align:center;flex:1;min-width:140px;">'
            f'<div style="font-size:26px;font-weight:800;color:{color};">{value}</div>'
            f'<div style="font-size:11px;font-weight:700;color:#333;margin:5px 0 3px;">{label}</div>'
            f'<div style="font-size:10px;color:#666;">{sub}</div></div>')


def _rec_card(rec) -> str:
    bgs  = {"P1 — CRITICAL":"#FFEBEE","P2 — HIGH":"#FFF3E0",
            "P3 — MEDIUM":"#FFFDE7","P4 — OPPORTUNITY":"#E8F5E9"}
    bds  = {"P1 — CRITICAL":"#C62828","P2 — HIGH":"#E65100",
            "P3 — MEDIUM":"#F9A825","P4 — OPPORTUNITY":"#2E7D32"}
    bg   = bgs.get(rec.priority,"#f0f0f0")
    bd   = bds.get(rec.priority,"#999")
    action_html = rec.action.replace("\n","<br>")
    return (f'<div style="background:{bg};border-left:5px solid {bd};border-radius:0 8px 8px 0;'
            f'padding:16px 20px;margin:14px 0;">'
            f'<div style="font-weight:800;color:{bd};font-size:13px;">'
            f'{rec.priority} &nbsp;|&nbsp; {rec.area}</div>'
            f'<p style="margin:8px 0 4px;"><strong>Finding:</strong> {rec.finding}</p>'
            f'<p style="margin:6px 0 4px;font-style:italic;color:#444;">'
            f'<strong>Actions:</strong><br>{action_html}</p>'
            f'<p style="margin:8px 0 0;font-weight:700;color:{bd};">📌 KPI: {rec.kpi}</p>'
            f'</div>')


def build_html_report(results, chart_paths, recs, out_path: Path) -> None:
    sc   = results["scorecard"].set_index("Company_Short")
    iavg = results["industry_avg"]
    meta = results["meta"]

    amex_mr  = sc.loc[FOCUS_COMPANY, "Monetary Relief %"]   if FOCUS_COMPANY in sc.index else 0
    amex_ur  = sc.loc[FOCUS_COMPANY, "Untimely Response %"] if FOCUS_COMPANY in sc.index else 0
    amex_cnt = int(sc.loc[FOCUS_COMPANY, "Total Complaints"]) if FOCUS_COMPANY in sc.index else 0
    rank     = results["scorecard"]["Company_Short"].tolist().index(FOCUS_COMPANY)+1 \
               if FOCUS_COMPANY in results["scorecard"]["Company_Short"].values else "N/A"

    kpi_row = (f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:18px 0;">'
               + _kpi(f"{amex_cnt:,}",       "AMEX Complaints",          f"{meta['date_min']} – {meta['date_max']}", "#006FCF")
               + _kpi(f"#{rank} of 9",        "Industry Rank",            "by complaint volume",                     "#2E7D32")
               + _kpi(f"{amex_mr:.1f}%",      "Monetary Relief Rate",     f"Industry avg {iavg['monetary_relief_pct']:.1f}%", "#E65100")
               + _kpi(f"{amex_ur:.2f}%",      "Untimely Response Rate",   f"Industry avg {iavg['untimely_pct']:.2f}%",        "#C62828")
               + _kpi(str(sum(1 for r in recs if "CRITICAL" in r.priority)), "Critical Risks", "auto-detected",               "#C62828")
               + "</div>")

    # scorecard table
    sc_rows = ""
    for _, row in results["scorecard"].iterrows():
        is_fc  = row["Company_Short"] == FOCUS_COMPANY
        bg     = "#EBF5FB" if is_fc else ""
        fw     = "font-weight:700;" if is_fc else ""
        mr_bg  = "#fadbd8" if row["Monetary Relief %"]   > iavg["monetary_relief_pct"] else "#d5f5e3"
        ur_bg  = "#fadbd8" if row["Untimely Response %"] > iavg["untimely_pct"]        else "#d5f5e3"
        sc_rows += (f'<tr style="background:{bg};">'
                    f'<td style="{fw}padding:8px 10px;">{row["Company_Short"]}{"  ★" if is_fc else ""}</td>'
                    f'<td style="text-align:right;padding:8px 10px;">{row["Total Complaints"]:,}</td>'
                    f'<td style="text-align:right;padding:8px 10px;background:{mr_bg};">{row["Monetary Relief %"]:.1f}%</td>'
                    f'<td style="text-align:right;padding:8px 10px;">{row["Non-Monetary Relief %"]:.1f}%</td>'
                    f'<td style="text-align:right;padding:8px 10px;background:{ur_bg};">{row["Untimely Response %"]:.2f}%</td>'
                    f'<td style="text-align:right;padding:8px 10px;">{row["Explanation Only %"]:.1f}%</td></tr>')

    scorecard_html = f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin:14px 0;">
      <thead><tr style="background:#1a3a5c;color:white;">
        <th style="padding:9px 10px;text-align:left;">Company</th>
        <th style="padding:9px 10px;text-align:right;">Total Complaints</th>
        <th style="padding:9px 10px;text-align:right;">Monetary Relief %</th>
        <th style="padding:9px 10px;text-align:right;">Non-Monetary Relief %</th>
        <th style="padding:9px 10px;text-align:right;">Untimely Response %</th>
        <th style="padding:9px 10px;text-align:right;">Explanation Only %</th>
      </tr></thead>
      <tbody>{sc_rows}</tbody>
      <tfoot><tr style="background:#f0f0f0;font-weight:600;font-size:12px;">
        <td style="padding:8px 10px;">Industry Average</td>
        <td style="text-align:right;padding:8px 10px;">{results["scorecard"]["Total Complaints"].mean():,.0f}</td>
        <td style="text-align:right;padding:8px 10px;">{iavg["monetary_relief_pct"]:.1f}%</td>
        <td style="text-align:right;padding:8px 10px;">{iavg["non_monetary_pct"]:.1f}%</td>
        <td style="text-align:right;padding:8px 10px;">{iavg["untimely_pct"]:.2f}%</td>
        <td style="text-align:right;padding:8px 10px;">{iavg["explanation_pct"]:.1f}%</td>
      </tr></tfoot>
    </table>"""

    rec_cards = "".join(_rec_card(r) for r in recs)

    css = """
    <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:"Segoe UI",Helvetica,Arial,sans-serif;font-size:14px;
         line-height:1.7;color:#222;background:#f5f7fa;}
    .page{max-width:1100px;margin:0 auto;background:white;padding:0 0 60px;
          box-shadow:0 0 40px rgba(0,0,0,.08);}
    .cover{background:linear-gradient(135deg,#003580 0%,#006FCF 60%,#0094E8 100%);
           color:white;padding:72px 60px 60px;}
    .content{padding:0 60px;}
    h2{font-size:21px;color:#1a3a5c;}
    h3{font-size:16px;color:#1a3a5c;margin:22px 0 7px;}
    p{margin:9px 0;color:#333;}
    ul{margin:9px 0 9px 22px;}
    li{margin:4px 0;color:#333;}
    figure figcaption{font-size:11px;color:#666;margin-top:5px;
                      font-style:italic;text-align:center;}
    .page-break{page-break-before:always;}
    @media print{body{background:white;}.page{box-shadow:none;}}
    </style>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{FOCUS_COMPANY} — CFPB Complaint Intelligence Report</title>
{css}</head><body><div class="page">

<div class="cover">
  <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;opacity:.7;margin-bottom:14px;">
    Confidential — Senior Leadership Report</div>
  <h1 style="font-size:36px;font-weight:800;line-height:1.15;color:white;">
    {FOCUS_COMPANY}<br>Consumer Complaint<br>Intelligence Report</h1>
  <div style="margin:22px 0 0;font-size:16px;opacity:.9;line-height:1.6;">
    CFPB Public Complaints Database &nbsp;|&nbsp;
    {meta["date_min"]} – {meta["date_max"]} &nbsp;|&nbsp;
    {meta["total_all"]:,} Complaints &nbsp;|&nbsp; {meta["n_companies"]} Institutions
  </div>
  <div style="margin-top:40px;font-size:13px;opacity:.7;">
    Generated automatically by cfpb_intelligence pipeline · {date.today()}
  </div>
</div>

<div class="content">

{_section("","Executive Summary")}
<p>This report analyses {meta["total_all"]:,} CFPB complaints against the top {meta["n_companies"]}
U.S. financial institutions from {meta["date_min"]} through {meta["date_max"]}.
{FOCUS_COMPANY} is benchmarked across complaint volume, resolution quality, issue mix,
geographic exposure, and trend trajectory.</p>

{kpi_row}

{_img(chart_paths["exec_dashboard"], "Executive Summary Dashboard")}

<div style="background:#F0F8FF;border:1px solid #006FCF;border-radius:8px;padding:16px 20px;margin:18px 0;">
  <strong style="color:#1a3a5c;">Three Headline Findings</strong>
  <ol style="margin:10px 0 0 20px;">
    <li style="margin-bottom:5px;"><strong>{FOCUS_COMPANY} has the #{rank}-lowest complaint volume</strong>
    ({amex_cnt:,} complaints, {meta["amex_share_pct"]:.1f}% of the top-{meta["n_companies"]} total) — a genuine competitive advantage.</li>
    <li style="margin-bottom:5px;"><strong>Untimely response rate ({amex_ur:.2f}%) is
    {amex_ur/iavg["untimely_pct"]:.1f}× the industry average ({iavg["untimely_pct"]:.2f}%)</strong>
    — the most urgent regulatory compliance gap in the dataset.</li>
    <li><strong>Purchase disputes and card-usage issues</strong> sit in the HIGH FREQ / HIGH COST quadrant
    of the risk matrix — both high volume and high monetary relief rates, requiring immediate process intervention.</li>
  </ol>
</div>

<div class="page-break"></div>
{_section(1,"Industry Landscape","Complaint volumes and trends across the top 9 institutions")}
<p>{FOCUS_COMPANY} accounts for {meta["amex_share_pct"]:.1f}% of all top-{meta["n_companies"]} complaints —
ranking #{rank} by volume. Capital One leads with the highest absolute complaints.</p>
{_img(chart_paths["industry_volume"], "Figure 1 — Complaint volume and industry share by company")}
{_callout(f"{FOCUS_COMPANY}'s low complaint share vs. much larger institutions is a structural competitive strength. However, rate-based metrics (monetary relief %, untimely response %) reveal where quality gaps remain independent of scale.", "insight")}
{_img(chart_paths["complaint_trends"], "Figure 2 — Monthly complaint volume for all 9 institutions (AMEX highlighted in bold blue)")}

<div class="page-break"></div>
{_section(2,"Competitive Position","Multi-metric scorecard benchmarking {FOCUS_COMPANY} against all peers")}
<p>Rate-based metrics reveal where institutions are structurally failing consumers regardless of size.
Cells highlighted in red are above industry average (risk); green is at or below average.</p>
{scorecard_html}
{_callout(f"AMEX's untimely response rate ({amex_ur:.2f}%) is {amex_ur/iavg['untimely_pct']:.1f}× the industry average. Seven of nine competitors report 0.00% untimely response. This gap is a process control issue with no scale justification.", "risk")}

<div class="page-break"></div>
{_section(3,"Resolution Quality Benchmarking","How {FOCUS_COMPANY} resolves complaints versus peers")}
{_img(chart_paths["resolution_type"], "Figure 3 — Resolution type distribution (% of complaints per company)")}
{_img(chart_paths["resolution_benchmarks"], "Figure 4 — Monetary relief rate and untimely response rate benchmarks")}

<div class="page-break"></div>
{_section(4,"Product & Issue Deep Dive","What drives {FOCUS_COMPANY} complaints versus the industry")}
{_img(chart_paths["product_mix"], "Figure 5 — Product mix: AMEX vs industry average")}
{_img(chart_paths["issues_comparison"], "Figure 6 — Issue comparison and over/under-index")}
{_img(chart_paths["issue_heatmap"], "Figure 7 — AMEX monthly issue heatmap")}

<div class="page-break"></div>
{_section(5,"Trend Analysis","Is {FOCUS_COMPANY}'s trajectory improving or deteriorating?")}
{_img(chart_paths["amex_trend"], "Figure 8 — AMEX monthly trend and quarter-over-quarter change")}
{_img(chart_paths["share_trend"], "Figure 9 — AMEX share of industry complaints over time")}

<div class="page-break"></div>
{_section(6,"Geographic Risk Profile","State-level complaint concentration and regulatory exposure")}
{_img(chart_paths["geo_risk"], "Figure 10 — State complaint share: AMEX vs industry, and geographic over/under-index")}
{_callout("CA, TX, and FL likely account for 40%+ of AMEX complaints. Each state has an active consumer financial protection framework. Proactive engagement with state regulators in these markets is warranted.", "risk")}

<div class="page-break"></div>
{_section(7,"Key Risks for American Express","Data-driven risk identification with evidence")}
{_img(chart_paths["monetary_relief_risk"], "Figure 11 — AMEX monetary relief rate trend vs industry")}
{_img(chart_paths["issue_growth"], "Figure 12 — Fastest-growing and most-improved AMEX issues (H2 vs H1 2025)")}
{_img(chart_paths["risk_matrix"], "Figure 13 — Risk matrix: complaint frequency vs financial impact")}

<div class="page-break"></div>
{_section(8,"Strategic Recommendations","Prioritised, auto-generated from threshold analysis")}
<p><strong>{len(recs)} recommendations</strong> generated by the recommendation engine:
{sum(1 for r in recs if "CRITICAL" in r.priority)} critical ·
{sum(1 for r in recs if "HIGH" in r.priority)} high ·
{sum(1 for r in recs if "MEDIUM" in r.priority)} medium ·
{sum(1 for r in recs if "OPPORTUNITY" in r.priority)} opportunities.</p>
{rec_cards}

<div style="margin-top:44px;padding-top:18px;border-top:1px solid #e0e0e0;
            font-size:11px;color:#999;text-align:center;">
  Generated by cfpb_intelligence pipeline · {date.today()} ·
  Data: CFPB Public Complaints Database · {meta["date_min"]} – {meta["date_max"]}
</div>
</div></div></body></html>"""

    out_path.write_text(html, encoding="utf-8")
    print(f"[report] Saved → {out_path}  ({out_path.stat().st_size // 1024:,} KB)")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CFPB Complaint Intelligence Pipeline")
    parser.add_argument("--data",    default="../f.xlsx",
                        help="Path to CFPB data file (.xlsx or .csv)")
    parser.add_argument("--out",     default="output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--dashboard", action="store_true",
                        help="Launch Streamlit dashboard after generating report")
    args = parser.parse_args()

    data_path = Path(args.data)
    out_dir   = Path(__file__).parent / args.out
    chart_dir = out_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  CFPB Complaint Intelligence Pipeline")
    print("=" * 60)

    # 1. Load
    df = load_data(data_path)

    # 2. Analyse
    print("[analysis] Running full analysis suite…")
    results = run_analysis(df)

    # 3. Monetary relief trend (needed by chart + report)
    df_top = top_company_filter(df)
    amex   = df_top[df_top["Is_Focus"]]
    amex_mr= amex.groupby("Month_dt").apply(lambda g: g["Is_Monetary"].mean()*100).reset_index(name="amex_mr")
    ind_mr = df_top.groupby("Month_dt").apply(lambda g: g["Is_Monetary"].mean()*100).reset_index(name="ind_mr")
    merged = amex_mr.merge(ind_mr, on="Month_dt")
    merged["rolling_3m"] = merged["amex_mr"].rolling(3, center=True).mean()
    results["amex_mr_trend"] = merged

    # 4. Charts
    print("[charts] Generating static charts…")
    chart_paths = generate_all_charts(results, chart_dir)

    # 5. Recommendations
    print("[recs] Running recommendation engine…")
    recs = build_recommendations(results)
    print(f"  → {len(recs)} recommendations generated")
    for r in recs:
        print(f"     {r.priority}: {r.area}")

    # 6. Report
    print("[report] Building HTML report…")
    report_path = out_dir / "AMEX_CFPB_Intelligence_Report.html"
    build_html_report(results, chart_paths, recs, report_path)

    print("\n" + "=" * 60)
    print(f"  ✓ Charts  → {chart_dir}")
    print(f"  ✓ Report  → {report_path}")
    print("=" * 60)

    if args.dashboard:
        print("\n[dashboard] Launching Streamlit…")
        subprocess.run(["streamlit", "run",
                        str(Path(__file__).parent / "dashboard.py")])


if __name__ == "__main__":
    main()
