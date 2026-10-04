"""One command demo setup: generate synthetic data + run the whole pipeline.   python -m scripts.setup_demo"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.pipeline import run_pipeline  # noqa: E402
from scripts.generate_data import main as generate  # noqa: E402

if __name__ == "__main__":
    t = time.time()
    generate()
    rid = run_pipeline(trigger="setup")
    print(f"done in {time.time() - t:.0f}s - run {rid}. Now start the API:  uvicorn app.main:app --reload --port 8000")
