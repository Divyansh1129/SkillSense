"""Module 4 - Forecast engine.

Models (monthly openings, 12-month horizon):
  * harmonic  : damped-trend log-linear regression with 2 annual harmonics (fast ETS-style seasonal baseline)
  * gbm       : one global gradient-boosting model (LightGBM, sklearn fallback) on lag / rolling / seasonality / agri-season
                features, scale-free (ratio to series level) so it also forecasts aggregated series; recursive multi-step
  * ensemble  : per-series inverse-error weights from calibration backtests, shrunk 50% to the global mix
Backtesting: rolling origins (18,21,24,27,30), 6-month horizon. Weights and interval widths are calibrated on origins <= 24;
metrics and interval coverage are reported on holdout origins 27 and 30 (+ a seasonal-naive reference).
Hierarchy: National -> State -> District -> Trade. Series are forecast at district-trade and state-trade levels;
district-trade forecasts are reconciled top-down to the state-trade forecast (forecast-proportion method, sparse series blend
with their parent share first), so district -> state -> national add up exactly.
"""
import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAVE_LGB = True
except Exception:  # pragma: no cover
    HAVE_LGB = False
from sklearn.ensemble import HistGradientBoostingRegressor

from .config import DATA_START
from .taxonomy import DISTRICT_BY_CODE, TRADE_BY_CODE

ORIGINS, BT_H, CAL_MAX, H_MAX = [18, 21, 24, 27, 30], 6, 24, 12
Z80, Z95, PHI = 1.2816, 1.96, 0.92
SECTORS = ["ELE", "REN", "HLT"]
AGRI = {6, 7, 8, 10, 11}


# ---------------------------------------------------------------- base models
def harmonic_forecast(Y: np.ndarray, month0: int, H: int) -> np.ndarray:
    S, n = Y.shape
    L = np.log(np.maximum(Y, 1e-3))
    t = np.arange(n, dtype=float)
    cal = (month0 - 1 + np.arange(n)) % 12

    def X(tt, cc):
        w = 2 * np.pi * cc / 12
        return np.column_stack([np.ones(len(tt)), tt / 12, np.sin(w), np.cos(w), np.sin(2 * w), np.cos(2 * w)])
    Xh = X(t, cal)
    lam = np.diag([0, 0.01, 0.5, 0.5, 0.5, 0.5])
    beta = np.linalg.solve(Xh.T @ Xh + lam, Xh.T @ L.T)
    h = np.arange(1, H + 1)
    tf = (n - 1) + np.cumsum(PHI ** h)                       # damped trend steps
    calf = (month0 - 1 + n - 1 + h) % 12
    return np.exp((X(tf, calf) @ beta).T)


def seasonal_naive(Y: np.ndarray, H: int) -> np.ndarray:
    n = Y.shape[1]
    if n < 12:
        return np.repeat(Y[:, -1:], H, axis=1)
    return np.column_stack([Y[:, n - 12 + (h % 12)] for h in range(H)])


def _features(Z, t, cal_m, static):
    l1, l2, l3, l12 = Z[:, t - 1], Z[:, t - 2], Z[:, t - 3], Z[:, t - 12]
    m3, m12 = Z[:, t - 3:t].mean(1), Z[:, t - 12:t].mean(1)
    w = 2 * np.pi * cal_m / 12
    agri = float(cal_m in AGRI)
    n = Z.shape[0]
    return np.column_stack([l1, l2, l3, l12, m3, m12, m3 / np.maximum(m12, 1e-6) - 1,
                            np.full(n, np.sin(w)), np.full(n, np.cos(w)), static["rural"] * agri, static["rural"], static["sec"]])


def _make_model():
    if HAVE_LGB:
        return lgb.LGBMRegressor(n_estimators=300, learning_rate=0.04, num_leaves=15, min_child_samples=15, subsample=0.8,
                                 subsample_freq=1, colsample_bytree=0.9, verbose=-1, n_jobs=2, random_state=7)
    return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=15, random_state=7)


def gbm_forecast(Y: np.ndarray, month0: int, H: int, static: dict) -> np.ndarray:
    S, n = Y.shape
    scale = np.maximum(Y[:, -12:].mean(1, keepdims=True), 1e-3)
    Z = Y / scale
    Xs, ys = [], []
    for t in range(12, n):
        Xs.append(_features(Z, t, (month0 - 1 + t) % 12 + 1, static))
        ys.append(Z[:, t])
    model = _make_model().fit(np.vstack(Xs), np.concatenate(ys))
    Zx = np.hstack([Z, np.zeros((S, H))])
    for h in range(H):
        t = n + h
        Zx[:, t] = np.clip(model.predict(_features(Zx, t, (month0 - 1 + t) % 12 + 1, static)), 0.2, 4.0)
    return Zx[:, n:] * scale


