"""Module 3 - Demand Index + Supply model.

Per (district, trade, month):
  1. each source signal is scaled with a robust z-score within the series (median/MAD, clipped to +-3)
  2. DemandIndex = sum_i  w~_i * z_i, where w~ are the configured weights multiplied by a per-source quality factor and
     re-normalised over the sources actually available that month (missing source -> lower confidence, not a crash)
  3. Calibration to openings: z is converted back to a relative deviation with each signal's own robust spread
     (s_i = 1.4826*MAD/median) and applied to a PLFS-anchored baseline:
        openings_t = B * clip(1 + sum_i w~_i z_i s_i, 0.2, 3.0),   B = median(PLFS employment) * turnover_rate / 12
     so the result is in "openings per month" and comparable to training seats.
  4. Per-source contributions (in openings) are stored for explainability.
"""
import numpy as np
import pandas as pd

from .config import DATA_START, N_MONTHS
from .taxonomy import DISTRICTS, TRADES

SOURCES = ["postings", "hiring", "plfs", "eshram"]
MONTHS = [str(p) for p in pd.period_range(DATA_START, periods=N_MONTHS, freq="M")]
TURNOVER = {t[0]: t[6] for t in TRADES}


def _grid() -> pd.DataFrame:
    return pd.MultiIndex.from_product([[d[0] for d in DISTRICTS], [t[0] for t in TRADES], MONTHS],
                                      names=["district_code", "trade_code", "month"]).to_frame(index=False)


