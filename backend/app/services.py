"""Query/service layer. Framework independent so it can be tested without FastAPI."""
import io
import json

import numpy as np
import pandas as pd

from . import db
from .config import DEMO_DATA, DEFAULT_WEIGHTS, RAW_DIR, WEIGHT_RATIONALE
from .gap import decorate, recommend_seats, whatif as _whatif
from .taxonomy import DISTRICTS, SECTORS, STATES, TRADES


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def latest_run(run_id: str | None = None) -> str:
    if run_id:
        return run_id
    r = db.query("SELECT run_id FROM pipeline_runs WHERE status='success' ORDER BY run_id DESC LIMIT 1")
    if not r:
        raise ApiError(409, "no_data", "No pipeline run yet. Run `python -m scripts.setup_demo` or POST /api/v1/pipeline/run.")
    return r[0]["run_id"]


def taxonomy() -> dict:
    return {"demo_data": DEMO_DATA,
            "states": [{"code": c, "name": n} for c, n in STATES],
            "districts": [{"code": d[0], "name": d[1], "state": d[2], "type": d[3]} for d in DISTRICTS],
            "sectors": [{"code": c, "name": n} for c, n in SECTORS],
            "trades": [{"code": t[0], "name": t[1], "sector": t[2], "nco_code": t[3], "nsqf_level": t[4], "ssc": t[5]} for t in TRADES]}


def _filter(df: pd.DataFrame, state=None, district=None, sector=None, trade=None) -> pd.DataFrame:
    if state:
        df = df[df["state"] == state]
    if district:
        df = df[df["district_code"] == district]
    if sector:
        df = df[df["sector"] == sector]
    if trade:
        df = df[df["trade_code"] == trade]
    return df


def gaps_df(horizon: int = 12, run_id: str | None = None, **flt) -> pd.DataFrame:
    run_id = latest_run(run_id)
    g = decorate(db.qdf("SELECT * FROM gaps WHERE run_id=? AND horizon=?", (run_id, horizon)))
    al = db.qdf("SELECT district_code, trade_code, level, flag FROM alerts WHERE run_id=?", (run_id,))
    if len(al):
        al["r"] = al["level"].map({"watch": 1, "warning": 2, "critical": 3})
        top = al.sort_values("r", ascending=False).drop_duplicates(["district_code", "trade_code"])
        g = g.merge(top[["district_code", "trade_code", "flag", "level"]].rename(columns={"level": "flag_level"}), how="left", on=["district_code", "trade_code"])
    else:
        g["flag"], g["flag_level"] = None, None
    return _filter(g, **flt).reset_index(drop=True)


def _clean(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.replace({np.nan: None}).to_json(orient="records"))


def paginate(df: pd.DataFrame, page: int, page_size: int) -> dict:
    total = len(df)
    sl = df.iloc[(page - 1) * page_size: page * page_size]
    return {"total": total, "page": page, "page_size": page_size, "items": _clean(sl)}


GAP_COLS = ["district_code", "district", "state", "trade_code", "trade", "sector", "nco_code", "nsqf_level", "ssc", "horizon", "demand", "supply",
            "gap", "gap_pct", "gap_z", "severity", "direction", "demand_growth", "supply_growth", "seats", "suggested_seats", "confidence", "flag", "flag_level"]


def gap_page(horizon, page, page_size, run_id=None, **flt) -> dict:
    g = gaps_df(horizon, run_id, **flt).sort_values("severity", ascending=False)
    return paginate(g[GAP_COLS], page, page_size)


def ranking(type_: str, level: str, top: int, horizon: int, run_id=None, **flt) -> dict:
    g = gaps_df(horizon, run_id, **flt)
    if level in ("state", "district"):
        keys = ["state"] if level == "state" else ["district_code", "district", "state"]
        a = g.assign(w=g["demand"].clip(lower=1), sv=g["severity"] * g["demand"].clip(lower=1)).groupby(keys).agg(
            demand=("demand", "sum"), supply=("supply", "sum"), gap=("gap", "sum"), sv=("sv", "sum"), w=("w", "sum"),
            critical=("flag_level", lambda s: int((s == "critical").sum()))).reset_index()
        a["gap_pct"] = a["gap"] / a["demand"].clip(lower=5)
        a["severity"] = (a["sv"] / a["w"]).round(1)
        a["direction"] = np.where(a["gap_pct"] > 0.05, "shortage", np.where(a["gap_pct"] < -0.05, "oversupply", "balanced"))
        g = a.drop(columns=["sv", "w"])
    g = g[g["gap"] > 0] if type_ == "shortage" else g[g["gap"] < 0]
    g = g.sort_values("severity", ascending=False).head(top)
    return {"type": type_, "level": level, "items": _clean(g[[c for c in GAP_COLS + ["critical"] if c in g.columns]])}


