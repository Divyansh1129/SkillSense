"""Module 5 - Gap, severity, early warnings, what-if, target recommendation.

Gap = ForecastDemand(H months) - ExpectedEmployableSupply(H/12 of annual)     (+ = shortage, - = oversupply)
GapPct = Gap / max(ForecastDemand, 5), clipped to [-1.5, 1.5];  GapZ = z-score of GapPct within trade across districts.

Severity (0-100) = 100 * ( 0.55*m + 0.20*t + 0.10*g + 0.15*c )
   m = min(|GapPct| / 0.6, 1)                         magnitude of the gap
   t = clip((dem_growth - sup_growth) * sign(gap) / 0.30, 0, 1)    is the gap widening?
   g = clip( sign(gap) * dem_growth / 0.30, 0, 1)     demand growth that worsens the gap (rising for shortage, falling for oversupply)
   c = (1 - clip(width95 / 1.2, 0, 1)) * confidence   forecast certainty x data confidence
"""
import json

import numpy as np
import pandas as pd

from .taxonomy import DISTRICT_BY_CODE, TRADE_BY_CODE

LEVEL_RANK = {"watch": 1, "warning": 2, "critical": 3}


def severity_score(gap_pct, dem_growth, sup_growth, width_rel, conf):
    gap_pct, dem_growth, sup_growth, width_rel, conf = map(lambda x: np.asarray(x, float), (gap_pct, dem_growth, sup_growth, width_rel, conf))
    sgn = np.sign(gap_pct)
    m = np.minimum(np.abs(gap_pct) / 0.6, 1)
    t = np.clip((dem_growth - sup_growth) * sgn / 0.30, 0, 1)
    g = np.clip(sgn * dem_growth / 0.30, 0, 1)
    c = (1 - np.clip(width_rel / 1.2, 0, 1)) * conf
    return np.round(100 * (0.55 * m + 0.20 * t + 0.10 * g + 0.15 * c), 1)


def direction(gap_pct):
    gap_pct = np.asarray(gap_pct, float)
    return np.where(gap_pct > 0.05, "shortage", np.where(gap_pct < -0.05, "oversupply", "balanced"))


def recommend_seats(D, seats, a, carry, max_change=0.5, budget=None):
    """Seat allocation minimising total |gap| subject to +-max_change per series and an optional total-seat budget.
    Closed form per series (S = a*x + carry, so x* = (D-carry)/a), clipped to bounds; with a binding budget the extra seats
    are allocated greedily to the series where one seat closes most gap (highest a) - the exact LP solution (fractional knapsack)."""
    D, seats, a, carry = (np.asarray(v, float) for v in (D, seats, a, carry))
    target = np.maximum(0.0, (D - carry) / np.maximum(a, 1e-9))
    lo = np.floor(seats * (1 - max_change))
    hi = np.maximum(np.ceil(seats * (1 + max_change)), np.where(seats == 0, np.round(target * max_change), 0))
    tgt = np.clip(target, lo, hi)
    x = tgt.copy()
    if budget is not None:
        budget = float(budget)
        if lo.sum() >= budget:
            x = lo * (budget / max(lo.sum(), 1e-9))
        elif tgt.sum() > budget:
            x, remaining = lo.copy(), budget - lo.sum()
            for i in np.argsort(-a):
                add = min(tgt[i] - lo[i], remaining)
                if add > 0:
                    x[i] += add
                    remaining -= add
    return np.round(x)


def compute_gaps(fc: pd.DataFrame, supply: pd.DataFrame, hist: pd.DataFrame, quality: pd.DataFrame, thr: dict, run_id: str) -> pd.DataFrame:
    """One row per (district, trade, horizon in {6,12})."""
    key = ["district_code", "trade_code"]
    base = supply.set_index(key)
    last12 = hist.groupby(key)["openings_est"].apply(lambda s: s.iloc[-12:].sum()).rename("hist12")
    conf = quality.set_index(key)["confidence"]
    d12 = fc.groupby(key)["yhat"].sum().rename("d12")
    parts = []
    for H in (6, 12):
        f = fc[fc["h"] <= H].copy()
        f["w95"] = (f["hi95"] - f["lo95"]) / np.maximum(f["yhat"], 1e-6)
        g = f.groupby(key).agg(demand=("yhat", "sum"), width=("w95", "mean"), lo=("lo80", "sum"), hi=("hi80", "sum")).reset_index().set_index(key)
        g = g.join(base[["seats", "seats_prev", "a_rate", "carry", "supply_annual", "supply_growth"]]).join(last12).join(conf.rename("confidence")).join(d12)
        g["horizon"] = H
        g["supply"] = g["supply_annual"] * H / 12
        g["gap"] = g["demand"] - g["supply"]
        g["gap_pct"] = (g["gap"] / np.maximum(g["demand"], 5)).clip(-1.5, 1.5)
        g["demand_growth"] = (g["d12"] / np.maximum(g["hist12"], 1e-6) - 1).clip(-0.9, 3.0)
        g = g.reset_index()
        g["gap_z"] = g.groupby("trade_code")["gap_pct"].transform(lambda s: (s - s.mean()) / (s.std() or 1))
        g["severity"] = severity_score(g["gap_pct"], g["demand_growth"], g["supply_growth"], g["width"], g["confidence"])
        g["direction"] = direction(g["gap_pct"])
        g["suggested_seats"] = np.nan
        if H == 12:
            g["suggested_seats"] = recommend_seats(g["demand"], g["seats"], g["a_rate"], g["carry"], thr["max_change_pct"])
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    out["run_id"] = run_id
    out = out.rename(columns={"width": "width95"})
    return out.drop(columns=["d12"])


