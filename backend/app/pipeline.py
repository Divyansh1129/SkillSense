"""Pipeline orchestrator: ingest -> index -> forecast -> gap. Idempotent and versioned (every run gets a run_id; forecasts,
gaps, alerts and backtests are kept per run so planners can compare 'forecast made in month X')."""
import json
import traceback

import pandas as pd

from . import db
from .config import RAW_DIR
from .forecast import run_forecast
from .gap import build_alerts, compute_gaps
from .index import build_panel, compute_demand_index, compute_supply
from .ingestion import run_ingestion
from .mapping import evaluate_mapping, map_titles
from .taxonomy import DISTRICTS, SECTORS, STATES, TRADES, seed_rows

STAGES = ["ingest", "index", "forecast", "gap"]
KEEP_RUNS = 12


def seed_taxonomy() -> None:
    db.write_df(pd.DataFrame(STATES, columns=["code", "name"]), "states")
    db.write_df(pd.DataFrame([(d[0], d[1], d[2], d[3], d[4]) for d in DISTRICTS], columns=["code", "name", "state", "type", "size_factor"]), "districts")
    db.write_df(pd.DataFrame(SECTORS, columns=["code", "name"]), "sectors")
    db.write_df(pd.DataFrame([(t[0], t[1], t[2], t[3], t[4], t[5], t[6]) for t in TRADES],
                             columns=["code", "name", "sector", "nco_code", "nsqf_level", "ssc", "turnover_rate"]), "trades")
    db.write_df(pd.DataFrame(seed_rows(), columns=["phrase", "trade_code"]), "taxonomy_seeds")


def _set_stage(run_id: str, stage: str) -> None:
    db.execute("UPDATE pipeline_runs SET stage=? WHERE run_id=?", (stage, run_id))


def start_run(trigger: str = "manual", from_stage: str = "ingest", note: str = "") -> str:
    db.init_schema()
    run_id = db.new_run_id()
    db.execute("INSERT INTO pipeline_runs(run_id, started, status, trigger, from_stage, note, stage) VALUES (?,?,?,?,?,?,?)",
               (run_id, db.now(), "running", trigger, from_stage, note, "queued"))
    return run_id


def _upsert_review(mapped: pd.DataFrame, postings: pd.DataFrame) -> None:
    cnt = postings.groupby("title_norm").size().rename("n")
    sample = postings.groupby("title_norm")["title"].first().rename("sample")
    rv = mapped[mapped["status"] == "review"].set_index("title_norm").join(cnt).join(sample).sort_values("n", ascending=False).head(300)
    for tn, r in rv.iterrows():
        db.execute("""INSERT INTO mapping_review(title_norm, sample_title, n_postings, suggested_trade, confidence, status, updated)
                      VALUES (?,?,?,?,?,'pending',?)
                      ON CONFLICT(title_norm) DO UPDATE SET n_postings=excluded.n_postings, suggested_trade=excluded.suggested_trade,
                      confidence=excluded.confidence, updated=excluded.updated WHERE mapping_review.status='pending'""",
                   (tn, r["sample"], int(r["n"]), r["trade_code"], float(r["confidence"]), db.now()))


def _stage_ingest(run_id: str, thr: dict) -> None:
    ing = run_ingestion(run_id, thr)
    fr = ing["frames"]
    post = fr["postings"]
    overrides = {r["title_norm"]: r["resolved_trade"] for r in db.query(
        "SELECT title_norm, resolved_trade FROM mapping_review WHERE status IN ('approved','reassigned','rejected') AND resolved_trade IS NOT NULL")}
    mapped = map_titles(post["title"], overrides, thr["mapping_threshold"])
    post = post.merge(mapped[["title_norm", "trade_code", "confidence", "status"]], on="title_norm", how="left")
    clean = post[post["status"].isin(["auto", "override"])]
    _upsert_review(mapped, post)
    truth_path = RAW_DIR / "title_truth.csv"
    if truth_path.exists():
        q = evaluate_mapping(mapped, post, pd.read_csv(truth_path))
        db.write_df(pd.DataFrame([{"run_id": run_id, "metrics": json.dumps(q)}]), "mapping_quality")
    db.write_df(clean[["posting_id", "month", "district_code", "trade_code", "title", "confidence"]], "postings_clean")
    for name, tbl in (("hiring", "hiring_signals"), ("plfs", "plfs_stats"), ("eshram", "eshram_stats"), ("seats", "training_seats")):
        db.write_df(fr[name], tbl)
    meta = pd.DataFrame(ing["metrics"])
    meta["mapped_share"] = len(clean) / max(len(post), 1)
    db.write_df(meta, "source_meta")
    db.audit("system", "ingest", {"run_id": run_id, "postings_clean": len(clean)})


