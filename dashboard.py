"""
Interactive Streamlit dashboard — drop in any CFPB file and explore.
Run with:  streamlit run dashboard.py
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from cfpb_intelligence import load_data, run_analysis, build_recommendations
from cfpb_intelligence.loader import top_company_filter
from cfpb_intelligence.config import (
    FOCUS_COMPANY, COMPANY_PALETTE, COLORS, ISSUE_SHORT_LABELS
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CFPB Complaint Intelligence",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background: #f5f7fa; }
  [data-testid="stMetric"] {
    background: var(--secondary-background-color);
    border-radius: 8px;
    padding: 14px 16px;
    border: 1px solid rgba(128,128,128,0.15);
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  [data-testid="stMetricLabel"] { color: var(--text-color) !important; }
  [data-testid="stMetricValue"] { color: var(--text-color) !important; }
  [data-testid="stMetricDelta"] { color: var(--text-color) !important; }
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  h1 { color: #1a3a5c !important; }
  h2 { color: #1a3a5c !important; font-size: 1.3rem !important; }
  .rec-card { border-radius: 8px; padding: 14px 18px; margin-bottom: 10px; border-left: 5px solid; }
  .stTabs {
    margin-top: 1.2rem;
  }
  .stTabs [data-baseweb="tab-list"] {
    gap: 0px;
    border-bottom: 2px solid #d0d7e2;
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-top: 8px;
  }
  .stTabs [data-baseweb="tab"] {
    padding: 8px 18px;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    color: #555;
    border-bottom: 3px solid transparent;
    background: transparent;
  }
  .stTabs [aria-selected="true"] {
    color: #006FCF !important;
    border-bottom: 3px solid #006FCF !important;
    background: transparent !important;
  }
</style>
""", unsafe_allow_html=True)

A  = COLORS["amex"]
R  = COLORS["risk_red"]
G  = COLORS["safe_green"]
W  = COLORS["warn_amber"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/f/fa/American_Express_logo_%282018%29.svg",
             width=140)
    st.markdown("---")
    st.header("Settings")

    default_path = Path(__file__).parent.parent.parent / "f.xlsx"

    # ── Cached loaders ────────────────────────────────────────────────────────
    def _enrich_results(df):
        """Shared post-analysis enrichment (monetary relief trend)."""
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

    @st.cache_data(show_spinner="Loading default dataset…", persist=False)
    def load_default(path_str: str):
        """Keyed on path — loads once, never re-reads disk on UI interactions."""
        return _enrich_results(load_data(Path(path_str)))

    @st.cache_data(show_spinner="Analysing uploaded file…")
    def load_uploaded(file_bytes: bytes, file_name: str):
        """Keyed on file content — recomputes only when a new file is uploaded."""
        tmp = Path("/tmp") / file_name
        tmp.write_bytes(file_bytes)
        return _enrich_results(load_data(tmp))

    # ── Source selection ──────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload new CFPB data (Excel / CSV)",
        type=["xlsx", "xls", "csv"],
        help="Leave empty to use the built-in f.xlsx dataset",
    )

    if uploaded is not None:
        results = load_uploaded(uploaded.read(), uploaded.name)
        st.success(f"Using uploaded file: {uploaded.name}")
    elif default_path.exists():
        results = load_default(str(default_path))
        st.info(f"Using default dataset: f.xlsx")
    else:
        st.error("Default file f.xlsx not found. Please upload a CFPB data file.")
        st.stop()

    recs = build_recommendations(results)

    st.markdown("---")
    st.caption(f"**Dataset:** {results['meta']['total_all']:,} complaints")
    st.caption(f"**Period:** {results['meta']['date_min']} → {results['meta']['date_max']}")
    st.caption(f"**Focus company:** {FOCUS_COMPANY}")

# ── Tab layout ────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "Executive Summary",
    "Industry Landscape",
    "Competitive Position",
    "AMEX Deep Dive",
    "Trends",
    "Geographic Risk",
    "Risk Analysis",
    "Recommendations",
])