# ----------------------------------------------------------------------- early warning flags
def _level_from(v, watch, warn, crit):
    return "critical" if v >= crit else "warning" if v >= warn else "watch" if v >= watch else None


def build_alerts(gaps: pd.DataFrame, thr: dict, run_id: str) -> pd.DataFrame:
    """Flags: ACUTE_SHORTAGE, APPROACHING_SATURATION, EMERGING_DEMAND, DATA_LOW_CONFIDENCE (horizon 12 rows)."""
    g = gaps[gaps["horizon"] == 12].reset_index(drop=True)
    # best same-district shortage trade to shift seats towards (prefer same sector)
    short = g[(g["gap"] > 20) & (g["gap_pct"] > thr["shortage_watch"])]
    recs = []
    for r in g.itertuples(index=False):
        dc, tc = r.district_code, r.trade_code
        sec = TRADE_BY_CODE[tc][2]
        flags = []
        gp, dg, sg = r.gap_pct, r.demand_growth, r.supply_growth
        ratio = r.supply / max(r.demand, 1e-9)
        lv = _level_from(gp, thr["shortage_watch"], thr["shortage_warning"], thr["shortage_critical"])
        if lv:
            flags.append(("ACUTE_SHORTAGE", lv))
        lv = _level_from(-gp, thr["oversupply_watch"], thr["oversupply_warning"], thr["oversupply_critical"])
        if lv and dg <= thr["saturation_demand_growth_max"]:
            if sg > 0 and lv != "critical":
                lv = {"watch": "warning", "warning": "critical"}[lv]      # supply still rising -> escalate
            flags.append(("APPROACHING_SATURATION", lv))
        if dg >= thr["emerging_growth_min"] and ratio <= thr["emerging_supply_ratio_max"]:
            lv = "critical" if (dg >= thr["emerging_growth_critical"] and gp >= thr["shortage_warning"]) else \
                 "warning" if dg >= (thr["emerging_growth_min"] + thr["emerging_growth_critical"]) / 2 else "watch"
            flags.append(("EMERGING_DEMAND", lv))
        if r.confidence < thr["low_conf_warning"]:
            flags.append(("DATA_LOW_CONFIDENCE", "warning"))
        elif r.confidence < thr["low_conf_watch"]:
            flags.append(("DATA_LOW_CONFIDENCE", "watch"))
        for flag, lvl in flags:
            params = {"horizon": 12, "demand": int(round(r.demand)), "supply": int(round(r.supply)), "gap": int(round(r.gap)),
                      "gap_pct": int(round(abs(gp) * 100)), "dem_growth": int(round(dg * 100)), "sup_growth": int(round(sg * 100)),
                      "conf": int(round(r.confidence * 100)), "severity": float(r.severity)}
            chg = (r.suggested_seats / r.seats - 1) if r.seats > 0 else None
            aparams = {"pct": int(round(abs(chg) * 100)) if chg is not None else None, "seats": int(round(abs(r.suggested_seats - r.seats)))}
            if flag == "ACUTE_SHORTAGE" or flag == "EMERGING_DEMAND":
                akey = "action.increase" if r.seats > 0 else "action.new_centre"
            elif flag == "APPROACHING_SATURATION":
                cand = short[(short["district_code"] == dc) & (short["trade_code"] != tc)]
                if len(cand):
                    cand = cand.assign(same=[TRADE_BY_CODE[c][2] == sec for c in cand["trade_code"]]).sort_values(["same", "gap"], ascending=False)
                    aparams["shift_trade_code"] = cand.iloc[0]["trade_code"]
                    akey = "action.reduce_shift"
                else:
                    akey = "action.reduce"
            else:
                akey = "action.verify_data"
            recs.append({"run_id": run_id, "alert_key": f"{dc}|{tc}|{flag}", "district_code": dc, "trade_code": tc, "flag": flag,
                         "level": lvl, "severity": float(r.severity), "reason_key": f"reason.{flag}",
                         "reason_params": json.dumps(params), "action_key": akey, "action_params": json.dumps(aparams),
                         "reason_en": reason_en(flag, params), "action_en": action_en(akey, aparams)})
    df = pd.DataFrame(recs)
    if len(df):
        df["rank"] = df["level"].map(LEVEL_RANK)
        df = df.sort_values(["rank", "severity"], ascending=False).drop(columns="rank").reset_index(drop=True)
        df.insert(0, "id", np.arange(1, len(df) + 1))
    return df


