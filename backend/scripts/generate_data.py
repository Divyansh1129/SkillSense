"""Deterministic synthetic data generator (SIMULATED data - never present as real statistics).

Writes raw files in the shape the connectors expect into data/raw/:
  postings.csv, hiring_signals.csv, plfs.csv, eshram.csv, training_seats.csv, title_truth.csv, scenarios.json
Usage:  python -m scripts.generate_data
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import DATA_START, N_MONTHS, RAW_DIR  # noqa: E402
from app.taxonomy import DISTRICTS, TRADES  # noqa: E402

SEED = 42
rng = np.random.default_rng(SEED)
rnd = random.Random(SEED)
MONTHS = [str(p) for p in pd.period_range(DATA_START, periods=N_MONTHS, freq="M")]
CAL = np.array([int(m[5:]) for m in MONTHS])
T = np.arange(N_MONTHS)

# annual openings for a size-1.0 district, and yearly growth
TRADE_BASE = {"ELE01": 400, "ELE02": 220, "ELE03": 150, "ELE04": 180, "ELE05": 160, "ELE06": 260,
              "REN01": 120, "REN02": 70, "REN03": 50, "REN04": 20, "REN05": 40, "REN06": 30,
              "HLT01": 450, "HLT02": 200, "HLT03": 160, "HLT04": 110, "HLT05": 60, "HLT06": 220}
TRADE_GROWTH = {"ELE01": 0.02, "ELE02": 0.06, "ELE03": 0.08, "ELE04": -0.03, "ELE05": 0.03, "ELE06": 0.01,
                "REN01": 0.35, "REN02": 0.25, "REN03": 0.20, "REN04": 0.12, "REN05": 0.50, "REN06": 0.05,
                "HLT01": 0.05, "HLT02": 0.08, "HLT03": 0.10, "HLT04": 0.07, "HLT05": 0.09, "HLT06": 0.05}
STATE_MULT = {"MH": {"REN04": 3.0, "ELE02": 1.1, "HLT04": 1.2}, "UP": {"HLT01": 1.15, "ELE04": 1.1, "REN03": 1.5}}
GEN_SEAT_F = {"ELE01": 1.15, "ELE02": 0.95, "ELE03": 0.9, "ELE04": 1.3, "ELE05": 0.95, "ELE06": 1.1,
              "REN01": 0.6, "REN02": 0.6, "REN03": 0.7, "REN04": 0.7, "REN05": 0.5, "REN06": 0.9,
              "HLT01": 0.95, "HLT02": 0.9, "HLT03": 0.85, "HLT04": 0.8, "HLT05": 0.9, "HLT06": 1.0}
SEAT_DIVISOR = 0.59  # seats needed per unit demand when rates are nominal (see METHODOLOGY supply model)

# planted scenarios (district, trade) -> overrides
SCEN = {
    ("UP-KNP", "ELE01"): dict(g=-0.04, seat_f=2.3, sup_g=0.14, note="Oversupply in a traditional trade: seats rising while demand is flat"),
    ("MH-PUN", "REN01"): dict(g=0.45, base_mult=1.3, seat_f=0.30, sup_g=0.08, note="Solar PV installer demand surging with very few seats"),
    ("UP-GBN", "ELE02"): dict(jump=(30, 1.7), seat_f=1.0, note="Sudden demand jump from month 31 (Apr 2026)"),
    ("MH-NGP", "REN05"): dict(g=0.60, seat_f=0.35, note="EV charging: emerging demand with low seats"),
    ("UP-AGR", "ELE06"): dict(seat_f=1.9, sup_g=0.10, note="Mobile repair oversupply"),
    ("MH-THN", "ELE04"): dict(g=-0.08, seat_f=1.8, sup_g=0.10, note="Declining consumer-electronics repair, seats still rising"),
    ("MH-KOP", "HLT01"): dict(seat_f=0.55, note="General Duty Assistant shortage"),
    ("UP-GKP", "HLT03"): dict(seat_f=0.50, note="Home health aide shortage"),
    ("MH-NSK", "ELE06"): dict(jump=(24, 0.65), note="Structural break: demand drops ~35% from month 25"),
}
SPARSE_DISTRICT = "MH-GAD"            # very few online postings (sparse-data district)
ESHRAM_MISSING = ("UP-BRH", 18, 30)   # e-Shram feed missing for months 18..29

EXTRA = {  # unseen title variants (not in taxonomy seeds) so mapping accuracy is honest
    "ELE01": ["house electrician", "residential wiring technician", "electric mistri"],
    "ELE02": ["electronics service engineer field", "on-site electronics technician", "field technician (electronics & appliances)"],
    "ELE03": ["cctv camera technician", "security camera fitter", "cctv installation and service technician"],
    "ELE04": ["home appliance mechanic", "tv and fridge repair technician", "consumer durable repair technician"],
    "ELE05": ["maintenance technician (electrical)", "factory electrician", "electrical maintenance engineer diploma"],
    "ELE06": ["mobile phone repairing technician", "cell phone repair mistri", "smartphone service executive"],
    "REN01": ["solar installation helper", "solar pv fitter", "pv panel installation technician"],
    "REN02": ["solar plant maintenance technician", "o&m technician solar plant", "solar rooftop maintenance"],
    "REN03": ["solar water pump technician", "solar pump installation mechanic", "solar pumping technician"],
    "REN04": ["wind turbine service technician", "windmill maintenance technician", "wind power plant technician"],
    "REN05": ["ev charger technician", "electric vehicle charging station installer", "ev charging station operator technician"],
    "REN06": ["biogas plant operator technician", "gobar gas plant mistri", "biogas digester technician"],
    "HLT01": ["general duty attendant", "hospital ward attendant", "patient care helper"],
    "HLT02": ["blood sample collection technician", "phlebotomy executive", "sample collector (pathology)"],
    "HLT03": ["home care attendant", "elderly care taker home", "home nursing attendant"],
    "HLT04": ["ambulance emt", "emergency medical technician basic", "paramedic ambulance staff"],
    "HLT05": ["hemodialysis technician", "dialysis centre technician", "renal care technician"],
    "HLT06": ["lab technician pathology", "medical laboratory assistant", "dmlt lab technician"],
}
OTHER_TITLES = ["Accountant", "Delivery Executive", "Driver", "Data Entry Operator", "Sales Executive", "Graphic Designer",
                "Security Guard", "Receptionist", "Cook", "Teacher", "Telecaller", "Warehouse Helper"]
PREFIX = ["Urgent", "Hiring", "Required", "Wanted", "Immediate opening for", "Sr.", "Jr."]
SUFFIX = ["- Fresher", "(Contract)", "- Permanent", "needed", "/ helper", "(M/F)", "- walk-in"]
EMPLOYERS = {
    "ELE": ["Sunrise Electricals Pvt Ltd", "Bharat Wiring Co", "Volt Services LLP", "Metro Electronics", "CityCare Appliances", "Nova Security Systems", "Prime Power Works"],
    "REN": ["GreenGrid Energy", "SunPath Solar", "Surya Urja Pvt Ltd", "WindWorks India", "ChargeUp Mobility", "BioFuel Rural Co", "Kisan Solar Pumps"],
    "HLT": ["City General Hospital", "LifeLine Diagnostics", "CareFirst Home Health", "Sanjeevani Nursing Home", "RapidAid Ambulance", "Renal Care Centre", "Apex Pathlabs"],
}
PORTALS = ["NCS", "PortalA", "PortalB", "PortalC"]
SECTOR_OF = {t[0]: t[2] for t in TRADES}
NCO_OF = {t[0]: t[3] for t in TRADES}
TURNOVER = {t[0]: t[6] for t in TRADES}
SEEDS = {t[0]: t[7] for t in TRADES}
TRUTH: dict[str, str] = {}


def typo(s: str) -> str:
    if len(s) < 5 or not s.isascii():
        return s
    i = rnd.randrange(1, len(s) - 1)
    op = rnd.choice(["del", "swap", "dup"])
    if op == "del":
        return s[:i] + s[i + 1:]
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    return s[:i] + s[i] + s[i:]


def noisy(base: str) -> str:
    s = base
    if rnd.random() < 0.20:
        s = typo(s)
    if rnd.random() < 0.25:
        s = rnd.choice(PREFIX) + " " + s
    if rnd.random() < 0.25:
        s = s + " " + rnd.choice(SUFFIX)
    r = rnd.random()
    return s.upper() if r < 0.10 else s.title() if r < 0.40 else s


def gen_title(code: str) -> str:
    if rnd.random() < 0.025:
        t = noisy(rnd.choice(OTHER_TITLES))
        TRUTH.setdefault(t, "OTHER")
        return t
    t = noisy(rnd.choice(SEEDS[code] + EXTRA[code]))
    TRUTH.setdefault(t, code)
    return t


def season(rural: bool, sector: str) -> np.ndarray:
    s = 1 + 0.10 * np.cos(2 * np.pi * (CAL - 3) / 12)            # hiring-cycle peak in March
    if sector == "HLT":
        s = 1 + 0.04 * np.cos(2 * np.pi * (CAL - 9) / 12)
    if rural:
        s = s * (1 - (0.22 if sector != "HLT" else 0.10) * np.isin(CAL, [6, 7, 8, 10, 11]))  # agri-season dips
    return s


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    postings, hiring, plfs, eshram, seats = [], [], [], [], []
    pid = 0
    for (dcode, dname, st, dtype, size, aliases) in DISTRICTS:
        rural = dtype == "rural"
        cov = {"urban": 1.0, "semi": 0.6, "rural": 0.35}[dtype] * (0.35 if dcode == SPARSE_DISTRICT else 1.0)
        for (tcode, tname, sec, nco, nsqf, ssc, turn, _) in TRADES:
            sc = SCEN.get((dcode, tcode), {})
            mult = STATE_MULT[st].get(tcode, 1.0) * sc.get("base_mult", 1.0)
            if tcode == "REN03" and rural:
                mult *= 1.5
            if tcode == "REN05" and rural:
                mult *= 0.3
            if tcode == "ELE03" and dtype == "urban":
                mult *= 1.3
            g = sc.get("g", TRADE_GROWTH[tcode] + rng.normal(0, 0.03))
            A = TRADE_BASE[tcode] * size * mult / 12 * (1 + g) ** (T / 12) * season(rural, sec) * np.exp(rng.normal(0, 0.08, N_MONTHS))
            if "jump" in sc:
                A = A.copy()
                A[sc["jump"][0]:] *= sc["jump"][1]
            A = np.maximum(A, 0.05)
            # ---------- postings
            for t in range(N_MONTHS):
                for _ in range(rng.poisson(0.25 * cov * A[t])):
                    pid += 1
                    day = int(rng.integers(1, 29))
                    date = f"{MONTHS[t]}-{day:02d}"
                    title, emp = gen_title(tcode), rnd.choice(EMPLOYERS[sec])
                    loc = rnd.choice(aliases)
                    if rnd.random() < 0.3:
                        loc = loc.title() + (", UP" if st == "UP" else ", Maharashtra")
                    postings.append((pid, title, emp, loc, rnd.choice(PORTALS), date))
                    if rnd.random() < 0.18:  # cross-portal duplicate
                        pid += 1
                        d2 = pd.Timestamp(date) + pd.Timedelta(days=int(rng.integers(0, 4)))
                        t2 = typo(title) if rnd.random() < 0.4 else title
                        postings.append((pid, t2, emp, loc, rnd.choice(PORTALS), d2.strftime("%Y-%m-%d")))
            # ---------- hiring signal (industry), PLFS-style (quarterly), e-Shram
            ref = A[:6].mean()
            hs = 100 * A / ref * np.exp(rng.normal(0, 0.10, N_MONTHS))
            ann = 12 * pd.Series(A).rolling(6, min_periods=1).mean().to_numpy()
            lvl = ann / TURNOVER[tcode] * np.exp(rng.normal(0, 0.05, N_MONTHS))
            esr = A * 3 * np.exp(rng.normal(0, 0.15, N_MONTHS))
            for t in range(N_MONTHS):
                hiring.append((MONTHS[t], dcode, tcode, nco, round(float(hs[t]), 2)))
                if CAL[t] in (3, 6, 9, 12):
                    plfs.append((MONTHS[t], dcode, tcode, round(float(lvl[t]), 1)))
                miss = dcode == ESHRAM_MISSING[0] and ESHRAM_MISSING[1] <= t < ESHRAM_MISSING[2]
                if not miss and rng.random() > 0.02:
                    eshram.append((MONTHS[t], dcode, tcode, round(float(esr[t]), 1)))
            # ---------- training seats (3 cycles; latest = 2025)
            d12 = A[-12:].sum()
            f = GEN_SEAT_F[tcode] * sc.get("seat_f", 1.0) * float(np.exp(rng.normal(0, 0.15)))
            s25 = max(5, int(round(f * d12 / SEAT_DIVISOR / 5) * 5))
            if size < 0.7 and "seat_f" not in sc and rng.random() < 0.15:
                s25 = 0  # no centre offering this trade in the district
            sg = sc.get("sup_g", float(rng.normal(0.04, 0.06)))
            s24 = int(round(s25 / (1 + sg) / 5) * 5)
            s23 = int(round(s24 / (1 + float(rng.normal(0.04, 0.05))) / 5) * 5)
            for cyc, tot in ((2023, s23), (2024, s24), (2025, s25)):
                if tot <= 0:
                    continue
                n_c = 1 + (tot > 200) + (tot > 500)
                shares = rng.dirichlet(np.ones(n_c) * 3)
                for k in range(n_c):
                    place = 0.78 if sec == "HLT" else 0.65 if sec == "REN" else 0.70
                    seats.append((cyc, f"TC-{dcode}-{tcode}-{k + 1}", dcode, tcode, max(5, int(round(tot * shares[k]))),
                                  round(float(np.clip(rng.normal(0.85, 0.04), 0.6, 0.98)), 3),
                                  round(float(np.clip(rng.normal(0.82, 0.04), 0.6, 0.98)), 3),
                                  round(float(np.clip(rng.normal(place, 0.05), 0.4, 0.95)), 3)))
    P = pd.DataFrame(postings, columns=["posting_id", "title", "employer", "district_raw", "portal", "posted_date"])
    # messy rows to exercise validation
    n_bad = int(len(P) * 0.02)
    P.loc[P.sample(n_bad, random_state=1).index, "title"] = ""
    P.loc[P.sample(int(len(P) * 0.015), random_state=2).index, "district_raw"] = "Unknownville"
    P.to_csv(RAW_DIR / "postings.csv", index=False)
    pd.DataFrame(hiring, columns=["month", "district_code", "trade_code", "nco_code", "hiring_index"]).to_csv(RAW_DIR / "hiring_signals.csv", index=False)
    pd.DataFrame(plfs, columns=["month", "district_code", "trade_code", "employment_level"]).to_csv(RAW_DIR / "plfs.csv", index=False)
    pd.DataFrame(eshram, columns=["month", "district_code", "trade_code", "registrations"]).to_csv(RAW_DIR / "eshram.csv", index=False)
    pd.DataFrame(seats, columns=["cycle", "centre_id", "district_code", "trade_code", "seats", "enrolment_rate", "completion_rate", "placement_ready_rate"]).to_csv(RAW_DIR / "training_seats.csv", index=False)
    pd.DataFrame(sorted(TRUTH.items()), columns=["title", "true_trade_code"]).to_csv(RAW_DIR / "title_truth.csv", index=False)
    scen = [{"district": k[0], "trade": k[1], "note": v["note"]} for k, v in SCEN.items()]
    scen += [{"district": SPARSE_DISTRICT, "trade": "*", "note": "Sparse-data district (few online postings)"},
             {"district": ESHRAM_MISSING[0], "trade": "*", "note": "e-Shram feed missing for 12 months"}]
    (RAW_DIR / "scenarios.json").write_text(json.dumps(scen, indent=2), encoding="utf-8")
    print(f"postings={len(P)} hiring={len(hiring)} plfs={len(plfs)} eshram={len(eshram)} seats={len(seats)} -> {RAW_DIR}")


if __name__ == "__main__":
    main()