# ---------------------------------------------------------------- series assembly
def build_series(di: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame, list[str]]:
    """Returns Y_all (bottom + state-trade parents), meta, months."""
    piv = di.pivot_table(index=["district_code", "trade_code"], columns="month", values="openings_est").sort_index()
    months = list(piv.columns)
    bottom = piv.reset_index()[["district_code", "trade_code"]]
    bottom["state"] = bottom["district_code"].map(lambda d: DISTRICT_BY_CODE[d][2])
    bottom["rural"] = bottom["district_code"].map(lambda d: float(DISTRICT_BY_CODE[d][3] == "rural"))
    bottom["sector"] = bottom["trade_code"].map(lambda c: TRADE_BY_CODE[c][2])
    bottom["level"] = "bottom"
    Yb = piv.to_numpy()
    par = bottom.assign(g=bottom["state"] + "|" + bottom["trade_code"])
    ind = par.groupby("g", sort=True).indices
    keys = sorted(ind.keys())
    Yp = np.vstack([Yb[ind[k]].sum(0) for k in keys])
    pmeta = pd.DataFrame([{"district_code": k, "trade_code": k.split("|")[1], "state": k.split("|")[0], "rural": 0.0,
                           "sector": TRADE_BY_CODE[k.split("|")[1]][2], "level": "parent"} for k in keys])
    meta = pd.concat([bottom, pmeta], ignore_index=True)
    return np.vstack([Yb, Yp]), meta, months


def _static(meta: pd.DataFrame) -> dict:
    return {"rural": meta["rural"].to_numpy(float), "sec": np.column_stack([(meta["sector"] == s).to_numpy(float) for s in SECTORS])}


def _month0(months: list[str]) -> int:
    return int(months[0][5:])


def _metrics(a: np.ndarray, f: np.ndarray) -> dict:
    m = a > 0
    return {"wape": float(np.abs(a - f).sum() / max(a.sum(), 1e-9)),
            "mape": float(np.mean(np.abs(a[m] - f[m]) / a[m])) if m.any() else np.nan,
            "smape": float(np.mean(2 * np.abs(a - f) / np.maximum(np.abs(a) + np.abs(f), 1e-9))),
            "bias": float((f - a).sum() / max(a.sum(), 1e-9))}