def build_panel(frames: dict) -> pd.DataFrame:
    """Join the four demand signals onto the full district x trade x month grid."""
    g = _grid()
    p = frames["postings_clean"].groupby(["district_code", "trade_code", "month"]).size().rename("postings_raw").reset_index()
    g = g.merge(p, how="left", on=["district_code", "trade_code", "month"])
    g["postings_raw"] = g["postings_raw"].fillna(0.0)
    g = g.merge(frames["hiring"][["district_code", "trade_code", "month", "hiring_index"]], how="left", on=["district_code", "trade_code", "month"])
    g = g.merge(frames["plfs"][["district_code", "trade_code", "month", "employment_level"]], how="left", on=["district_code", "trade_code", "month"])
    g = g.merge(frames["eshram"][["district_code", "trade_code", "month", "registrations"]], how="left", on=["district_code", "trade_code", "month"])
    g = g.sort_values(["district_code", "trade_code", "month"]).reset_index(drop=True)
    key = ["district_code", "trade_code"]
    g["postings_s"] = g.groupby(key)["postings_raw"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    g["plfs_f"] = g.groupby(key)["employment_level"].ffill()   # quarterly -> monthly (carry forward)
    return g.rename(columns={"hiring_index": "hiring_raw", "registrations": "eshram_raw"})


def _robust(g: pd.DataFrame, col: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    key = ["district_code", "trade_code"]
    med = g.groupby(key)[col].transform("median")
    mad = (g[col] - med).abs().groupby([g[k] for k in key]).transform("median") * 1.4826
    std = g.groupby(key)[col].transform("std")
    scale = mad.where(mad > 1e-9, std).fillna(0.0)
    z = ((g[col] - med) / scale.replace(0, np.nan)).clip(-3, 3).fillna(0.0).where(g[col].notna())
    spread = (scale / med.abs().replace(0, np.nan)).clip(0.01, 0.6).fillna(0.1)
    return z, spread, med


def compute_demand_index(panel: pd.DataFrame, weights: dict, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (demand_index rows, series_quality rows)."""
    w0 = {k: float(weights.get(k, 0.0)) for k in SOURCES}
    tot = sum(w0.values())
    w0 = {k: v / tot for k, v in w0.items()}                     # enforce sum to 1
    g = panel.copy()
    cols = {"postings": "postings_s", "hiring": "hiring_raw", "plfs": "plfs_f", "eshram": "eshram_raw"}
    key = ["district_code", "trade_code"]
    # per-series quality: sparse online postings get down-weighted
    mean_post = g.groupby(key)["postings_raw"].transform("mean")
    q = {"postings": (mean_post / 2.0).clip(0.15, 1.0), "hiring": 1.0, "plfs": 1.0, "eshram": 1.0}
    z, s, eff = {}, {}, {}
    for k, c in cols.items():
        z[k], s[k], _ = _robust(g, c)
        avail = g[c].notna().astype(float)
        eff[k] = w0[k] * (q[k] if isinstance(q[k], pd.Series) else q[k]) * avail
    denom = sum(eff.values()).replace(0, np.nan)
    wn = {k: (eff[k] / denom).fillna(0.0) for k in SOURCES}
    out = g[["district_code", "trade_code", "month"]].copy()
    out["run_id"] = run_id
    out["demand_index"] = sum(wn[k] * z[k].fillna(0.0) for k in SOURCES)
    out["confidence"] = (sum(eff.values()) / sum(w0.values())).clip(0, 1)
    base = g.groupby(key)["plfs_f"].transform("median") * g["trade_code"].map(TURNOVER) / 12.0
    # fall back to the median of the other signals if PLFS is entirely absent for a series
    fb = g.groupby(key)["eshram_raw"].transform("median") / 3.0
    base = base.fillna(fb).fillna(g.groupby("trade_code")["postings_raw"].transform("median") / 0.25)
    rel = sum(wn[k] * z[k].fillna(0.0) * s[k] for k in SOURCES)
    out["baseline"] = base
    out["rel_dev"] = rel
    out["openings_est"] = base * (1 + rel).clip(0.2, 3.0)
    for k in SOURCES:
        out[f"w_{k}"] = wn[k]
        out[f"z_{k}"] = z[k]
        out[f"o_{k}"] = base * wn[k] * z[k].fillna(0.0) * s[k]    # contribution in openings/month
    sq = pd.DataFrame({"district_code": g["district_code"], "trade_code": g["trade_code"], "mean_postings": mean_post,
                       "confidence": out["confidence"]}).groupby(key).agg(
        mean_postings=("mean_postings", "first"), confidence=("confidence", "mean")).reset_index()
    sq["sparse"] = (sq["mean_postings"] < 1.0).astype(int)
    sq["run_id"] = run_id
    return out, sq


def compute_supply(seats: pd.DataFrame, retention: float, run_id: str) -> pd.DataFrame:
    """Annual employable supply = seats * enrolment * completion * placement-ready  + carry-over of recently certified
    candidates still unplaced (previous cycle certified * (1-ready share) * retention)."""
    s = seats.copy()
    s["cert"] = s["seats"] * s["enrolment_rate"] * s["completion_rate"]
    s["ready"] = s["cert"] * s["placement_ready_rate"]
    agg = s.groupby(["district_code", "trade_code", "cycle"]).agg(
        seats=("seats", "sum"), cert=("cert", "sum"), ready=("ready", "sum")).reset_index()
    latest = int(agg["cycle"].max())
    cur = agg[agg["cycle"] == latest].set_index(["district_code", "trade_code"])
    prev = agg[agg["cycle"] == latest - 1].set_index(["district_code", "trade_code"])
    idx = pd.MultiIndex.from_product([[d[0] for d in DISTRICTS], [t[0] for t in TRADES]], names=["district_code", "trade_code"])
    out = pd.DataFrame(index=idx)
    out["seats"] = cur["seats"].reindex(idx).fillna(0.0)
    out["cert"] = cur["cert"].reindex(idx).fillna(0.0)
    out["ready"] = cur["ready"].reindex(idx).fillna(0.0)
    out["seats_prev"] = prev["seats"].reindex(idx).fillna(0.0)
    prev_unplaced = (prev["cert"] - prev["ready"]).reindex(idx).fillna(0.0)
    out["carry"] = prev_unplaced * retention
    out["a_rate"] = np.where(out["seats"] > 0, out["ready"] / out["seats"].replace(0, np.nan), 0.0)
    # rate for zero-seat series (needed by the recommender): trade-level median
    med_rate = out.loc[out["a_rate"] > 0].groupby("trade_code")["a_rate"].median()
    out["a_rate"] = np.where(out["a_rate"] > 0, out["a_rate"], out.index.get_level_values("trade_code").map(med_rate).fillna(0.45))
    out["supply_annual"] = out["ready"] + out["carry"]
    out["supply_growth"] = np.where(out["seats_prev"] > 0, out["seats"] / out["seats_prev"].replace(0, np.nan) - 1,
                                    np.where(out["seats"] > 0, 1.0, 0.0))
    out = out.reset_index()
    out["cycle"] = latest
    out["run_id"] = run_id
    return out
