"""Thin SQLite helpers (pandas friendly). Schema is plain SQL so a PostgreSQL swap only needs this file."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pandas as pd

from .config import DB_PATH, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS


def connect(row: bool = False) -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
    if row:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def query(sql: str, params=()) -> list[dict]:
    with closing(connect(row=True)) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def qdf(sql: str, params=()) -> pd.DataFrame:
    with closing(connect()) as c:
        return pd.read_sql_query(sql, c, params=params)


def execute(sql: str, params=()) -> None:
    with closing(connect()) as c:
        c.execute(sql, params)
        c.commit()


def write_df(df: pd.DataFrame, table: str, if_exists: str = "replace") -> None:
    with closing(connect()) as c:
        df.to_sql(table, c, if_exists=if_exists, index=False)
        c.commit()


def table_exists(name: str) -> bool:
    return bool(query("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    return "R" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def audit(role: str, action: str, detail="") -> None:
    execute("INSERT INTO audit_log(ts, role, action, detail) VALUES (?,?,?,?)",
            (now(), role, action, detail if isinstance(detail, str) else json.dumps(detail)))


SCHEMA = """
CREATE TABLE IF NOT EXISTS config_weights (source TEXT PRIMARY KEY, weight REAL NOT NULL);
CREATE TABLE IF NOT EXISTS config_thresholds (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mapping_review (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title_norm TEXT UNIQUE, sample_title TEXT, n_postings INTEGER,
  suggested_trade TEXT, confidence REAL, status TEXT DEFAULT 'pending', resolved_trade TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS alert_ack (alert_key TEXT PRIMARY KEY, status TEXT, note TEXT, ts TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id TEXT PRIMARY KEY, started TEXT, finished TEXT, status TEXT, trigger TEXT, from_stage TEXT,
  note TEXT, stage TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, role TEXT, action TEXT, detail TEXT);
"""


def init_schema() -> None:
    with closing(connect()) as c:
        c.executescript(SCHEMA)
        for k, v in DEFAULT_WEIGHTS.items():
            c.execute("INSERT OR IGNORE INTO config_weights VALUES (?,?)", (k, v))
        for k, v in DEFAULT_THRESHOLDS.items():
            c.execute("INSERT OR IGNORE INTO config_thresholds VALUES (?,?)", (k, v))
        c.commit()


def get_weights() -> dict:
    return {r["source"]: r["weight"] for r in query("SELECT * FROM config_weights")}


def get_thresholds() -> dict:
    t = dict(DEFAULT_THRESHOLDS)
    t.update({r["key"]: r["value"] for r in query("SELECT * FROM config_thresholds")})
    return t