# ---------------------------------------------------------------- main entry
def run_forecast(di: pd.DataFrame, sq: pd.DataFrame, run_id: str) -> dict:
    Y, meta, months = build_series(di)
    S = len(meta)
    m0 = _month0(months)
    static = _static(meta)
    n = Y.shape[1]
    parent = (meta["level"] == "parent").to_numpy()

    # ---- rolling-origin backtest
    bt = {}
    for o in ORIGINS:
        Yo = Y[:, :o]
        bt[o] = {"harmonic": harmonic_forecast(Yo, m0, BT_H), "gbm": gbm_forecast(Yo, m0, BT_H, static),
                 "snaive": seasonal_naive(Yo, BT_H), "actual": Y[:, o:o + BT_H]}
    cal = [o for o in ORIGINS if o <= CAL_MAX]
    test = [o for o in ORIGINS if o > CAL_MAX]

    def wape_series(model, origins):
        num = sum(np.abs(bt[o]["actual"] - bt[o][model]).sum(1) for o in origins)
        den = sum(bt[o]["actual"].sum(1) for o in origins)
        return num / np.maximum(den, 1e-9)
    eh, eg = wape_series("harmonic", cal), wape_series("gbm", cal)
    w_ser = (1 / (eh + 0.02) ** 2) / ((1 / (eh + 0.02) ** 2) + (1 / (eg + 0.02) ** 2))
    w_glob = float(np.median(w_ser))
    w_h = 0.5 * w_ser + 0.5 * w_glob                               # weight of harmonic model per series

    def ens(o):
        return w_h[:, None] * bt[o]["harmonic"] + (1 - w_h[:, None]) * bt[o]["gbm"]

    # ---- interval calibration on calibration origins (relative errors, pooled by hierarchy level and horizon)
    R = np.stack([(bt[o]["actual"] - ens(o)) / np.maximum(ens(o), 1e-6) for o in cal], axis=1)   # S x O x H
    sig_h = {}
    for lvl, mask in (("bottom", ~parent), ("parent", parent)):
        sh = np.sqrt((R[mask] ** 2).mean(axis=(0, 1)))             # per horizon
        coef = np.polyfit(np.arange(1, BT_H + 1), sh, 1)
        sig = np.maximum(np.polyval(coef, np.arange(1, H_MAX + 1)), 0.03)
        sig_h[lvl] = np.maximum.accumulate(sig)
    sig_ser = np.sqrt((R ** 2).mean(axis=(1, 2)))
    rho = np.ones(S)
    for lvl, mask in (("bottom", ~parent), ("parent", parent)):
        pooled = np.sqrt((R[mask] ** 2).mean())
        rho[mask] = np.clip(0.5 + 0.5 * sig_ser[mask] / max(pooled, 1e-6), 0.7, 1.8)
    sigma = np.vstack([sig_h["parent" if parent[i] else "bottom"] * rho[i] for i in range(S)])  # S x 12

    # ---- backtest metrics on holdout origins
    rows = []
    sector_of = meta["sector"].to_numpy()
    for scope, mask in [("all_bottom", ~parent), ("state_trade", parent)] + [(s, (~parent) & (sector_of == s)) for s in SECTORS]:
        for model in ["harmonic", "gbm", "snaive", "ensemble"]:
            a = np.concatenate([bt[o]["actual"][mask].ravel() for o in test])
            f = np.concatenate([(ens(o) if model == "ensemble" else bt[o][model])[mask].ravel() for o in test])
            for k, v in _metrics(a, f).items():
                rows.append((run_id, scope, model, k, v, int(len(a))))
        cov80 = cov95 = tot = 0
        for o in test:
            F, A = ens(o)[mask], bt[o]["actual"][mask]
            sg = sigma[mask][:, :BT_H]
            cov80 += (np.abs(A - F) <= Z80 * sg * F).sum()
            cov95 += (np.abs(A - F) <= Z95 * sg * F).sum()
            tot += A.size
        rows.append((run_id, scope, "ensemble", "coverage_80", cov80 / tot, int(tot)))
        rows.append((run_id, scope, "ensemble", "coverage_95", cov95 / tot, int(tot)))
    for hh in range(BT_H):  # error by horizon (bottom, ensemble)
        a = np.concatenate([bt[o]["actual"][~parent][:, hh] for o in test])
        f = np.concatenate([ens(o)[~parent][:, hh] for o in test])
        rows.append((run_id, "all_bottom", "ensemble", f"wape_h{hh + 1}", _metrics(a, f)["wape"], int(len(a))))
    backtests = pd.DataFrame(rows, columns=["run_id", "scope", "model", "metric", "value", "n"])

    # ---- final fit on full history
    Fh, Fg = harmonic_forecast(Y, m0, H_MAX), gbm_forecast(Y, m0, H_MAX, static)
    F = w_h[:, None] * Fh + (1 - w_h[:, None]) * Fg
    Fb, Fp = F[~parent].copy(), F[parent]
    mb = meta[~parent].reset_index(drop=True)
    mp = meta[parent].reset_index(drop=True)
    pkey = (mp["state"] + "|" + mp["trade_code"]).tolist()
    bkey = (mb["state"] + "|" + mb["trade_code"]).to_numpy()
    last12 = Y[~parent][:, -12:].sum(1)
    sparse = mb.merge(sq[["district_code", "trade_code", "sparse"]], how="left", on=["district_code", "trade_code"])["sparse"].fillna(0).to_numpy() == 1
    for gi, k in enumerate(pkey):
        idx = np.where(bkey == k)[0]
        share = last12[idx] / max(last12[idx].sum(), 1e-9)
        f = Fb[idx]
        f[sparse[idx]] = 0.5 * f[sparse[idx]] + 0.5 * share[sparse[idx], None] * Fp[gi][None, :]   # borrow strength
        Fb[idx] = f * (Fp[gi] / np.maximum(f.sum(0), 1e-9))[None, :]                               # coherent with parent
    sg_b = sigma[~parent]
    fut = [str(p) for p in pd.period_range(pd.Period(months[-1]) + 1, periods=H_MAX, freq="M")]
    recs = []
    for i in range(len(mb)):
        for h in range(H_MAX):
            y, s = Fb[i, h], sg_b[i, h]
            recs.append((run_id, mb.at[i, "district_code"], mb.at[i, "trade_code"], fut[h], h + 1, y,
                         max(y * (1 - Z80 * s), 0), y * (1 + Z80 * s), max(y * (1 - Z95 * s), 0), y * (1 + Z95 * s), float(w_h[~parent][i])))
    fc = pd.DataFrame(recs, columns=["run_id", "district_code", "trade_code", "month", "h", "yhat", "lo80", "hi80", "lo95", "hi95", "w_harmonic"])
    info = {"run_id": run_id, "lightgbm": HAVE_LGB, "n_series_bottom": int((~parent).sum()), "n_series_parent": int(parent.sum()),
            "data_through": months[-1], "horizon": H_MAX, "origins": ORIGINS, "calibration_origins": cal, "holdout_origins": test,
            "global_harmonic_weight": round(w_glob, 3)}
    return {"forecast": fc, "backtests": backtests, "info": info}
