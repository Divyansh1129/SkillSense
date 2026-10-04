"""FastAPI application (Module 6). Docs at /docs (Swagger) and /openapi.json.
Auth: send `X-API-Key` (or ?api_key= for file downloads). Roles: viewer < analyst < admin (dev keys in .env.example)."""
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db, services as sv
from .config import API_KEYS, CORS_ORIGINS, DEMO_DATA, ENABLE_SCHEDULER
from .pipeline import run_pipeline, seed_taxonomy, start_run

RANK = {"viewer": 1, "analyst": 2, "admin": 3}
scheduler = None


def monthly_refresh():
    run_pipeline(trigger="scheduler", note="monthly refresh")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    db.init_schema()
    seed_taxonomy()
    if ENABLE_SCHEDULER:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler = BackgroundScheduler()
            scheduler.add_job(monthly_refresh, "cron", day=1, hour=2, id="monthly_refresh")
            scheduler.start()
        except Exception:  # pragma: no cover
            scheduler = None
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="SkillSense LMIS API", version="1.0.0", lifespan=lifespan,
              description="Labour Market Intelligence System. **All data is simulated (demo).**")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def auth(min_role: str):
    def dep(x_api_key: Optional[str] = Header(default=None), api_key: Optional[str] = Query(default=None)) -> str:
        role = API_KEYS.get(x_api_key or api_key or "")
        if not role:
            raise sv.ApiError(401, "unauthorized", "Missing or invalid API key")
        if RANK[role] < RANK[min_role]:
            raise sv.ApiError(403, "forbidden", f"Requires role '{min_role}' (you are '{role}')")
        return role
    return dep


viewer, analyst, admin = Depends(auth("viewer")), Depends(auth("analyst")), Depends(auth("admin"))


def _err(status, code, msg):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": msg}})


@app.exception_handler(sv.ApiError)
async def _api_err(_: Request, e: sv.ApiError):
    return _err(e.status, e.code, e.message)


@app.exception_handler(StarletteHTTPException)
async def _http_err(_: Request, e: StarletteHTTPException):
    return _err(e.status_code, "http_error", str(e.detail))


