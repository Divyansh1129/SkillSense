# SkillSense

SkillSense is a labour market intelligence dashboard that helps skilling planners compare job demand with training capacity. It highlights possible skill shortages and surpluses, forecasts future gaps, and supports training-seat planning.

> **Demo limitation:** All data in this project is simulated. Results demonstrate the system’s features and are not real labour market findings. Source labels and classification codes are illustrative and must be verified before real use.

## Features

- Explore demand and training supply by state, district, sector, and trade.
- View forecasts up to 12 months ahead, with uncertainty ranges.
- Rank skill shortages and oversupply areas.
- See early warnings for acute shortages, emerging demand, oversupply risk, and low-confidence data.
- Inspect demand contributors and confidence indicators.
- Try training-seat changes and review suggested targets within a seat budget.
- Export forecasts and target recommendations.
- Use the dashboard in English, Hindi, or Marathi, with high contrast and adjustable text size.
- Switch between Viewer, Analyst, and Admin roles. The role selector is a custom menu with keyboard support.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Plotly
- **Backend:** FastAPI, SQLite, pandas
- **Analysis:** Demand-index calculation, skill mapping, forecasting, gap and severity scoring

## Run locally

Requirements: Python 3.11+ and Node.js 18+.

### 1. Start the backend

```bash
cd backend
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies, generate demo data, and start the API:

```bash
pip install -r requirements.txt
python -m scripts.setup_demo
uvicorn app.main:app --reload --port 8000
```

The API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Demo roles

The role selector is in the dashboard header.

| Role | Example permissions |
|---|---|
| Viewer | View dashboard data |
| Analyst | Run what-if scenarios, acknowledge alerts, and review mappings |
| Admin | Change weights and thresholds, and run the pipeline |

The development API keys are defined in `backend/.env.example`. They are for local demonstration and should be changed before any real deployment.

## Dashboard pages

- **Overview:** Summary metrics with drill-down from state to district and trade.
- **Trade Explorer:** Demand and supply history, forecasts, gap charts, and demand contributors.
- **Rankings:** Trades and locations ordered by gap severity.
- **Early Warnings:** Alerts with severity, reasons, and suggested actions.
- **Workbench:** Test seat changes and generate target recommendations.
- **Methodology & Data:** Review the analysis approach, sources, and limitations.
- **Admin:** Review uncertain job-title mappings, adjust settings, and run the pipeline.

## Data flow

```text
Simulated source data
        ↓
Ingestion, validation, and deduplication
        ↓
Job-title mapping and demand index
        ↓
Supply estimates and forecasts
        ↓
Gap analysis, severity rankings, and alerts
        ↓
FastAPI endpoints and dashboard
```

The pipeline creates versioned runs so forecast and export results can be traced back to their source run.

## Forecasting and methodology

SkillSense combines job postings, hiring signals, employment estimates, and worker registrations into a demand index. It compares estimated demand with training supply, then calculates gaps and severity scores. Forecasts use a harmonic trend baseline and a LightGBM model ensemble, with uncertainty ranges.

See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for details and [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for documented interfaces for connecting real data feeds.

## Build and type check

From the `frontend` directory:

```bash
npm run typecheck
npm run build
```

## Known limitations

- The included data is simulated, so reported accuracy applies only to the demo dataset.
- Real data-feed integrations are documented but not connected.
- Development API keys are static and are not production authentication.
- Some geographic labels, skill codes, and assumptions are illustrative.
- Forecasts are decision support and should be reviewed by planners.