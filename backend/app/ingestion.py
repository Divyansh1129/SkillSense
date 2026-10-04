"""Module 1 - ingestion: one connector per source (common interface), schema validation (Pandera), rejected-rows report,
deduplication (exact hash + near-duplicate similarity) and per-source freshness/completeness metrics.

Every connector here is a SIMULATED implementation that reads generated files from data/raw/.
To plug in a real feed, subclass the connector and override `fetch()` (see docs/INTEGRATION.md and the stubs below).
"""
import shutil
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from .config import DATA_START, N_MONTHS, RAW_DIR, SNAP_DIR
from .mapping import HAVE_RF, normalise_district, normalise_text
from .taxonomy import DISTRICTS, TRADES

try:
    try:
        import pandera.pandas as pa
    except ImportError:
        import pandera as pa
except ImportError:  # pragma: no cover
    pa = None

if HAVE_RF:
    from rapidfuzz import fuzz, process

D_CODES = [d[0] for d in DISTRICTS]
T_CODES = [t[0] for t in TRADES]
MONTHS = [str(p) for p in pd.period_range(DATA_START, periods=N_MONTHS, freq="M")]


def _schemas():
    if pa is None:
        return {}
    C = pa.Column
    return {
        "postings": pa.DataFrameSchema({
            "title": C(str, pa.Check.str_length(min_value=2)),
            "employer": C(str, nullable=True),
            "district_raw": C(str, pa.Check.str_length(min_value=2)),
            "portal": C(str, nullable=True),
            "posted_date": C("datetime64[ns]", coerce=True)}, coerce=True),
        "hiring": pa.DataFrameSchema({
            "month": C(str, pa.Check.isin(MONTHS)), "district_code": C(str, pa.Check.isin(D_CODES)),
            "trade_code": C(str, pa.Check.isin(T_CODES)), "hiring_index": C(float, pa.Check.ge(0), coerce=True)}, coerce=True),
        "plfs": pa.DataFrameSchema({
            "month": C(str, pa.Check.isin(MONTHS)), "district_code": C(str, pa.Check.isin(D_CODES)),
            "trade_code": C(str, pa.Check.isin(T_CODES)), "employment_level": C(float, pa.Check.ge(0), coerce=True)}, coerce=True),
        "eshram": pa.DataFrameSchema({
            "month": C(str, pa.Check.isin(MONTHS)), "district_code": C(str, pa.Check.isin(D_CODES)),
            "trade_code": C(str, pa.Check.isin(T_CODES)), "registrations": C(float, pa.Check.ge(0), coerce=True)}, coerce=True),
        "seats": pa.DataFrameSchema({
            "cycle": C(int, coerce=True), "centre_id": C(str), "district_code": C(str, pa.Check.isin(D_CODES)),
            "trade_code": C(str, pa.Check.isin(T_CODES)), "seats": C(int, pa.Check.ge(0), coerce=True),
            "enrolment_rate": C(float, pa.Check.in_range(0, 1)), "completion_rate": C(float, pa.Check.in_range(0, 1)),
            "placement_ready_rate": C(float, pa.Check.in_range(0, 1))}, coerce=True),
    }


SCHEMAS = _schemas()


