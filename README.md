# SkillSense – Labour Market Intelligence System (SIH 2026, MSDE)

Demand–supply gap forecasting for skilling planners: ingestion → NLP mapping → demand index → hierarchical forecast → gap/severity/early-warning → API + React dashboard (English / हिन्दी / मराठी).

> **ALL DATA IS SIMULATED.** Every screen shows a "Demo data (simulated)" banner. NCO codes, NSQF levels, SSC labels and district codes are illustrative and must be verified before any real use. Real feeds (NCS, e-Shram, PLFS, Skill India Digital) are documented connector interfaces with simulated implementations.

## Quick start (no Docker)

**Needs:** Python 3.11+ and Node 18+.

```bash
# 1) Backend  (Windows: use `python -m venv .venv` then `.venv\Scripts\activate`)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.setup_demo          # generates simulated data + runs the whole pipeline (~1 min)
uvicorn app.main:app --reload --port 8000

# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                           # open http://localhost:5173
```

API docs (Swagger): http://localhost:8000/docs. Dev API keys (change via `backend/.env`, see `.env.example`):
`dev-viewer-key`, `dev-analyst-key`, `dev-admin-key`. The dashboard has a **Role** switcher in the header (what-if, acknowledge and mapping review need analyst; weights/thresholds/pipeline need admin).

Tests: `cd backend && pytest -q`  ·  Re-run pipeline only: `python -m scripts.run_pipeline` (idempotent; every run is versioned).
Optional better multilingual mapping: `pip install sentence-transformers` and set `USE_EMBEDDINGS=1`.

## Architecture
```
Connectors → 1 Ingestion (validate, dedup, snapshot) → 2 NLP mapping (fuzzy[+embeddings], confidence, review queue)
 → 3 Demand index (robust z, configurable weights, explainability) + supply model
 → 4 Forecast (harmonic + LightGBM ensemble, intervals, rolling backtest, reconciliation)
 → 5 Gap, severity, flags, what-if, target recommender → 6 FastAPI (RBAC, exports) → React dashboard
                SQLite (plain SQL; Postgres-ready) + run log + audit log
```
Code map: `backend/app/{ingestion,mapping,index,forecast,gap,pipeline,services,main}.py`, `backend/scripts/generate_data.py`, `frontend/src/pages/*`.

## Requirement traceability
| Problem-statement requirement | Module | Endpoint | Dashboard page |
|---|---|---|---|
| 1. Aggregate & normalise demand signals (portals, hiring, NCO/NSQF postings, e-Shram/NCS) | `ingestion.py`, `mapping.py`, `index.py` | `/meta/sources`, `/mapping/review`, `/demand-index/{d}/{t}` | Methodology & Data, Admin (review queue), Explorer (contributions) |
| 2. Cross-reference demand with training capacity/seats by sector, trade, district | `index.py::compute_supply`, `gap.py` | `/gap` | Overview, Explorer |
| 3. Forward-looking gap forecasts at sector & district level, refreshed periodically | `forecast.py`, `pipeline.py`, APScheduler (monthly) | `/forecast`, `/timeseries`, `/pipeline/run`, `/meta/runs` | Explorer, Admin |
| 4. Rank trades/geographies by severity of over/undersupply | `gap.py::severity_score` | `/ranking` | Rankings |
| 5. Interactive dashboard with national→district drill-down | React app | `/overview` | Overview (tile drill-down) |
| Documented methodology for the combined index | `docs/METHODOLOGY.md`, in-app page | `/config/weights`, `/meta/model-quality` | Methodology & Data |
| Early-warning flags | `gap.py::build_alerts` | `/alerts`, `/alerts/{id}/ack` | Early Warnings |
| API/export layer for target-setting | `services.py`, `main.py` | `/export/forecast.{csv,xlsx,json}`, `/export/targets.csv`, `/whatif`, `/recommend-targets` | Rankings, Workbench |
| Multilingual, accessible UI | `i18n.ts`, `locales/*.json`, `components/ui.tsx` | – | All pages (EN/HI/MR, contrast, text size, table view, keyboard) |

## 5-minute demo script (planted scenarios)
1. **Overview** – note the Demo banner; click *Maharashtra* → tiles by district; KPIs show EV Charging / Solar as top shortage and Consumer-Electronics Repair as top oversupply.
2. **Early Warnings** – *Kanpur Nagar · Electrician (Domestic)*: critical APPROACHING_SATURATION (seats rising ~14%, demand flat). *Pune · Solar PV Installer*: critical ACUTE_SHORTAGE (demand surging, few seats). *Nagpur · EV Charging*: EMERGING_DEMAND.
3. **Trade Explorer** (Pune, Solar PV Installer) – history + forecast with 80/95% bands, demand vs supply, "why this score" contribution chart, *View as table*.
4. **Explorer → Gautam Buddh Nagar · Field Technician (Electronics)** – sudden demand jump from Apr 2026 (structural break). **Gadchiroli** – sparse data → low-confidence flags and reduced confidence. **Bahraich** – e-Shram feed missing for 12 months (weights re-normalised, lower confidence).
5. **Workbench** – Kanpur/Electrician: slide seats −40% and watch gap/severity change; *Recommend targets* for Uttar Pradesh × Renewable with a seat budget; download target CSV.
6. **Switch language** to हिन्दी/मराठी (alert reasons/actions are template-translated); toggle high contrast and text size.
7. **Admin** – change source weights → index and forecasts recompute as a new versioned run; review low-confidence job titles.
8. **Methodology** – weights, source freshness, mapping accuracy, backtest metrics and limitations.

## Assumptions & known limitations (honest list)
- Simulated data; accuracy figures describe the synthetic data only (backtest: ensemble WAPE ≈ 11% vs ≈ 15–16% seasonal-naive; interval coverage ≈ 81% / 95% on holdout origins).
- **Deviations from the brief (for speed, per request):** SQLite instead of PostgreSQL/Alembic (schema is plain SQL in `db.py`); no Docker; harmonic damped-trend baseline instead of Prophet/statsforecast; top-down forecast-proportion reconciliation instead of MinT; fuzzy matching (RapidFuzz) by default with optional multilingual embeddings; near-duplicate detection uses string similarity (not embeddings); tile map instead of a GeoJSON choropleth (boundary files are not bundled offline); Vitest UI tests not included.
- Model-selection weights are calibrated on origins ≤ 24 and evaluated on 27/30 (small look-ahead in selection only). Backtests are not run on the reconciled forecasts.
- Planted "GBN Field Technician" jump (last 6 months of data) is visible in history but forecast/flag sensitivity to it is modest by design of the robust index.
- Auth is a documented dev implementation (static API keys); use a real IdP in production. Only aggregate, non-personal data is used; actions are written to `audit_log`.