def overview(horizon=12, run_id=None, **flt) -> dict:
    run_id = latest_run(run_id)
    g = gaps_df(horizon, run_id, **flt)

    def agg(keys):
        a = g.assign(sv=g["severity"] * g["demand"].clip(lower=1), w=g["demand"].clip(lower=1)).groupby(keys).agg(
            demand=("demand", "sum"), supply=("supply", "sum"), gap=("gap", "sum"), sv=("sv", "sum"), w=("w", "sum"),
            critical=("flag_level", lambda s: int((s == "critical").sum())), warning=("flag_level", lambda s: int((s == "warning").sum()))).reset_index()
        a["gap_pct"] = a["gap"] / a["demand"].clip(lower=5)
        a["severity"] = (a["sv"] / a["w"]).round(1)
        a["direction"] = np.where(a["gap_pct"] > 0.05, "shortage", np.where(a["gap_pct"] < -0.05, "oversupply", "balanced"))
        return a.drop(columns=["sv", "w"])
    tr = agg(["trade_code", "trade"])
    tr = tr[tr["demand"] > 50]
    ts = tr.sort_values("gap_pct", ascending=False).iloc[0] if len(tr) else None
    to = tr.sort_values("gap_pct").iloc[0] if len(tr) else None
    runs = db.query("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,))[0]
    meta = db.qdf("SELECT source, freshness_lag_months, completeness FROM source_meta")
    return {"run": {"run_id": run_id, "finished": runs["finished"], "demo_data": DEMO_DATA},
            "kpis": {"critical_alerts": int((g["flag_level"] == "critical").sum()), "warning_alerts": int((g["flag_level"] == "warning").sum()),
                     "top_shortage": _clean(pd.DataFrame([ts]))[0] if ts is not None else None,
                     "top_oversupply": _clean(pd.DataFrame([to]))[0] if to is not None else None,
                     "max_freshness_lag_months": float(meta["freshness_lag_months"].max()) if len(meta) else None,
                     "min_completeness": float(meta["completeness"].min()) if len(meta) else None},
            "states": _clean(agg(["state"])), "districts": _clean(agg(["district_code", "district", "state"])), "trades": _clean(tr)}


def forecast_rows(run_id=None, horizon=12, page=1, page_size=200, **flt) -> dict:
    run_id = latest_run(run_id)
    f = db.qdf("SELECT * FROM forecasts WHERE run_id=? AND h<=?", (run_id, horizon))
    f = _filter(decorate(f), **flt)
    return paginate(f[["district_code", "district", "state", "trade_code", "trade", "sector", "month", "h", "yhat", "lo80", "hi80", "lo95", "hi95"]], page, page_size)


def timeseries(district: str, trade: str, run_id=None) -> dict:
    run_id = latest_run(run_id)
    hist = db.qdf("SELECT month, openings_est, demand_index, confidence FROM demand_index WHERE district_code=? AND trade_code=? ORDER BY month", (district, trade))
    fc = db.qdf("SELECT month, h, yhat, lo80, hi80, lo95, hi95 FROM forecasts WHERE run_id=? AND district_code=? AND trade_code=? ORDER BY h", (run_id, district, trade))
    sup = db.query("SELECT * FROM supply_estimate WHERE district_code=? AND trade_code=?", (district, trade))
    if hist.empty or not sup:
        raise ApiError(404, "not_found", "Unknown district/trade")
    g = gaps_df(12, run_id, district=district, trade=trade)
    al = db.qdf("SELECT * FROM alerts WHERE run_id=? AND district_code=? AND trade_code=?", (run_id, district, trade))
    ack = {r["alert_key"]: r for r in db.query("SELECT * FROM alert_ack")}
    alerts = [{**r, "reason_params": json.loads(r["reason_params"]), "action_params": json.loads(r["action_params"]), "ack": ack.get(r["alert_key"])} for r in _clean(al)]
    s = sup[0]
    return {"run_id": run_id, "history": _clean(hist), "forecast": _clean(fc), "supply_annual": s["supply_annual"], "seats": s["seats"],
            "supply_monthly": s["supply_annual"] / 12, "gap": _clean(g)[0] if len(g) else None, "alerts": alerts}


def demand_index_series(district: str, trade: str) -> dict:
    d = db.qdf("SELECT * FROM demand_index WHERE district_code=? AND trade_code=? ORDER BY month", (district, trade))
    if d.empty:
        raise ApiError(404, "not_found", "Unknown district/trade")
    return {"district_code": district, "trade_code": trade, "weights_configured": db.get_weights(), "items": _clean(d)}


def alerts_list(run_id=None, level=None, state=None, sector=None, flag=None, district=None, include_dismissed=False) -> list[dict]:
    run_id = latest_run(run_id)
    a = decorate(db.qdf("SELECT * FROM alerts WHERE run_id=?", (run_id,)))
    a = _filter(a, state=state, sector=sector, district=district)
    if level:
        a = a[a["level"] == level]
    if flag:
        a = a[a["flag"] == flag]
    ack = {r["alert_key"]: r for r in db.query("SELECT * FROM alert_ack")}
    out = []
    for r in _clean(a):
        r["reason_params"], r["action_params"] = json.loads(r["reason_params"]), json.loads(r["action_params"])
        r["ack"] = ack.get(r["alert_key"])
        if r["ack"] and r["ack"]["status"] == "dismissed" and not include_dismissed:
            continue
        out.append(r)
    return out


def ack_alert(alert_id: int, status: str, note: str, role: str) -> dict:
    run_id = latest_run()
    r = db.query("SELECT alert_key FROM alerts WHERE run_id=? AND id=?", (run_id, alert_id))
    if not r:
        raise ApiError(404, "not_found", "Alert not found")
    db.execute("INSERT INTO alert_ack(alert_key,status,note,ts,role) VALUES (?,?,?,?,?) ON CONFLICT(alert_key) DO UPDATE SET status=excluded.status, note=excluded.note, ts=excluded.ts, role=excluded.role",
               (r[0]["alert_key"], status, note, db.now(), role))
    db.audit(role, "alert_" + status, {"alert_key": r[0]["alert_key"], "note": note})
    return {"alert_key": r[0]["alert_key"], "status": status}


def run_whatif(p: dict) -> dict:
    h = p.get("horizon", 12)
    g = gaps_df(h, None, state=p.get("state"), district=p.get("district"), sector=p.get("sector"), trade=p.get("trade"))
    if g.empty:
        raise ApiError(404, "not_found", "No series match the scope")
    r = _whatif(g, p.get("mode", "pct"), float(p["value"]), h / 12)

    def tot(d, supply, gap, sev):
        D, S = float(d["demand"].sum()), float(d[supply].sum())
        w = d["demand"].clip(lower=1)
        return {"demand": D, "supply": S, "gap": D - S, "gap_pct": (D - S) / max(D, 5), "severity": float((d[sev] * w).sum() / w.sum()),
                "seats": float(d["seats"].sum() if supply == "supply" else d["seats_new"].sum())}
    items = r.sort_values("severity", ascending=False).head(200)
    cols = ["district_code", "district", "trade_code", "trade", "demand", "seats", "seats_new", "supply", "supply_new", "gap", "gap_new", "gap_pct", "gap_pct_new",
            "severity", "severity_new", "direction", "direction_new"]
    return {"n_series": len(r), "before": tot(r, "supply", "gap", "severity"), "after": tot(r, "supply_new", "gap_new", "severity_new"), "items": _clean(items[cols])}


def run_recommend(p: dict) -> dict:
    thr = db.get_thresholds()
    g = gaps_df(12, None, state=p.get("state"), district=p.get("district"), sector=p.get("sector"), trade=p.get("trade"))
    if g.empty:
        raise ApiError(404, "not_found", "No series match the scope")
    mc = p.get("max_change_pct", thr["max_change_pct"] * 100) / 100
    x = recommend_seats(g["demand"], g["seats"], g["a_rate"], g["carry"], mc, p.get("budget"))
    g["suggested_seats"] = x
    g["supply_after"] = g["a_rate"] * x + g["carry"]
    g["gap_after"] = g["demand"] - g["supply_after"]
    g["change"] = x - g["seats"]
    items = g.reindex(g["change"].abs().sort_values(ascending=False).index).head(300)
    return {"n_series": len(g), "total_seats_before": float(g["seats"].sum()), "total_seats_after": float(x.sum()),
            "abs_gap_before": float(g["gap"].abs().sum()), "abs_gap_after": float(g["gap_after"].abs().sum()),
            "items": _clean(items[["district_code", "district", "trade_code", "trade", "demand", "seats", "suggested_seats", "change", "gap", "gap_after"]])}


def export_df(run_id=None, **flt) -> pd.DataFrame:
    run_id = latest_run(run_id)
    g = gaps_df(12, run_id, **flt)
    out = g.rename(columns={"demand": "forecast_demand"})
    out["source_run_id"] = run_id
    out["generated_at"] = db.query("SELECT generated_at FROM forecast_runs WHERE run_id=?", (run_id,))[0]["generated_at"]
    out["flag"] = out["flag"].fillna("")
    return out[["state", "district", "sector", "trade", "nco_code", "nsqf_level", "forecast_demand", "supply", "gap", "severity", "flag",
                "suggested_seats", "source_run_id", "generated_at"]].round(2)


def export_bytes(fmt: str, **flt) -> tuple[bytes, str, str]:
    df = export_df(**flt)
    if fmt == "csv":
        return df.to_csv(index=False).encode(), "text/csv", "forecast.csv"
    if fmt == "json":
        return df.to_json(orient="records", indent=1).encode(), "application/json", "forecast.json"
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="forecast")
    return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "forecast.xlsx"


