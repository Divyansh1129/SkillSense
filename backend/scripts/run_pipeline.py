"""Run the full pipeline once:  python -m scripts.run_pipeline [ingest|index|forecast]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.pipeline import run_pipeline  # noqa: E402

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    rid = run_pipeline(from_stage=stage, trigger="cli")
    print("pipeline finished:", rid)
