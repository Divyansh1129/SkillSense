"""Central configuration (environment driven). No secrets are hard-coded; dev keys are defaults only."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("SKILLSENSE_DATA", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SNAP_DIR = DATA_DIR / "snapshots"
DB_PATH = Path(os.getenv("SKILLSENSE_DB", DATA_DIR / "skillsense.db"))

API_KEYS = {
    os.getenv("API_KEY_VIEWER", "dev-viewer-key"): "viewer",
    os.getenv("API_KEY_ANALYST", "dev-analyst-key"): "analyst",
    os.getenv("API_KEY_ADMIN", "dev-admin-key"): "admin",
}
DEMO_DATA = os.getenv("DEMO_DATA", "1") == "1"
USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "0") == "1"
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

DATA_START = "2023-10"   # 36 months: 2023-10 .. 2026-09
N_MONTHS = 36

DEFAULT_WEIGHTS = {"postings": 0.35, "hiring": 0.25, "plfs": 0.25, "eshram": 0.15}
WEIGHT_RATIONALE = {
    "postings": "Most timely and granular (weekly, district level) but noisy, urban-skewed and duplicate-prone.",
    "hiring": "Direct employer intent, sector-level reliability; moderate freshness.",
    "plfs": "Statistically sound survey-based employment level, but quarterly and slow-moving.",
    "eshram": "Large coverage of informal workers; self-reported, so used as a weaker demand proxy.",
}
DEFAULT_THRESHOLDS = {
    "shortage_watch": 0.15, "shortage_warning": 0.25, "shortage_critical": 0.45,
    "oversupply_watch": 0.15, "oversupply_warning": 0.25, "oversupply_critical": 0.45,
    "saturation_demand_growth_max": 0.05,
    "emerging_growth_min": 0.20, "emerging_growth_critical": 0.40, "emerging_supply_ratio_max": 0.90,
    "low_conf_watch": 0.70, "low_conf_warning": 0.50,
    "carryover_retention": 0.50, "mapping_threshold": 0.72, "near_dup_cutoff": 92.0,
    "max_change_pct": 0.50,
}