def targets_csv(**flt) -> bytes:
    g = gaps_df(12, None, **flt)
    return g.assign(current_seats=g["seats"])[["state", "district", "sector", "trade", "nco_code", "nsqf_level", "current_seats", "suggested_seats", "gap", "severity"]].round(1).to_csv(index=False).encode()


def meta_sources() -> dict:
    return {"demo_data": DEMO_DATA, "items": _clean(db.qdf("SELECT * FROM source_meta")), "runs": db.query("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1")}


def model_quality(run_id=None) -> dict:
    run_id = latest_run(run_id)
    bt = db.qdf("SELECT scope, model, metric, value, n FROM backtests WHERE run_id=?", (run_id,))
    info = db.query("SELECT * FROM forecast_runs WHERE run_id=?", (run_id,))
    return {"run_id": run_id, "info": info[0] if info else None, "demo_data": DEMO_DATA, "metrics": _clean(bt),
            "note": "Backtest on SIMULATED data (holdout origins). Intervals calibrated on earlier origins. Real-data accuracy will differ."}


def mapping_quality() -> dict:
    r = db.query("SELECT * FROM mapping_quality")
    return {"metrics": json.loads(r[0]["metrics"]) if r else {}}


def runs() -> list[dict]:
    return db.query("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 30")


def get_weights() -> dict:
    return {"weights": db.get_weights(), "defaults": DEFAULT_WEIGHTS, "rationale": WEIGHT_RATIONALE}


