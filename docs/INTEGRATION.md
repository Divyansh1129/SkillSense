# Plugging in real feeds
Each source is a class in `backend/app/ingestion.py` implementing `fetch() -> DataFrame` with a fixed column schema (Pandera). To go live, subclass the connector and override `fetch()`:
- **NCS postings**: columns `posting_id,title,employer,district_raw,portal,posted_date` (see the commented `LiveNCS` stub).
- **PLFS**: `month,district_code,trade_code,employment_level` (district estimates need small-area modelling).
- **e-Shram**: aggregate counts only: `month,district_code,trade_code,registrations`.
- **Hiring signals**: `month,district_code,trade_code,nco_code,hiring_index`.
- **Skill India Digital / PMKVY seats**: `cycle,centre_id,district_code,trade_code,seats,enrolment_rate,completion_rate,placement_ready_rate`.
Replace the `CONNECTORS` list entries, keep schemas, run `python -m scripts.run_pipeline`.

# Feeding target-setting workflows
`GET /api/v1/export/forecast.csv|xlsx|json` columns: `state, district, sector, trade, nco_code, nsqf_level, forecast_demand, supply, gap, severity, flag, suggested_seats, source_run_id, generated_at`. `GET /export/targets.csv` lists current vs suggested seats. `POST /recommend-targets` supports a seat budget and max-change band. Every export carries `source_run_id` for traceability; runs are versioned in `/meta/runs`.
