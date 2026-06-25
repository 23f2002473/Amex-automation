"""
Rule-based recommendation engine.
Reads analysis results and applies threshold rules to produce a
structured list of findings, risks, and prioritised recommendations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .config import THRESHOLDS, FOCUS_COMPANY


@dataclass
class Recommendation:
    priority:   str          # P1-CRITICAL / P2-HIGH / P3-MEDIUM / P4-OPPORTUNITY
    area:       str
    finding:    str
    action:     str
    kpi:        str
    color:      str = "#grey"
    border:     str = "#333"
    evidence:   dict = field(default_factory=dict)  # raw numbers that triggered this


def build_recommendations(results: dict) -> list[Recommendation]:
    """
    Apply threshold rules to analysis results and return a prioritised
    list of Recommendation objects.
    """
    recs: list[Recommendation] = []
    sc   = results["scorecard"].set_index("Company_Short")
    iavg = results["industry_avg"]
    rm   = results["risk_matrix"]
    ig   = results["issue_growth"]
    meta = results["meta"]

    amex_mr  = sc.loc[FOCUS_COMPANY, "Monetary Relief %"]   if FOCUS_COMPANY in sc.index else 0.0
    amex_ur  = sc.loc[FOCUS_COMPANY, "Untimely Response %"] if FOCUS_COMPANY in sc.index else 0.0
    amex_cnt = sc.loc[FOCUS_COMPANY, "Total Complaints"]    if FOCUS_COMPANY in sc.index else 0

    # ── P1: Untimely response (regulatory compliance) ────────────────────────
    if amex_ur > THRESHOLDS["untimely_critical"]:
        recs.append(Recommendation(
            priority="P1 — CRITICAL",
            area="CFPB Response Timeliness",
            finding=(f"{FOCUS_COMPANY}'s untimely response rate is {amex_ur:.2f}% — "
                     f"{amex_ur / iavg['untimely_pct']:.1f}× the industry average "
                     f"({iavg['untimely_pct']:.2f}%). This is a regulatory compliance failure."),
            action=("1. Audit the CFPB complaint intake and routing workflow immediately.\n"
                    "2. Implement automated SLA alerts at 10 days (warning) and 13 days (critical).\n"
                    "3. Assign a dedicated CFPB compliance owner with escalation authority.\n"
                    "4. Benchmark against zero-untimely peers (JPMorgan Chase, Citibank)."),
            kpi=f"Target: untimely rate < {THRESHOLDS['untimely_high']:.2f}% within 60 days; "
                f"at or below industry average ({iavg['untimely_pct']:.2f}%) within 2 quarters.",
            color="#FFEBEE", border="#C62828",
            evidence={"amex_ur": amex_ur, "industry_avg_ur": iavg["untimely_pct"]},
        ))

    # ── P1: Purchase dispute volume & cost ───────────────────────────────────
    purchase_row = rm[rm["Issue"].str.contains("purchase", case=False, na=False)]
    if not purchase_row.empty:
        row = purchase_row.iloc[0]
        recs.append(Recommendation(
            priority="P1 — CRITICAL",
            area="Purchase Dispute Resolution",
            finding=(f'"Problem with a purchase shown on your statement" is {FOCUS_COMPANY}\'s '
                     f'#1 complaint ({int(row["count"]):,} complaints) with a '
                     f'{row["monetary_pct"]:.1f}% monetary relief rate — high frequency AND high cost.'),
            action=("1. End-to-end audit of the dispute resolution workflow.\n"
                    "2. Deploy AI-assisted triage to accelerate simple vs complex dispute routing.\n"
                    "3. Proactive status updates at 48h, 7d, and 14d for all open disputes.\n"
                    "4. Review first-contact resolution rate — high reopens signal inconsistent decisions."),
            kpi="Target: 20% reduction in dispute-related CFPB complaints within 2 quarters.",
            color="#FFEBEE", border="#C62828",
            evidence={"count": int(row["count"]), "monetary_pct": row["monetary_pct"]},
        ))

    # ── P1 / P2: Monetary relief rate vs industry ────────────────────────────
    if amex_mr > THRESHOLDS["monetary_relief_high"]:
        severity = "P1 — CRITICAL" if amex_mr > 15 else "P2 — HIGH"
        recs.append(Recommendation(
            priority=severity,
            area="Monetary Relief Exposure",
            finding=(f"{FOCUS_COMPANY}'s monetary relief rate ({amex_mr:.1f}%) is above the "
                     f"industry average ({iavg['monetary_relief_pct']:.1f}%). "
                     f"~{int(amex_cnt * amex_mr / 100):,} complaints required financial remediation."),
            action=("1. Root-cause analysis on the top 3 issue types driving monetary relief.\n"
                    "2. Implement upstream process fixes to prevent escalation to formal complaints.\n"
                    "3. Track monetary relief rate as a monthly executive KPI alongside complaint volume."),
            kpi=(f"Target: monetary relief rate at or below industry average "
                 f"({iavg['monetary_relief_pct']:.1f}%) within 3 quarters."),
            color="#FFEBEE" if severity.startswith("P1") else "#FFF3E0",
            border="#C62828" if severity.startswith("P1") else "#E65100",
            evidence={"amex_mr": amex_mr, "industry_avg_mr": iavg["monetary_relief_pct"]},
        ))

    # ── P2: Application friction ("Getting a credit card") ───────────────────
    issue_cmp = results["issue_cmp"]
    app_row = issue_cmp[issue_cmp.index.str.contains("Getting a credit card", case=False, na=False)]
    if not app_row.empty and app_row.iloc[0]["diff"] > 1.0:
        diff = app_row.iloc[0]["diff"]
        recs.append(Recommendation(
            priority="P2 — HIGH",
            area="Credit Card Application Friction",
            finding=(f'"Getting a credit card" is over-indexed for {FOCUS_COMPANY} vs industry '
                     f'by +{diff:.1f}pp, signalling disproportionate friction in the '
                     f'application and onboarding funnel.'),
            action=("1. Simplify digital application flows — reduce document re-request loops.\n"
                    "2. Redesign decline communications with specific, actionable reason codes.\n"
                    "3. A/B test streamlined journeys for Platinum and Gold product lines."),
            kpi="Target: 15% reduction in application-stage CFPB complaints within 1 quarter.",
            color="#FFF3E0", border="#E65100",
            evidence={"over_index_pp": diff},
        ))

    # ── P2: Fees / interest ───────────────────────────────────────────────────
    fee_row = rm[rm["Issue"].str.contains("Fees or interest", case=False, na=False)]
    if not fee_row.empty and fee_row.iloc[0]["monetary_pct"] > 20:
        row = fee_row.iloc[0]
        recs.append(Recommendation(
            priority="P2 — HIGH",
            area="Fees & Interest Transparency",
            finding=(f'"Fees or interest" complaints ({int(row["count"]):,}) carry a '
                     f'{row["monetary_pct"]:.1f}% monetary relief rate — persistent billing '
                     f'surprise is driving financial remediation.'),
            action=("1. Proactive in-app fee alerts 5 business days before billing.\n"
                    "2. Plain-language annual fee renewal communications.\n"
                    "3. Reduce friction for self-serve fee inquiry deflection."),
            kpi="Target: 10% reduction in fee-related complaints + increase in self-serve resolution.",
            color="#FFF3E0", border="#E65100",
            evidence={"count": int(row["count"]), "monetary_pct": row["monetary_pct"]},
        ))

    # ── P2: Trouble using card (highest unit cost) ────────────────────────────
    card_row = rm[rm["Issue"].str.contains("Trouble using", case=False, na=False)]
    if not card_row.empty and card_row.iloc[0]["monetary_pct"] > 35:
        row = card_row.iloc[0]
        recs.append(Recommendation(
            priority="P2 — HIGH",
            area="Card Functionality — High Unit Cost",
            finding=(f'"Trouble using the card" has the highest monetary relief rate '
                     f'({row["monetary_pct"]:.1f}%) in {FOCUS_COMPANY}\'s portfolio. '
                     f'Nearly half of these complaints require financial remediation.'),
            action=("1. Deep-dive into card decline and card acceptance failure root causes.\n"
                    "2. Identify whether issues are merchant-side, network-side, or AMEX-side.\n"
                    "3. Reduce unnecessary card declines through fraud-model calibration review."),
            kpi="Target: monetary relief rate for this category below 30% within 2 quarters.",
            color="#FFF3E0", border="#E65100",
            evidence={"count": int(row["count"]), "monetary_pct": row["monetary_pct"]},
        ))

    # ── P3: Fastest-growing issues ────────────────────────────────────────────
    fast_growing = ig[ig["growth_pct"] > THRESHOLDS["issue_growth_high"]].head(3)
    for issue, row in fast_growing.iterrows():
        recs.append(Recommendation(
            priority="P3 — MEDIUM",
            area=f"Emerging Risk: {issue[:55]}",
            finding=(f'This issue grew {row["growth_pct"]:+.0f}% from H1 to H2 2025 '
                     f'({int(row["H1_2025"]):,} → {int(row["H2_2025"]):,} complaints). '
                     f'Accelerating trends become next quarter\'s top issues if unaddressed.'),
            action=("1. Investigate root cause of the growth spike.\n"
                    "2. Set a monthly monitoring alert for this issue category.\n"
                    "3. Assign an owner to track and report back within 30 days."),
            kpi=f"Target: growth rate below {THRESHOLDS['issue_growth_medium']:.0f}% QoQ within 2 quarters.",
            color="#FFFDE7", border="#F9A825",
            evidence={"h1": int(row["H1_2025"]), "h2": int(row["H2_2025"]),
                      "growth_pct": row["growth_pct"]},
        ))

    # ── P3: Geographic concentration ─────────────────────────────────────────
    geo = results["geo_cmp"]
    top_state = geo.index[0] if not geo.empty else "CA"
    top_pct   = geo["AMEX"].iloc[0] if not geo.empty else 0
    if top_pct > 18:
        recs.append(Recommendation(
            priority="P3 — MEDIUM",
            area="Geographic Concentration Risk",
            finding=(f"{top_state} accounts for ~{top_pct:.1f}% of {FOCUS_COMPANY} complaints. "
                     f"CA, TX, and FL together likely exceed 40% — all have active state-level "
                     f"consumer financial protection frameworks."),
            action=("1. Establish state-level complaint monitoring with alert thresholds.\n"
                    "2. Deploy regional compliance task forces for top 3 states.\n"
                    "3. Monitor CA DFPI, TX OCC, FL OFR for new enforcement signals."),
            kpi="Target: no single state exceeds 25% of total AMEX CFPB complaints.",
            color="#FFFDE7", border="#F9A825",
            evidence={"top_state": top_state, "top_pct": top_pct},
        ))

    # ── P4: Opportunity — brand differentiator ────────────────────────────────
    rank = (results["scorecard"]["Company_Short"]
            .tolist().index(FOCUS_COMPANY) + 1
            if FOCUS_COMPANY in results["scorecard"]["Company_Short"].values else "N/A")
    recs.append(Recommendation(
        priority="P4 — OPPORTUNITY",
        area="Compliance Strength as Brand Differentiator",
        finding=(f"{FOCUS_COMPANY} ranks #{rank} lowest in complaint volume among the top-9 peers. "
                 f"This low-complaint profile is a marketable differentiator in the premium segment."),
        action=("1. Develop a 'trust and transparency' narrative for premium card acquisition.\n"
                "2. Tie complaint KPIs to NPS and premium card retention programs.\n"
                "3. Publish an annual Consumer Service Report to externalise the advantage."),
        kpi="Opportunity: measurable acquisition lift and NPS improvement within 3 quarters.",
        color="#E8F5E9", border="#2E7D32",
        evidence={"rank": rank, "amex_count": int(amex_cnt)},
    ))

    return recs
