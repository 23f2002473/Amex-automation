"""
Central configuration — change labels, thresholds, or colors here without
touching any analytical code.
"""

# ── Company label mapping ─────────────────────────────────────────────────────
COMPANY_LABELS: dict[str, str] = {
    "CAPITAL ONE FINANCIAL CORPORATION":     "Capital One",
    "JPMORGAN CHASE & CO.":                  "JPMorgan Chase",
    "CITIBANK, N.A.":                        "Citibank",
    "WELLS FARGO & COMPANY":                 "Wells Fargo",
    "BANK OF AMERICA, NATIONAL ASSOCIATION": "Bank of America",
    "SYNCHRONY FINANCIAL":                   "Synchrony",
    "AMERICAN EXPRESS COMPANY":              "American Express",
    "U.S. BANCORP":                          "U.S. Bancorp",
    "BARCLAYS BANK DELAWARE":                "Barclays",
}

# Primary company being analysed
FOCUS_COMPANY = "American Express"

# ── Resolution types ──────────────────────────────────────────────────────────
RESOLUTION_TYPES = [
    "Closed with monetary relief",
    "Closed with non-monetary relief",
    "Closed with explanation",
    "In progress",
    "Untimely response",
]

# ── Risk thresholds (used by the recommendation engine) ──────────────────────
THRESHOLDS = {
    # Monetary relief rate above this → HIGH risk flag
    "monetary_relief_high":   12.0,   # %
    "monetary_relief_medium":  8.0,   # %
    # Untimely response rate above this → CRITICAL flag
    "untimely_critical":       0.50,  # %
    "untimely_high":           0.20,  # %
    # Issue growth rate (H2 vs H1) above this → emerging risk
    "issue_growth_high":      25.0,   # %
    "issue_growth_medium":    10.0,   # %
    # Minimum complaint count to include an issue in risk analysis
    "min_issue_count":         50,
}

# ── Colours ───────────────────────────────────────────────────────────────────
COLORS = {
    "amex":        "#006FCF",
    "peer":        "#B0BEC5",
    "risk_red":    "#C62828",
    "safe_green":  "#2E7D32",
    "warn_amber":  "#F57F17",
    "background":  "#F7F9FC",
}

COMPANY_PALETTE: dict[str, str] = {
    "American Express": "#006FCF",
    "Capital One":      "#E53935",
    "JPMorgan Chase":   "#43A047",
    "Citibank":         "#FB8C00",
    "Wells Fargo":      "#8E24AA",
    "Bank of America":  "#00ACC1",
    "Synchrony":        "#795548",
    "U.S. Bancorp":     "#3949AB",
    "Barclays":         "#00897B",
}

# Short labels for the issue heatmap
ISSUE_SHORT_LABELS: dict[str, str] = {
    "Problem with a purchase shown on your statement":                   "Purchase dispute",
    "Other features, terms, or problems":                                "Other features/terms",
    "Getting a credit card":                                             "Getting a credit card",
    "Fees or interest":                                                  "Fees or interest",
    "Closing your account":                                              "Closing account",
    "Incorrect information on your report":                              "Incorrect credit report",
    "Managing an account":                                               "Managing account",
    "Improper use of your report":                                       "Improper report use",
    "Problem with a company's investigation into an existing problem":   "Investigation problem",
    "Attempts to collect debt not owed":                                 "Debt collection",
    "Trouble using the card":                                            "Trouble using card",
    "Advertising and marketing, including promotional offers":           "Advertising/marketing",
}
