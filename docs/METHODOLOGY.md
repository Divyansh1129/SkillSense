# Methodology (policy summary)

**1. Sources → one index.** Four demand signals per district × trade × month: de-duplicated, trade-mapped job postings (3-month smoothed), industry hiring index, PLFS-style employment level (quarterly, carried forward), e-Shram registrations. Each is scaled by a robust z-score (median/MAD, clipped ±3) *within its own series*, so different units are comparable.
`DemandIndex = Σ w̃ᵢ·zᵢ`. Default weights: postings 35%, hiring 25%, PLFS 25%, e-Shram 15% (rationale: timeliness vs reliability; editable by admin). Missing source → weights re-normalised over available sources; sparse online postings are down-weighted; `confidence = Σ available weight×quality / Σ weight`.

**2. Calibration to openings.** `openings_t = B·clip(1+Σ w̃ᵢ·zᵢ·sᵢ, 0.2, 3)`, where `sᵢ = 1.4826·MAD/median` converts z back to relative deviation and `B = median(PLFS level)×turnover/12`. Turnover rates (12–20%/yr) are assumptions. Per-source contributions are stored for explainability.

**3. Supply.** `seats × enrolment × completion × placement-ready + carry-over`, carry-over = previous-cycle certified-but-unplaced × retention (50%).

**4. Forecast.** 12 months ahead. Harmonic damped-trend baseline + global LightGBM (lags, rolling means, seasonality, agri-season); per-series inverse-error ensemble. Rolling-origin backtest (origins 18…30, 6-month horizon); intervals from pooled relative errors by horizon (80% / 95%). District-trade forecasts are reconciled to the state-trade forecast (sparse series blend with parent share first).

**5. Gap & severity.** `Gap = Demand − Supply` (+ shortage). `GapPct = Gap/max(Demand,5)`. `Severity = 100(0.55·magnitude + 0.20·widening + 0.10·demand-growth + 0.15·certainty)`.

**6. Flags.** ACUTE_SHORTAGE, APPROACHING_SATURATION, EMERGING_DEMAND, DATA_LOW_CONFIDENCE with watch/warning/critical levels from editable thresholds; reasons/actions are generated from translatable templates.

**7. Planner tools.** What-if recomputes supply/gap/severity for seat changes; recommender minimises total |gap| within ±X% per series and an optional seat budget (greedy fractional knapsack = exact LP solution here).

**Limitations:** simulated data; assumptions listed above; accuracy on real data will differ.
