"""
cfpb_intelligence — CFPB Complaint Intelligence Module
Drop in any CFPB-format Excel/CSV file and get a full analysis, charts, and report.
"""
from .loader import load_data
from .analysis import run_analysis
from .charts import generate_all_charts
from .recommendations import build_recommendations

__all__ = ["load_data", "run_analysis", "generate_all_charts", "build_recommendations"]
__version__ = "1.0.0"
