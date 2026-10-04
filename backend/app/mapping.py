"""Module 2 - map free-text job titles (English / Hindi / Marathi transliteration / mixed) to trade -> NCO -> NSQF -> SSC.

Method: normalise text, score against seeded taxonomy phrases with fuzzy matching (RapidFuzz WRatio; difflib fallback),
optionally blended with multilingual sentence embeddings (USE_EMBEDDINGS=1). Confidence combines the top score and the
margin to the runner-up trade. Below threshold -> "needs review" queue; approved reviews become overrides (feedback).
"""
import re
from difflib import SequenceMatcher

import numpy as np
import pandas as pd

from .config import USE_EMBEDDINGS
from .taxonomy import DISTRICTS, TRADES

try:
    from rapidfuzz import fuzz, process
    HAVE_RF = True
except ImportError:  # pragma: no cover - fallback keeps the project runnable without rapidfuzz
    HAVE_RF = False

NOISE = {"urgent", "urgently", "required", "requirement", "hiring", "wanted", "vacancy", "opening", "fresher", "freshers",
         "experienced", "contract", "permanent", "needed", "walk", "in", "immediate", "immediately", "for", "joining",
         "job", "jobs", "sr", "jr", "senior", "junior", "m", "f", "helper", "cum"}
ABBR = {"tech": "technician", "asst": "assistant", "engg": "engineer", "elec": "electrical", "mob": "mobile"}
_PUNCT = re.compile(r"[!-/:-@\[-`{-~।]")  # ASCII punctuation + danda; keeps Devanagari combining marks intact


def normalise_text(s: str) -> str:
    s = _PUNCT.sub(" ", str(s).lower())
    toks = [ABBR.get(t, t) for t in s.split() if t not in NOISE]
    return " ".join(toks)


_SEED_TEXT, _SEED_TRADE = [], []
for _t in TRADES:
    for _s in _t[7]:
        _SEED_TEXT.append(normalise_text(_s))
        _SEED_TRADE.append(_t[0])
TRADE_CODES = [t[0] for t in TRADES]
_TRADE_IDX = {c: np.array([i for i, x in enumerate(_SEED_TRADE) if x == c]) for c in TRADE_CODES}


def _fuzzy_matrix(queries: list[str]) -> np.ndarray:
    """(Q x seeds) similarity in 0..1."""
    if HAVE_RF:
        return process.cdist(queries, _SEED_TEXT, scorer=fuzz.WRatio, dtype=np.uint8, workers=-1).astype(float) / 100.0
    out = np.zeros((len(queries), len(_SEED_TEXT)))
    for i, q in enumerate(queries):
        for j, sd in enumerate(_SEED_TEXT):
            out[i, j] = SequenceMatcher(None, q, sd).ratio()
    return out


_EMB = {}


def _embedding_matrix(queries: list[str]):
    """Cosine similarity (Q x seeds) via multilingual MiniLM, or None when unavailable."""
    if not USE_EMBEDDINGS:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        if "m" not in _EMB:
            _EMB["m"] = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            _EMB["seeds"] = _EMB["m"].encode(_SEED_TEXT, normalize_embeddings=True)
        q = _EMB["m"].encode(queries, normalize_embeddings=True, batch_size=128)
        return np.clip(q @ _EMB["seeds"].T, 0, 1)
    except Exception:  # pragma: no cover
        return None