def _manual_validate(df: pd.DataFrame, key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fallback validator (same rules as the Pandera schemas) used when Pandera is missing or incompatible."""
    df = df.copy()
    bad = pd.Series("", index=df.index)

    def flag(mask, why):
        nonlocal bad
        bad = bad.where(~mask, bad + why + ";")
    if key == "postings":
        df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce")
        flag(df["title"].fillna("").astype(str).str.strip().str.len() < 2, "title:too_short")
        flag(df["district_raw"].fillna("").astype(str).str.strip().str.len() < 2, "district_raw:empty")
        flag(df["posted_date"].isna(), "posted_date:unparseable")
    else:
        flag(~df["district_code"].isin(D_CODES), "district_code:unknown")
        flag(~df["trade_code"].isin(T_CODES), "trade_code:unknown")
        if key != "seats":
            flag(~df["month"].isin(MONTHS), "month:out_of_range")
        for col in {"hiring": ["hiring_index"], "plfs": ["employment_level"], "eshram": ["registrations"],
                    "seats": ["seats", "enrolment_rate", "completion_rate", "placement_ready_rate"]}[key]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            flag(df[col].isna() | (df[col] < 0), f"{col}:invalid")
    rejected = df[bad != ""].assign(reason=bad[bad != ""])
    return df[bad == ""], rejected


def validate(df: pd.DataFrame, key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate against the Pandera schema. Returns (clean, rejected-with-reason)."""
    schema = SCHEMAS.get(key)
    if schema is None:
        return _manual_validate(df, key)
    try:
        return schema.validate(df, lazy=True), df.iloc[0:0].assign(reason=[])
    except pa.errors.SchemaErrors as e:
        fc = e.failure_cases.dropna(subset=["index"]).copy()
        fc["index"] = fc["index"].astype(int)
        reasons = fc.groupby("index").apply(lambda g: "; ".join(sorted({f"{c}:{k}" for c, k in zip(g["column"], g["check"])})), include_groups=False)
        rejected = df.loc[df.index.isin(reasons.index)].copy()
        rejected["reason"] = reasons.reindex(rejected.index).values
        clean = schema.validate(df.drop(index=rejected.index))
        return clean, rejected
    except Exception:  # Pandera/pandas version mismatch -> equivalent manual rules
        return _manual_validate(df, key)


class BaseConnector(ABC):
    """Common connector interface: fetch() -> DataFrame, schema, source_meta()."""
    name = "base"
    filename = ""
    schema_key = ""
    description = ""
    real_feed = ""

    @property
    def schema(self):
        return SCHEMAS.get(self.schema_key)

    def fetch(self) -> pd.DataFrame:
        """SIMULATED: reads generated CSV. Override to call a real API / CSV drop."""
        return pd.read_csv(RAW_DIR / self.filename)

    def source_meta(self) -> dict:
        return {"source": self.name, "mode": "simulated", "file": self.filename, "description": self.description,
                "real_feed": self.real_feed}


class NCSJobPostingsConnector(BaseConnector):
    name, filename, schema_key = "postings", "postings.csv", "postings"
    description = "Job-portal / NCS-style postings (free text titles, employer, raw location, date)"
    real_feed = "NCS portal API or partner CSV drops; implement fetch() to page through postings and keep this column schema."
    # --- real integration stub ---
    # class LiveNCS(NCSJobPostingsConnector):
    #     def fetch(self):
    #         rows = requests.get(NCS_URL, headers={"Authorization": f"Bearer {TOKEN}"}, params={...}).json()
    #         return pd.DataFrame(rows)[["posting_id","title","employer","district_raw","portal","posted_date"]]


class IndustryHiringConnector(BaseConnector):
    name, filename, schema_key = "hiring", "hiring_signals.csv", "hiring"
    description = "Industry hiring signal index by district x NCO-coded trade x month"
    real_feed = "Industry body / SSC hiring surveys or aggregated HR-platform indices (NCO-coded)."


class PLFSConnector(BaseConnector):
    name, filename, schema_key = "plfs", "plfs.csv", "plfs"
    description = "PLFS-style quarterly employment level by district x trade (modelled)"
    real_feed = "MoSPI PLFS unit-level / tabulated estimates mapped from NCO to trade; district estimates need small-area modelling."


class EShramConnector(BaseConnector):
    name, filename, schema_key = "eshram", "eshram.csv", "eshram"
    description = "e-Shram registrations declaring the trade (aggregate counts only)"
    real_feed = "e-Shram aggregate dashboards/API (aggregate, non-personal counts only)."


class TrainingSeatsConnector(BaseConnector):
    name, filename, schema_key = "seats", "training_seats.csv", "seats"
    description = "Training seats by centre x trade x cycle with enrolment, completion and placement-ready rates"
    real_feed = "Skill India Digital / PMKVY centre MIS exports."


CONNECTORS = [NCSJobPostingsConnector(), IndustryHiringConnector(), PLFSConnector(), EShramConnector(), TrainingSeatsConnector()]


def _month_of(s: pd.Series) -> pd.Series:
    return s.dt.strftime("%Y-%m")


def dedup_postings(df: pd.DataFrame, cutoff: float) -> tuple[pd.DataFrame, dict]:
    """Exact duplicates via hash of normalised title + employer + district + ISO week; then near-duplicates
    (string similarity >= cutoff within the same district-week)."""
    df = df.sort_values("posted_date").reset_index(drop=True)
    iso = df["posted_date"].dt.isocalendar()
    df["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    df["employer_norm"] = df["employer"].fillna("").map(normalise_text)
    key = pd.util.hash_pandas_object(df[["title_norm", "employer_norm", "district_code", "week"]], index=False)
    exact = key.duplicated(keep="first").to_numpy()
    keep = ~exact
    near = np.zeros(len(df), dtype=bool)
    if HAVE_RF:
        sub = df[keep]
        for _, g in sub.groupby(["district_code", "week"]):
            if len(g) < 2:
                continue
            strs = (g["title_norm"] + "|" + g["employer_norm"]).tolist()
            idx = g.index.to_numpy()
            M = process.cdist(strs, strs, scorer=fuzz.ratio, score_cutoff=cutoff, dtype=np.uint8, workers=1)
            dropped = np.zeros(len(g), dtype=bool)
            for i in range(len(g)):
                if dropped[i]:
                    continue
                for j in np.nonzero(M[i, i + 1:])[0] + i + 1:
                    dropped[j] = True
            near[idx[dropped]] = True
    out = df[keep & ~near].reset_index(drop=True)
    return out, {"exact_duplicates": int(exact.sum()), "near_duplicates": int(near.sum())}


def run_ingestion(run_id: str, thresholds: dict) -> dict:
    """Fetch + validate + clean all sources. Returns cleaned frames and per-source quality metrics."""
    snap = SNAP_DIR / run_id
    snap.mkdir(parents=True, exist_ok=True)
    frames, metrics, rejects = {}, [], {}
    for c in CONNECTORS:
        raw = c.fetch()
        shutil.copy(RAW_DIR / c.filename, snap / c.filename) if (RAW_DIR / c.filename).exists() else None
        clean, rej = validate(raw, c.schema_key)
        m = {"run_id": run_id, "rows_raw": len(raw), "rows_valid": len(clean), "rows_rejected": len(rej),
             "exact_duplicates": 0, "near_duplicates": 0, **c.source_meta()}
        if c.name == "postings":
            clean = clean.copy()
            clean["district_code"] = clean["district_raw"].map(normalise_district)
            unk = clean[clean["district_code"].isna()]
            if len(unk):
                rej = pd.concat([rej, unk.assign(reason="district_raw:unknown_district")])
            clean = clean[clean["district_code"].notna()].copy()
            clean["title_norm"] = clean["title"].map(normalise_text)
            clean, d = dedup_postings(clean, thresholds["near_dup_cutoff"])
            clean["month"] = _month_of(clean["posted_date"])
            clean = clean[clean["month"].isin(MONTHS)]
            m.update(d)
            m["rows_rejected"] = len(rej)
            m["rows_valid"] = len(clean)
            m["completeness"] = round(m["rows_valid"] / max(m["rows_raw"] - m["exact_duplicates"] - m["near_duplicates"], 1), 4)
            m["latest_period"] = str(clean["month"].max())
        elif c.name == "seats":
            m["completeness"] = round(len(clean) / max(len(raw), 1), 4)
            m["latest_period"] = f"cycle {int(clean['cycle'].max())}"
        else:
            expected = len(D_CODES) * len(T_CODES) * (N_MONTHS if c.name != "plfs" else N_MONTHS // 3)
            m["completeness"] = round(min(len(clean) / expected, 1.0), 4)
            m["latest_period"] = str(clean["month"].max())
        frames[c.name] = clean
        rejects[c.name] = rej
        metrics.append(m)
    ref = max(MONTHS)
    for m in metrics:
        lp = m["latest_period"]
        m["freshness_lag_months"] = (pd.Period(ref) - pd.Period(lp)).n if lp[:2] == "20" and len(lp) == 7 else None
    for k, r in rejects.items():
        if len(r):
            r.head(5000).to_csv(snap / f"rejected_{k}.csv", index=False)
    return {"frames": frames, "metrics": metrics, "rejects": rejects}