def put_weights(w: dict, role: str) -> dict:
    keys = set(DEFAULT_WEIGHTS)
    if set(w) != keys or any(v < 0 for v in w.values()):
        raise ApiError(422, "invalid_weights", f"Provide non-negative weights for exactly: {sorted(keys)}")
    s = sum(w.values())
    if abs(s - 1) > 0.01:
        raise ApiError(422, "invalid_weights", f"Weights must sum to 1 (got {s:.3f})")
    for k, v in w.items():
        db.execute("UPDATE config_weights SET weight=? WHERE source=?", (v / s, k))
    db.audit(role, "weights_changed", w)
    return {"weights": db.get_weights()}


def put_thresholds(t: dict, role: str) -> dict:
    cur = db.get_thresholds()
    bad = [k for k in t if k not in cur]
    if bad:
        raise ApiError(422, "invalid_threshold", f"Unknown thresholds: {bad}")
    for k, v in t.items():
        db.execute("INSERT INTO config_thresholds(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, float(v)))
    db.audit(role, "thresholds_changed", t)
    return db.get_thresholds()


def review_list(status: str = "pending", limit: int = 100) -> list[dict]:
    rows = db.query("SELECT * FROM mapping_review WHERE status=? ORDER BY n_postings DESC LIMIT ?", (status, limit))
    names = {t[0]: t[1] for t in TRADES}
    for r in rows:
        r["suggested_trade_name"] = names.get(r["suggested_trade"])
    return rows


def review_resolve(rid: int, action: str, trade_code: str | None, role: str) -> dict:
    r = db.query("SELECT * FROM mapping_review WHERE id=?", (rid,))
    if not r:
        raise ApiError(404, "not_found", "Review item not found")
    valid = {t[0] for t in TRADES}
    if action == "approve":
        tc, st = r[0]["suggested_trade"], "approved"
    elif action == "reassign":
        if trade_code not in valid:
            raise ApiError(422, "invalid_trade", "Unknown trade_code")
        tc, st = trade_code, "reassigned"
    elif action == "reject":
        tc, st = "OTHER", "rejected"
    else:
        raise ApiError(422, "invalid_action", "action must be approve|reassign|reject")
    db.execute("UPDATE mapping_review SET status=?, resolved_trade=?, updated=? WHERE id=?", (st, tc, db.now(), rid))
    db.audit(role, "mapping_review", {"id": rid, "action": action, "trade": tc})
    return {"id": rid, "status": st, "resolved_trade": tc, "note": "Applied on the next pipeline run."}


def scenarios() -> list[dict]:
    p = RAW_DIR / "scenarios.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