def reason_en(flag: str, p: dict) -> str:
    return {
        "ACUTE_SHORTAGE": "Forecast demand ({demand}) exceeds expected trained supply ({supply}) by {gap_pct}% over the next {horizon} months.",
        "APPROACHING_SATURATION": "Trained supply ({supply}) exceeds forecast demand ({demand}) by {gap_pct}% while demand growth is {dem_growth}% (supply growth {sup_growth}%).",
        "EMERGING_DEMAND": "Demand is forecast to grow {dem_growth}% but expected supply covers only part of it ({supply} vs {demand}).",
        "DATA_LOW_CONFIDENCE": "Data confidence is only {conf}% (sparse or missing sources); treat this forecast with caution.",
    }[flag].format(**p)


def action_en(key: str, p: dict) -> str:
    sh = TRADE_BY_CODE[p["shift_trade_code"]][1] if p.get("shift_trade_code") else ""
    return {
        "action.increase": f"Consider increasing seats by about {p['pct']}% (~{p['seats']} seats) next cycle.",
        "action.new_centre": f"No current seats: consider sanctioning about {p['seats']} seats.",
        "action.reduce": f"Consider reducing seats by about {p['pct']}% (~{p['seats']} seats) next cycle.",
        "action.reduce_shift": f"Consider reducing seats by about {p['pct']}% (~{p['seats']} seats) or shifting them to {sh}.",
        "action.verify_data": "Verify source data for this district before using this forecast for targets.",
    }[key]


# ----------------------------------------------------------------------- what-if
def whatif(g: pd.DataFrame, mode: str, value: float, horizon_scale: float) -> pd.DataFrame:
    """g: gap rows (one horizon) in scope with seats/a_rate/carry/... Returns per-row before/after."""
    g = g.copy()
    if mode == "pct":
        new = np.maximum(0.0, g["seats"] * (1 + value / 100.0))
    else:  # absolute seat change distributed proportionally to current seats (equally if none)
        w = g["seats"] / g["seats"].sum() if g["seats"].sum() > 0 else pd.Series(1 / len(g), index=g.index)
        new = np.maximum(0.0, g["seats"] + value * w)
    g["seats_new"] = np.round(new)
    g["supply_new"] = (g["a_rate"] * g["seats_new"] + g["carry"]) * horizon_scale
    g["gap_new"] = g["demand"] - g["supply_new"]
    g["gap_pct_new"] = (g["gap_new"] / np.maximum(g["demand"], 5)).clip(-1.5, 1.5)
    sup_g = np.where(g["seats_prev"] > 0, g["seats_new"] / g["seats_prev"].replace(0, np.nan) - 1, np.where(g["seats_new"] > 0, 1.0, 0.0))
    g["severity_new"] = severity_score(g["gap_pct_new"], g["demand_growth"], sup_g, g["width95"], g["confidence"])
    g["direction_new"] = direction(g["gap_pct_new"])
    return g


def decorate(df: pd.DataFrame) -> pd.DataFrame:
    """Add names for display/export."""
    df = df.copy()
    df["district"] = df["district_code"].map(lambda c: DISTRICT_BY_CODE[c][1])
    df["state"] = df["district_code"].map(lambda c: DISTRICT_BY_CODE[c][2])
    df["trade"] = df["trade_code"].map(lambda c: TRADE_BY_CODE[c][1])
    df["sector"] = df["trade_code"].map(lambda c: TRADE_BY_CODE[c][2])
    df["nco_code"] = df["trade_code"].map(lambda c: TRADE_BY_CODE[c][3])
    df["nsqf_level"] = df["trade_code"].map(lambda c: TRADE_BY_CODE[c][4])
    df["ssc"] = df["trade_code"].map(lambda c: TRADE_BY_CODE[c][5])
    return df