sc   = results["scorecard"].set_index("Company_Short")
iavg = results["industry_avg"]
meta = results["meta"]
amex_mr  = sc.loc[FOCUS_COMPANY, "Monetary Relief %"]   if FOCUS_COMPANY in sc.index else 0
amex_ur  = sc.loc[FOCUS_COMPANY, "Untimely Response %"] if FOCUS_COMPANY in sc.index else 0
amex_cnt = sc.loc[FOCUS_COMPANY, "Total Complaints"]    if FOCUS_COMPANY in sc.index else 0

# ════════════════════════════════════════════════════════ TAB 0 — EXEC SUMMARY
with tabs[0]:
    st.title("CFPB Complaint Intelligence Report")
    st.markdown(f"**{FOCUS_COMPANY}** | {meta['date_min']} → {meta['date_max']} | "
                f"{meta['total_all']:,} total complaints | {meta['n_companies']} companies")
    st.markdown("---")

    c1, c2, c3, c4, c5 = st.columns(5)
    rank = results["scorecard"]["Company_Short"].tolist().index(FOCUS_COMPANY)+1 \
           if FOCUS_COMPANY in results["scorecard"]["Company_Short"].values else "N/A"
    c1.metric("AMEX Complaints",         f"{int(amex_cnt):,}", f"{meta['amex_share_pct']:.1f}% of industry")
    c2.metric("Industry Rank",           f"#{rank} of 9",       "by complaint volume")
    c3.metric("Monetary Relief Rate",    f"{amex_mr:.1f}%",     f"Industry avg {iavg['monetary_relief_pct']:.1f}%",
              delta_color="inverse")
    c4.metric("Untimely Response Rate",  f"{amex_ur:.2f}%",     f"Industry avg {iavg['untimely_pct']:.2f}%",
              delta_color="inverse")
    c5.metric("Critical Risks Found",    str(sum(1 for r in recs if "CRITICAL" in r.priority)),
              "from automated scan")

    st.markdown("---")
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.subheader("Monthly Complaint Trend")
        m = results["amex_monthly"]["monthly"]
        mv = results["monthly_volume"]
        fig = go.Figure()
        for co, grp in mv.groupby("Company_Short"):
            if co != FOCUS_COMPANY:
                fig.add_trace(go.Scatter(x=grp["Month_dt"], y=grp["complaints"],
                    name=co, line=dict(color=COMPANY_PALETTE.get(co,"#aaa"), width=1),
                    opacity=0.4, showlegend=True))
        fig.add_trace(go.Scatter(x=m["Month_dt"], y=m["complaints"],
            name=FOCUS_COMPANY, line=dict(color=A, width=3),
            fill="tozeroy", fillcolor="rgba(0,111,207,0.13)", mode="lines+markers",
            marker=dict(size=5)))
        fig.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("AMEX Resolution Breakdown")
        if FOCUS_COMPANY in results["resolution_mix"].index:
            res_row = results["resolution_mix"].loc[FOCUS_COMPANY]
            fig_pie = px.pie(values=res_row.values, names=res_row.index,
                             color_discrete_sequence=["#C62828","#EF9A9A","#CFD8DC","#FFA000","#37474F"],
                             hole=0.4)
            fig_pie.update_layout(height=310, margin=dict(l=0,r=0,t=10,b=0),
                                   showlegend=True, legend=dict(font=dict(size=10)))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.subheader("Top Findings")
    for rec in recs[:4]:
        color_map = {"P1 — CRITICAL":"#FFEBEE","P2 — HIGH":"#FFF3E0",
                     "P3 — MEDIUM":"#FFFDE7","P4 — OPPORTUNITY":"#E8F5E9"}
        border_map = {"P1 — CRITICAL":"#C62828","P2 — HIGH":"#E65100",
                      "P3 — MEDIUM":"#F9A825","P4 — OPPORTUNITY":"#2E7D32"}
        bg = color_map.get(rec.priority,"#f0f0f0")
        bd = border_map.get(rec.priority,"#999")
        st.markdown(f"""
        <div style="background:{bg};border-left:5px solid {bd};border-radius:6px;
                    padding:12px 16px;margin-bottom:8px;">
          <strong style="color:{bd};">{rec.priority} — {rec.area}</strong><br>
          <span style="font-size:13px;color:#333;">{rec.finding}</span>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════ TAB 1 — INDUSTRY LANDSCAPE
with tabs[1]:
    st.header("Industry Landscape")
    col1, col2 = st.columns(2)
    sc_plot = results["scorecard"].sort_values("Total Complaints", ascending=True)

    with col1:
        st.subheader("Complaint Volume by Company")
        fig = px.bar(sc_plot, x="Total Complaints", y="Company_Short", orientation="h",
                     color="Company_Short",
                     color_discrete_map=COMPANY_PALETTE,
                     text="Total Complaints")
        fig.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig.update_layout(showlegend=False, height=400, margin=dict(l=0,r=0,t=10,b=0),
                          yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Industry Complaint Share (%)")
        sc_pct = sc_plot.copy()
        sc_pct["share"] = sc_pct["Total Complaints"] / sc_pct["Total Complaints"].sum() * 100
        fig = px.bar(sc_pct, x="share", y="Company_Short", orientation="h",
                     color="Company_Short", color_discrete_map=COMPANY_PALETTE,
                     text=sc_pct["share"].round(1).astype(str)+"%")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=400, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis_title="% of Complaints", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Monthly Complaint Trends — All Companies")
    mv = results["monthly_volume"]
    fig = px.line(mv, x="Month_dt", y="complaints", color="Company_Short",
                  color_discrete_map=COMPANY_PALETTE, markers=False)
    for trace in fig.data:
        if trace.name == FOCUS_COMPANY:
            trace.line.width = 4
        else:
            trace.line.width = 1.2
            trace.opacity = 0.6
    fig.update_layout(height=380, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      margin=dict(l=0,r=0,t=30,b=0), xaxis_title="Month", yaxis_title="Complaints")
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════ TAB 2 — COMPETITIVE POSITION
with tabs[2]:
    st.header("Competitive Position")
    st.subheader("Competitive Scorecard")

    def style_scorecard(df):
        styled = df.copy()
        styled["Total Complaints"] = styled["Total Complaints"].apply(lambda x: f"{x:,}")
        for col in ["Monetary Relief %","Non-Monetary Relief %","Untimely Response %","Explanation Only %"]:
            styled[col] = styled[col].apply(lambda x: f"{x:.2f}%")
        return styled

    sc_display = results["scorecard"].copy()
    avg_row = pd.DataFrame([{
        "Company_Short": "Industry Average",
        "Total Complaints": int(sc_display["Total Complaints"].mean()),
        "Monetary Relief %": round(iavg["monetary_relief_pct"],1),
        "Non-Monetary Relief %": round(iavg["non_monetary_pct"],1),
        "Untimely Response %": round(iavg["untimely_pct"],2),
        "Explanation Only %": round(iavg["explanation_pct"],1),
    }])
    sc_display = pd.concat([sc_display, avg_row], ignore_index=True)
    st.dataframe(style_scorecard(sc_display).rename(columns={"Company_Short":"Company"}),
                 use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monetary Relief Rate (%)")
        mr = results["scorecard"].sort_values("Monetary Relief %")
        fig = px.bar(mr, x="Monetary Relief %", y="Company_Short", orientation="h",
                     color="Company_Short", color_discrete_map=COMPANY_PALETTE,
                     text=mr["Monetary Relief %"].apply(lambda x: f"{x:.1f}%"))
        fig.add_vline(x=iavg["monetary_relief_pct"], line_dash="dash", line_color="red",
                      annotation_text=f"Avg: {iavg['monetary_relief_pct']:.1f}%")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=380, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Untimely Response Rate (%)")
        ur = results["scorecard"].sort_values("Untimely Response %")
        fig = px.bar(ur, x="Untimely Response %", y="Company_Short", orientation="h",
                     color="Company_Short", color_discrete_map=COMPANY_PALETTE,
                     text=ur["Untimely Response %"].apply(lambda x: f"{x:.2f}%"))
        fig.add_vline(x=iavg["untimely_pct"], line_dash="dash", line_color="red",
                      annotation_text=f"Avg: {iavg['untimely_pct']:.2f}%")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=380, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Resolution Type Mix (100% stacked)")
    rm = results["resolution_mix"].reset_index()
    rm_long = rm.melt(id_vars="Company_Short", var_name="Resolution", value_name="Pct")
    col_order = ["Closed with monetary relief","Closed with non-monetary relief",
                 "Closed with explanation","In progress","Untimely response"]
    rm_long = rm_long[rm_long["Resolution"].isin(col_order)]
    fig = px.bar(rm_long, x="Company_Short", y="Pct", color="Resolution",
                 color_discrete_sequence=["#C62828","#EF9A9A","#CFD8DC","#FFA000","#37474F"],
                 text=rm_long["Pct"].apply(lambda x: f"{x:.0f}%" if x > 5 else ""))
    fig.update_traces(textposition="inside", textfont_color="white")
    fig.update_layout(height=420, barmode="stack", yaxis_title="% of Complaints",
                      xaxis_title="", legend_title="Resolution Type",
                      margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════ TAB 3 — AMEX DEEP DIVE
with tabs[3]:
    st.header(f"{FOCUS_COMPANY} Deep Dive")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Product Mix — AMEX vs Industry")
        cmp = results["product_cmp"].reset_index()
        cmp_long = cmp.melt(id_vars="Product", value_vars=["AMEX","Industry"],
                             var_name="Source", value_name="Pct")
        fig = px.bar(cmp_long, x="Pct", y="Product", color="Source", barmode="group",
                     orientation="h",
                     color_discrete_map={"AMEX": A, "Industry": "#B0BEC5"},
                     text=cmp_long["Pct"].apply(lambda x: f"{x:.1f}%"))
        fig.update_traces(textposition="outside")
        fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis_title="% of Complaints", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("AMEX Over/Under-Indexed Issues")
        cmp_i = results["issue_cmp"].reset_index().sort_values("diff")
        fig = px.bar(cmp_i, x="diff", y="Issue", orientation="h",
                     color="diff", color_continuous_scale=["#2E7D32","#eeeeee","#C62828"],
                     color_continuous_midpoint=0,
                     text=cmp_i["diff"].apply(lambda x: f"{x:+.1f}pp"))
        fig.add_vline(x=0, line_color="black", line_width=1)
        fig.update_traces(textposition="outside")
        fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis_title="Percentage Point Difference", yaxis_title="",
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Monthly Issue Heatmap")
    pivot = results["issue_heatmap"]
    fig = px.imshow(pivot.T.values,
                    x=[str(p) for p in pivot.index],
                    y=pivot.columns.tolist(),
                    color_continuous_scale="YlOrRd",
                    text_auto=True, aspect="auto")
    fig.update_layout(height=400, margin=dict(l=0,r=0,t=10,b=0),
                      xaxis_tickangle=-40, coloraxis_colorbar_title="Complaints")
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════ TAB 4 — TRENDS
with tabs[4]:
    st.header("Trend Analysis")

    m = results["amex_monthly"]["monthly"]
    q = results["amex_monthly"]["quarterly"]

    st.subheader(f"{FOCUS_COMPANY} Monthly Complaint Volume with 3-Month Rolling Average")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=m["Month_dt"], y=m["complaints"], name="Monthly",
                             line=dict(color=A, width=1.5), mode="lines+markers",
                             marker=dict(size=5), fill="tozeroy", fillcolor="rgba(0,111,207,0.13)"))
    fig.add_trace(go.Scatter(x=m["Month_dt"], y=m["rolling_3m"], name="3M Rolling Avg",
                             line=dict(color=A, width=3, dash="solid")))
    fig.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                      yaxis_title="Complaints", xaxis_title="Month")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Quarter-over-Quarter Change (%)")
        colors = [G if v < 0 else R for v in q["qoq_pct"].fillna(0)]
        fig = go.Figure(go.Bar(x=q["Quarter"].astype(str), y=q["qoq_pct"].fillna(0),
                               marker_color=colors, text=q["qoq_pct"].fillna(0).apply(lambda x: f"{x:+.1f}%"),
                               textposition="outside"))
        fig.add_hline(y=0, line_color="black")
        fig.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                          yaxis_title="QoQ Change (%)", xaxis_title="Quarter")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"{FOCUS_COMPANY} Share of Industry Complaints")
        s = results["share_trend"]
        avg = s["share_pct"].mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s["Month_dt"], y=s["share_pct"], name="Monthly Share",
                                 line=dict(color=A, width=1.5), fill="tozeroy", fillcolor="rgba(0,111,207,0.13)"))
        fig.add_trace(go.Scatter(x=s["Month_dt"], y=s["rolling_share"], name="3M Rolling",
                                 line=dict(color=A, width=3)))
        fig.add_hline(y=avg, line_dash="dash", line_color=W,
                      annotation_text=f"Avg {avg:.1f}%")
        fig.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                          yaxis_title="% Share", xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Issue Growth: H1 2025 vs H2 2025")
    ig = results["issue_growth"].reset_index()
    ig_sorted = ig.sort_values("growth_pct", ascending=True)
    fig = px.bar(ig_sorted, x="growth_pct", y="Issue", orientation="h",
                 color="growth_pct",
                 color_continuous_scale=["#2E7D32","#eeeeee","#C62828"],
                 color_continuous_midpoint=0,
                 text=ig_sorted["growth_pct"].apply(lambda x: f"{x:+.0f}%"),
                 hover_data=["H1_2025","H2_2025"])
    fig.add_vline(x=0, line_color="black", line_width=1)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=500, margin=dict(l=0,r=0,t=10,b=0),
                      xaxis_title="% Change H1→H2 2025", yaxis_title="",
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════ TAB 5 — GEOGRAPHIC RISK
with tabs[5]:
    st.header("Geographic Risk Profile")
    geo = results["geo_cmp"].reset_index()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top States — AMEX vs Industry (%)")
        geo_long = geo.head(12).melt(id_vars="State", value_vars=["AMEX","Industry"],
                                      var_name="Source", value_name="Pct")
        fig = px.bar(geo_long, x="Pct", y="State", color="Source", barmode="group",
                     orientation="h",
                     color_discrete_map={"AMEX": A, "Industry": "#B0BEC5"},
                     text=geo_long["Pct"].apply(lambda x: f"{x:.1f}%"))
        fig.update_traces(textposition="outside")
        fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis_title="% of Complaints", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("AMEX Geographic Over/Under-Index")
        diff_sorted = geo.sort_values("diff", ascending=True).head(12)
        fig = px.bar(diff_sorted, x="diff", y="State", orientation="h",
                     color="diff",
                     color_continuous_scale=["#2E7D32","#eeeeee","#C62828"],
                     color_continuous_midpoint=0,
                     text=diff_sorted["diff"].apply(lambda x: f"{x:+.1f}pp"))
        fig.add_vline(x=0, line_color="black", line_width=1)
        fig.update_traces(textposition="outside")
        fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis_title="pp vs Industry", yaxis_title="",
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("US State Complaint Share — AMEX (bubble map)")
    state_counts = geo.set_index("State")["AMEX"].reset_index()
    fig = px.choropleth(state_counts, locations="State", locationmode="USA-states",
                        color="AMEX", scope="usa",
                        color_continuous_scale=["#EBF5FB","#006FCF"],
                        labels={"AMEX":"% of AMEX Complaints"})
    fig.update_layout(height=380, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════ TAB 6 — RISK ANALYSIS
with tabs[6]:
    st.header("Risk Analysis")

    st.subheader("Risk Matrix — Complaint Frequency vs Financial Impact")
    rm = results["risk_matrix"]
    fig = px.scatter(rm, x="count", y="monetary_pct", size="count", color="monetary_pct",
                     text=rm["Issue"].str[:35],
                     color_continuous_scale=["#2E7D32","#FFEB3B","#C62828"],
                     size_max=60, hover_data=["Issue","count","monetary_pct"],
                     labels={"count":"Complaint Count","monetary_pct":"Monetary Relief Rate (%)"})
    fig.add_vline(x=rm["count"].median(), line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=rm["monetary_pct"].median(), line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_traces(textposition="top right", textfont_size=9)
    fig.update_layout(height=550, coloraxis_colorbar_title="Monetary %",
                      margin=dict(l=0,r=0,t=10,b=0))
    xl = [rm["count"].min()*0.9, rm["count"].max()*1.1]
    yl = [0, rm["monetary_pct"].max()*1.1]
    fig.add_annotation(x=xl[1], y=yl[1], text="HIGH FREQ / HIGH COST",
                       showarrow=False, font=dict(color=R, size=11))
    fig.add_annotation(x=xl[0], y=yl[1], text="LOW FREQ / HIGH COST",
                       showarrow=False, font=dict(color=W, size=11), xanchor="left")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monetary Relief Rate Trend")
        mr_trend = results.get("amex_mr_trend")
        if mr_trend is not None:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=mr_trend["Month_dt"], y=mr_trend["amex_mr"],
                                     name=FOCUS_COMPANY, line=dict(color=R, width=2.5),
                                     mode="lines+markers", marker=dict(size=5)))
            fig.add_trace(go.Scatter(x=mr_trend["Month_dt"], y=mr_trend["ind_mr"],
                                     name="Industry Avg", line=dict(color="#888888", width=2, dash="dash")))
            fig.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                              yaxis_title="% Monetary Relief", xaxis_title="Month",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Risk Register")
        risk_register = pd.DataFrame([{
            "Risk Area":   rec.area,
            "Priority":    rec.priority,
            "Finding":     rec.finding[:90]+"…" if len(rec.finding) > 90 else rec.finding,
        } for rec in recs])
        st.dataframe(risk_register, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════ TAB 7 — RECOMMENDATIONS
with tabs[7]:
    st.header("Recommendations")
    st.markdown(f"**{len(recs)} recommendations** auto-generated from data analysis · "
                f"{sum(1 for r in recs if 'CRITICAL' in r.priority)} critical · "
                f"{sum(1 for r in recs if 'HIGH' in r.priority)} high · "
                f"{sum(1 for r in recs if 'MEDIUM' in r.priority)} medium · "
                f"{sum(1 for r in recs if 'OPPORTUNITY' in r.priority)} opportunities")
    st.markdown("---")

    color_map = {
        "P1 — CRITICAL":    ("#FFEBEE","#C62828"),
        "P2 — HIGH":        ("#FFF3E0","#E65100"),
        "P3 — MEDIUM":      ("#FFFDE7","#F9A825"),
        "P4 — OPPORTUNITY": ("#E8F5E9","#2E7D32"),
    }

    filter_priority = st.multiselect(
        "Filter by priority",
        options=["P1 — CRITICAL","P2 — HIGH","P3 — MEDIUM","P4 — OPPORTUNITY"],
        default=["P1 — CRITICAL","P2 — HIGH","P3 — MEDIUM","P4 — OPPORTUNITY"])

    for rec in recs:
        if rec.priority not in filter_priority:
            continue
        bg, bd = color_map.get(rec.priority, ("#f0f0f0","#666"))
        with st.container():
            st.markdown(f"""
            <div style="background:{bg};border-left:5px solid {bd};border-radius:6px;
                        padding:14px 18px;margin-bottom:12px;">
              <div style="font-weight:800;color:{bd};font-size:14px;margin-bottom:6px;">
                {rec.priority} &nbsp;|&nbsp; {rec.area}</div>
              <div style="margin-bottom:8px;">
                <strong>Finding:</strong> {rec.finding}</div>
              <div style="margin-bottom:8px;font-style:italic;color:#555;">
                <strong>Actions:</strong><br>{rec.action.replace(chr(10),"<br>")}</div>
              <div style="font-weight:700;color:{bd};">
                KPI: {rec.kpi}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Export Recommendations as CSV")
    rec_df = pd.DataFrame([{
        "Priority": r.priority, "Area": r.area,
        "Finding": r.finding, "Action": r.action, "KPI Target": r.kpi
    } for r in recs])
    st.download_button("Download Recommendations CSV",
                       rec_df.to_csv(index=False).encode(),
                       "amex_recommendations.csv", "text/csv")