def map_titles(titles: pd.Series, overrides: dict[str, str], threshold: float) -> pd.DataFrame:
    """Map unique raw titles. Returns one row per unique normalised title:
    title_norm, trade_code (best suggestion), confidence, second_trade, method, status ('auto'|'review'|'override')."""
    norm = titles.map(normalise_text)
    uniq = sorted(set(norm))
    if not uniq:
        return pd.DataFrame(columns=["title_norm", "trade_code", "confidence", "second_trade", "method", "status"])
    M = _fuzzy_matrix(uniq)
    E = _embedding_matrix(uniq)
    method = "fuzzy"
    if E is not None:
        M = 0.5 * M + 0.5 * E
        method = "fuzzy+embedding"
    S = np.column_stack([M[:, _TRADE_IDX[c]].max(axis=1) for c in TRADE_CODES])  # Q x trades
    order = np.argsort(-S, axis=1)
    top = S[np.arange(len(uniq)), order[:, 0]]
    second = S[np.arange(len(uniq)), order[:, 1]]
    conf = top * (0.8 + 0.2 * np.minimum(1.0, (top - second) / 0.15))
    df = pd.DataFrame({"title_norm": uniq, "trade_code": [TRADE_CODES[i] for i in order[:, 0]], "confidence": conf.round(4),
                       "second_trade": [TRADE_CODES[i] for i in order[:, 1]], "method": method})
    df["status"] = np.where(df["confidence"] >= threshold, "auto", "review")
    for i, tn in enumerate(df["title_norm"].tolist()):  # human feedback overrides
        if tn in overrides:
            tr = overrides[tn]
            df.at[i, "trade_code"] = tr
            df.at[i, "confidence"] = 1.0
            df.at[i, "method"] = "override"
            df.at[i, "status"] = "override" if tr != "OTHER" else "excluded"
    return df


# ---------------- location normalisation
_ALIAS = {}
for _d in DISTRICTS:
    for _a in _d[5] + [_d[1].lower()]:
        _ALIAS[normalise_text(_a)] = _d[0]
_STATE_WORDS = {"up", "uttar", "pradesh", "maharashtra", "mh", "dist", "district"}
_ALIAS_KEYS = list(_ALIAS)


def normalise_district(raw: str, cutoff: float = 0.80) -> str | None:
    s = " ".join(t for t in _PUNCT.sub(" ", str(raw).lower()).split() if t not in _STATE_WORDS)
    if s in _ALIAS:
        return _ALIAS[s]
    if not s:
        return None
    if HAVE_RF:
        m = process.extractOne(s, _ALIAS_KEYS, scorer=fuzz.WRatio, score_cutoff=cutoff * 100)
        return _ALIAS[m[0]] if m else None
    best = max(_ALIAS_KEYS, key=lambda a: SequenceMatcher(None, s, a).ratio())
    return _ALIAS[best] if SequenceMatcher(None, s, best).ratio() >= cutoff else None


# ---------------- accuracy report
def evaluate_mapping(mapped: pd.DataFrame, postings: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Posting-weighted accuracy against the generator's ground truth (synthetic validation set).
    postings needs 'title' (raw) and 'title_norm'; truth has title, true_trade_code."""
    truth = truth.assign(title_norm=truth["title"].map(normalise_text))
    t = truth.groupby("title_norm")["true_trade_code"].agg(lambda s: s.value_counts().index[0]).rename("truth")
    w = postings.groupby("title_norm").size().rename("n")
    d = mapped.set_index("title_norm").join(t, how="left").join(w, how="left").dropna(subset=["truth", "n"])
    if d.empty:
        return {}
    d["correct"] = d["trade_code"] == d["truth"]
    inscope, auto = d["truth"] != "OTHER", d["status"].isin(["auto", "override"])
    n = d["n"]

    def wavg(mask):
        return float((d.loc[mask, "correct"] * n[mask]).sum() / max(n[mask].sum(), 1))
    return {
        "n_unique_titles": int(len(d)), "n_postings": int(n.sum()),
        "top1_accuracy_in_scope": round(wavg(inscope), 4),
        "auto_accepted_share": round(float(n[auto].sum() / n.sum()), 4),
        "auto_accepted_accuracy": round(wavg(auto & inscope), 4),
        "review_queue_share": round(float(n[~auto].sum() / n.sum()), 4),
        "out_of_scope_caught_share": round(float(n[(d["truth"] == "OTHER") & ~auto].sum() / max(n[d["truth"] == "OTHER"].sum(), 1)), 4),
        "method": str(mapped["method"].iloc[0]) if len(mapped) else "n/a",
        "note": "Measured on a synthetic validation set generated with the demo data; real-world accuracy will differ.",
    }