@app.exception_handler(RequestValidationError)
async def _val_err(_: Request, e: RequestValidationError):
    return _err(422, "validation_error", "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))


class Scope(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    sector: Optional[str] = None
    trade: Optional[str] = None


class WhatIf(Scope):
    mode: Literal["pct", "abs"] = "pct"
    value: float = Field(..., description="percent change or absolute seat change")
    horizon: Literal[6, 12] = 12


class Recommend(Scope):
    budget: Optional[float] = Field(None, description="optional total seat budget for the scope")
    max_change_pct: float = Field(50, ge=0, le=300)


class Ack(BaseModel):
    status: Literal["acknowledged", "dismissed", "open"]
    note: str = ""


class Review(BaseModel):
    action: Literal["approve", "reassign", "reject"]
    trade_code: Optional[str] = None


class PipelineReq(BaseModel):
    from_stage: Literal["ingest", "index", "forecast"] = "ingest"
    note: str = ""


P = "/api/v1"


def _validate_horizon(horizon: int) -> None:
    if horizon not in (6, 12):
        raise sv.ApiError(422, "validation_error", "horizon must be 6 or 12")


@app.get(f"{P}/health", tags=["meta"])
def health():
    return {"status": "ok", "demo_data": DEMO_DATA}


@app.get(f"{P}/meta/taxonomy", tags=["meta"], dependencies=[viewer])
def taxonomy():
    return sv.taxonomy()


@app.get(f"{P}/meta/sources", tags=["meta"], dependencies=[viewer])
def meta_sources():
    return sv.meta_sources()


@app.get(f"{P}/meta/model-quality", tags=["meta"], dependencies=[viewer])
def model_quality(run_id: Optional[str] = None):
    return sv.model_quality(run_id)


@app.get(f"{P}/meta/mapping-quality", tags=["meta"], dependencies=[viewer])
def mapping_quality():
    return sv.mapping_quality()


@app.get(f"{P}/meta/runs", tags=["meta"], dependencies=[viewer])
def runs():
    return sv.runs()


@app.get(f"{P}/meta/scenarios", tags=["meta"], dependencies=[viewer])
def scenarios():
    return sv.scenarios()


@app.get(f"{P}/overview", tags=["dashboard"], dependencies=[viewer])
def overview(horizon: int = Query(12, description="Forecast horizon in months (6 or 12)"), state: Optional[str] = None, sector: Optional[str] = None, run_id: Optional[str] = None):
    _validate_horizon(horizon)
    return sv.overview(horizon, run_id, state=state, sector=sector)


@app.get(f"{P}/forecast", tags=["forecast"], dependencies=[viewer])
def forecast(state: Optional[str] = None, district: Optional[str] = None, sector: Optional[str] = None, trade: Optional[str] = None,
             horizon: int = Query(12, ge=1, le=12), run_id: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=2000)):
    return sv.forecast_rows(run_id, horizon, page, page_size, state=state, district=district, sector=sector, trade=trade)


@app.get(f"{P}/timeseries/{{district}}/{{trade}}", tags=["forecast"], dependencies=[viewer])
def timeseries(district: str, trade: str, run_id: Optional[str] = None):
    return sv.timeseries(district, trade, run_id)


@app.get(f"{P}/gap", tags=["gap"], dependencies=[viewer])
def gap(state: Optional[str] = None, district: Optional[str] = None, sector: Optional[str] = None, trade: Optional[str] = None,
        horizon: int = Query(12, description="Forecast horizon in months (6 or 12)"), run_id: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
    _validate_horizon(horizon)
    return sv.gap_page(horizon, page, page_size, run_id, state=state, district=district, sector=sector, trade=trade)


@app.get(f"{P}/ranking", tags=["gap"], dependencies=[viewer])
def ranking(type: Literal["oversupply", "shortage"] = "shortage", level: Literal["state", "district", "trade"] = "trade", top: int = Query(10, ge=1, le=200),
            horizon: int = Query(12, description="Forecast horizon in months (6 or 12)"), state: Optional[str] = None, sector: Optional[str] = None, district: Optional[str] = None, run_id: Optional[str] = None):
    _validate_horizon(horizon)
    return sv.ranking(type, level, top, horizon, run_id, state=state, sector=sector, district=district)


@app.get(f"{P}/alerts", tags=["alerts"], dependencies=[viewer])
def alerts(level: Optional[Literal["watch", "warning", "critical"]] = None, state: Optional[str] = None, sector: Optional[str] = None,
           flag: Optional[str] = None, district: Optional[str] = None, include_dismissed: bool = False, run_id: Optional[str] = None):
    items = sv.alerts_list(run_id, level, state, sector, flag, district, include_dismissed)
    return {"total": len(items), "items": items}


@app.post(f"{P}/alerts/{{alert_id}}/ack", tags=["alerts"])
def ack(alert_id: int, body: Ack, role: str = Depends(auth("analyst"))):
    return sv.ack_alert(alert_id, body.status, body.note, role)


@app.get(f"{P}/demand-index/{{district}}/{{trade}}", tags=["demand-index"], dependencies=[viewer])
def demand_index(district: str, trade: str):
    return sv.demand_index_series(district, trade)


@app.post(f"{P}/whatif", tags=["planner"], dependencies=[analyst])
def whatif(body: WhatIf):
    return sv.run_whatif(body.model_dump())


@app.post(f"{P}/recommend-targets", tags=["planner"], dependencies=[analyst])
def recommend(body: Recommend):
    return sv.run_recommend(body.model_dump())


@app.get(f"{P}/export/forecast.{{fmt}}", tags=["export"], dependencies=[viewer])
def export_forecast(fmt: Literal["csv", "xlsx", "json"], state: Optional[str] = None, district: Optional[str] = None,
                    sector: Optional[str] = None, trade: Optional[str] = None, run_id: Optional[str] = None):
    data, mt, name = sv.export_bytes(fmt, run_id=run_id, state=state, district=district, sector=sector, trade=trade)
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename={name}"})


@app.get(f"{P}/export/targets.csv", tags=["export"], dependencies=[viewer])
def export_targets(state: Optional[str] = None, district: Optional[str] = None, sector: Optional[str] = None, trade: Optional[str] = None):
    return Response(sv.targets_csv(state=state, district=district, sector=sector, trade=trade), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=targets.csv"})


@app.post(f"{P}/pipeline/run", tags=["admin"], status_code=202)
def pipeline_run(body: PipelineReq, bg: BackgroundTasks, role: str = Depends(auth("admin"))):
    if db.query("SELECT 1 FROM pipeline_runs WHERE status='running' LIMIT 1"):
        raise sv.ApiError(409, "already_running", "A pipeline run is already in progress")
    rid = start_run("api", body.from_stage, body.note)
    db.audit(role, "pipeline_run", {"run_id": rid, "from_stage": body.from_stage})
    bg.add_task(_run_bg, rid, body.from_stage)
    return {"run_id": rid, "status": "started"}


def _run_bg(rid: str, stage: str):
    try:
        run_pipeline(run_id=rid, from_stage=stage)
    except Exception:  # status already recorded in pipeline_runs
        pass


@app.get(f"{P}/pipeline/status", tags=["admin"], dependencies=[viewer])
def pipeline_status():
    r = db.query("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1")
    return r[0] if r else {"status": "none"}


@app.get(f"{P}/config/weights", tags=["admin"], dependencies=[viewer])
def weights():
    return sv.get_weights()


@app.put(f"{P}/config/weights", tags=["admin"], status_code=202)
def set_weights(body: dict[str, float], bg: BackgroundTasks, role: str = Depends(auth("admin"))):
    out = sv.put_weights(body, role)
    if db.query("SELECT 1 FROM pipeline_runs WHERE status='running' LIMIT 1"):
        return {**out, "run_id": None, "note": "Saved; a run is in progress - re-run the pipeline afterwards."}
    rid = start_run("weights_changed", "index", "weights changed")
    bg.add_task(_run_bg, rid, "index")
    return {**out, "run_id": rid, "status": "recomputing"}


@app.get(f"{P}/config/thresholds", tags=["admin"], dependencies=[analyst])
def thresholds():
    return db.get_thresholds()


@app.put(f"{P}/config/thresholds", tags=["admin"])
def set_thresholds(body: dict[str, float], role: str = Depends(auth("admin"))):
    return sv.put_thresholds(body, role)


@app.get(f"{P}/mapping/review", tags=["mapping"], dependencies=[analyst])
def mapping_review(status: str = "pending", limit: int = Query(100, le=500)):
    return {"items": sv.review_list(status, limit)}


@app.post(f"{P}/mapping/review/{{rid}}", tags=["mapping"])
def mapping_resolve(rid: int, body: Review, role: str = Depends(auth("analyst"))):
    return sv.review_resolve(rid, body.action, body.trade_code, role)
