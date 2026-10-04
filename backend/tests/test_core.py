import numpy as np
import pandas as pd
import pytest

from app.gap import recommend_seats, severity_score, whatif
from app.mapping import map_titles, normalise_district, normalise_text


def test_normalise_keeps_devanagari():
    assert "इलेक्ट्रीशियन" in normalise_text("URGENT इलेक्ट्रीशियन required!!")


def test_mapping_confidence_and_review():
    m = map_titles(pd.Series(["Solar PV Installer", "solar pv instaler", "Accountant"]), {}, 0.72).set_index("title_norm")
    assert m.loc["solar pv installer", "trade_code"] == "REN01"
    assert m.loc["solar pv installer", "status"] == "auto"
    assert m.loc["accountant", "status"] == "review"


def test_mapping_override_feedback():
    m = map_titles(pd.Series(["Accountant"]), {"accountant": "OTHER"}, 0.72)
    assert m.iloc[0]["status"] == "excluded"


def test_district_fuzzy():
    assert normalise_district("Lucknow, UP") == "UP-LKO"
    assert normalise_district("लखनऊ") == "UP-LKO"
    assert normalise_district("Unknownville") is None


def test_severity_bounds_and_direction():
    s = severity_score([0.6, -0.6, 0.0], [0.3, -0.3, 0], [0, 0.2, 0], [0.4, 0.4, 0.4], [1, 1, 1])
    assert (s >= 0).all() and (s <= 100).all()
    assert s[0] > s[2] and s[1] > s[2]


def test_recommend_respects_bounds_and_budget():
    D, seats, a, carry = [100, 100], [100, 400], [0.5, 0.5], [0, 0]
    x = recommend_seats(D, seats, a, carry, 0.5)
    assert x[0] == 150 and x[1] == 200            # capped at +-50%
    xb = recommend_seats([300, 300], [100, 100], [0.4, 0.5], [0, 0], 1.0, budget=300)
    assert xb.sum() <= 300 + 1


def test_whatif_reduces_oversupply():
    g = pd.DataFrame({"seats": [1000.0], "seats_prev": [900.0], "a_rate": [0.5], "carry": [50.0], "demand": [300.0], "demand_growth": [0.0],
                      "width95": [0.4], "confidence": [1.0]})
    r = whatif(g, "pct", -50, 1.0)
    assert r.loc[0, "seats_new"] == 500 and r.loc[0, "gap_new"] > 0 - 1e9
    assert abs(r.loc[0, "gap_pct_new"]) < 1.5


@pytest.fixture(scope="session")
def pipeline_run():
    from app.pipeline import run_pipeline
    from scripts.generate_data import main as gen
    gen()
    return run_pipeline(trigger="test")


def test_pipeline_smoke(pipeline_run):
    from app import db, services as sv
    assert pipeline_run.startswith("R")
    g = sv.gaps_df(12)
    assert len(g) == 360 and g["severity"].between(0, 100).all()
    assert not db.qdf("SELECT * FROM alerts").empty
    fc = db.qdf("SELECT * FROM forecasts")
    assert (fc["lo95"] <= fc["lo80"] + 1e-9).all() and (fc["hi80"] <= fc["hi95"] + 1e-9).all()
    # hierarchical coherence: sum of districts per state-trade is finite & positive
    assert (fc.groupby(["run_id", "month"])["yhat"].sum() > 0).all()


def test_idempotent_rerun(pipeline_run):
    from app.pipeline import run_pipeline
    from app import services as sv
    before = sv.gaps_df(12)["demand"].sum()
    run_pipeline(from_stage="index", trigger="test")
    assert abs(sv.gaps_df(12)["demand"].sum() - before) < 1e-6


def test_export_columns(pipeline_run):
    from app import services as sv
    df = sv.export_df()
    for c in ["state", "district", "sector", "trade", "nco_code", "nsqf_level", "forecast_demand", "supply", "gap", "severity", "flag", "suggested_seats", "source_run_id", "generated_at"]:
        assert c in df.columns


def test_api_contract(pipeline_run):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/overview").status_code == 401
        h = {"X-API-Key": "dev-viewer-key"}
        assert c.get("/api/v1/overview", headers=h).status_code == 200
        assert c.get("/api/v1/gap?page_size=5", headers=h).json()["page_size"] == 5
        r = c.post("/api/v1/whatif", headers=h, json={"value": 10})
        assert r.status_code == 403 and "error" in r.json()
        a = {"X-API-Key": "dev-analyst-key"}
        assert c.post("/api/v1/whatif", headers=a, json={"district": "UP-KNP", "trade": "ELE01", "value": -20}).status_code == 200
        assert c.get("/api/v1/export/forecast.csv?api_key=dev-viewer-key").status_code == 200