def _stage_index(run_id: str, thr: dict) -> None:
    frames = {"postings_clean": db.qdf("SELECT * FROM postings_clean"), "hiring": db.qdf("SELECT * FROM hiring_signals"),
              "plfs": db.qdf("SELECT * FROM plfs_stats"), "eshram": db.qdf("SELECT * FROM eshram_stats")}
    panel = build_panel(frames)
    di, sq = compute_demand_index(panel, db.get_weights(), run_id)
    db.write_df(di, "demand_index")
    db.write_df(sq, "series_quality")
    sup = compute_supply(db.qdf("SELECT * FROM training_seats"), thr["carryover_retention"], run_id)
    db.write_df(sup, "supply_estimate")


def _stage_forecast(run_id: str) -> None:
    out = run_forecast(db.qdf("SELECT * FROM demand_index"), db.qdf("SELECT * FROM series_quality"), run_id)
    db.write_df(out["forecast"], "forecasts", "append")
    db.write_df(out["backtests"], "backtests", "append")
    info = out["info"]
    db.write_df(pd.DataFrame([{**{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in info.items()}, "generated_at": db.now()}]), "forecast_runs", "append")


def _stage_gap(run_id: str, thr: dict) -> None:
    fc = db.qdf("SELECT * FROM forecasts WHERE run_id=?", (run_id,))
    gaps = compute_gaps(fc, db.qdf("SELECT * FROM supply_estimate"), db.qdf("SELECT * FROM demand_index"),
                        db.qdf("SELECT * FROM series_quality"), thr, run_id)
    gaps["generated_at"] = db.now()
    db.write_df(gaps, "gaps", "append")
    db.write_df(build_alerts(gaps, thr, run_id), "alerts", "append")


def _retain() -> None:
    keep = [r["run_id"] for r in db.query("SELECT run_id FROM pipeline_runs WHERE status='success' ORDER BY run_id DESC LIMIT ?", (KEEP_RUNS,))]
    if not keep:
        return
    q = ",".join("?" * len(keep))
    for t in ("forecasts", "gaps", "alerts", "backtests", "forecast_runs"):
        if db.table_exists(t):
            db.execute(f"DELETE FROM {t} WHERE run_id NOT IN ({q})", tuple(keep))


def run_pipeline(run_id: str | None = None, from_stage: str = "ingest", trigger: str = "manual", note: str = "") -> str:
    """Run stages from `from_stage` to the end. Safe to call repeatedly."""
    db.init_schema()
    if run_id is None:
        run_id = start_run(trigger, from_stage, note)
    thr = db.get_thresholds()
    try:
        seed_taxonomy()
        start = STAGES.index(from_stage)
        if start <= 0:
            _set_stage(run_id, "ingest")
            _stage_ingest(run_id, thr)
        if start <= 1:
            _set_stage(run_id, "index")
            _stage_index(run_id, thr)
        if start <= 2:
            _set_stage(run_id, "forecast")
            _stage_forecast(run_id)
        _set_stage(run_id, "gap")
        _stage_gap(run_id, thr)
        db.execute("UPDATE pipeline_runs SET status='success', finished=?, stage='done' WHERE run_id=?", (db.now(), run_id))
        _retain()
    except Exception:
        db.execute("UPDATE pipeline_runs SET status='failed', finished=?, error=? WHERE run_id=?", (db.now(), traceback.format_exc()[-2000:], run_id))
        raise
    return run_id
