#!/usr/bin/env python3
"""
ERA5 Bias Correction — Gilgit-Baltistan Weather Dataset
========================================================
Method: Monthly Delta Bias Correction (per-station, per-variable)

The ERA5 reanalysis has a known discontinuity around 2016 caused by updates
to the ECMWF data assimilation system. This script corrects the pre-2016 data
to align with the post-2016 baseline using a monthly delta approach:

  For additive variables (temperature, wind, radiation, etc.):
      delta(month) = mean_post(month) - mean_pre(month)
      corrected_pre = raw_pre + delta(month)

  For multiplicative variables (precipitation, snowfall, etc.):
      ratio(month) = mean_post(month) / mean_pre(month)   [guarded: if pre=0 → ratio=1]
      corrected_pre = raw_pre × ratio(month)

Why monthly instead of annual?
  A global annual shift would squash seasonal variation. E.g. if ERA5 under-
  estimated January snow but over-estimated July rain in the old model, a
  single correction factor would fix one while breaking the other. Monthly
  deltas fix each season independently.

Output files:
  <station>_corrected.csv        — corrected version of each station CSV
  gb_weather_corrected.csv       — combined corrected dataset
  bias_correction_report.json    — all deltas / ratios applied (for audit trail)
"""

import csv
import json
import os
import math
from collections import defaultdict
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
BREAK_DATE   = "2016-01-01"
MIN_YEARS    = 3   # minimum years of data required in each period to correct

# Variables corrected additively (shift by delta)
ADDITIVE_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "apparent_temperature_mean",
    "wind_speed_10m_max",
    "wind_speed_10m_mean",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",  # special: circular mean handled separately
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "uv_index_max",
    "sunshine_duration",
    "daylight_duration",
    "cloud_cover_mean",
]

# Variables corrected multiplicatively (scale by ratio)
MULTIPLICATIVE_VARS = [
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
]

# Variables NOT corrected (categorical, astronomical, or already correct)
SKIP_VARS = [
    "weather_code",   # WMO categorical code
    "sunrise",        # astronomical — no ERA5 dependence
    "sunset",         # astronomical
    "daylight_duration",  # purely astronomical — skip correction
]

ALL_NUMERIC_VARS = ADDITIVE_VARS + MULTIPLICATIVE_VARS
META_COLS = ["date", "era5_period", "station", "district", "lat", "lon", "elevation_m"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def month_of(date_str):
    return int(date_str[5:7])  # "YYYY-MM-DD" → int month

def mean(values):
    vals = [v for v in values if v is not None and not math.isnan(v)]
    return sum(vals) / len(vals) if vals else None

def circular_mean_deg(angles):
    """Mean of angular values (wind direction) in degrees."""
    vals = [v for v in angles if v is not None and not math.isnan(v)]
    if not vals:
        return None
    import math
    sin_sum = sum(math.sin(math.radians(a)) for a in vals)
    cos_sum = sum(math.cos(math.radians(a)) for a in vals)
    angle   = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
    return angle

# ── Step 1: Load all station CSVs ─────────────────────────────────────────────
def load_station_files():
    stations = {}
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith("_weather.csv"):
            continue
        path  = os.path.join(DATA_DIR, fname)
        rows  = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        if rows:
            sname = rows[0].get("station", fname.replace("_weather.csv",""))
            stations[sname] = rows
            print(f"  Loaded {sname:12s} — {len(rows):,} rows")
    return stations

# ── Step 2: Compute monthly deltas per station per variable ───────────────────
def compute_corrections(station_name, rows):
    """
    Returns:
      corrections: dict[var][month] = {"type": "additive"|"multiplicative", "value": float}
      diagnostics: detailed report
    """
    # Bucket values by period × month
    pre  = defaultdict(lambda: defaultdict(list))   # pre[var][month]  = [float, ...]
    post = defaultdict(lambda: defaultdict(list))   # post[var][month] = [float, ...]

    for row in rows:
        period = row.get("era5_period", "")
        month  = month_of(row["date"])
        for var in ALL_NUMERIC_VARS:
            if var in SKIP_VARS:
                continue
            val = safe_float(row.get(var))
            if val is None:
                continue
            if period == "pre_2016":
                pre[var][month].append(val)
            elif period == "post_2016":
                post[var][month].append(val)

    # Check we have enough data in both periods
    pre_years  = sum(1 for r in rows if r.get("era5_period") == "pre_2016")  / 365.25
    post_years = sum(1 for r in rows if r.get("era5_period") == "post_2016") / 365.25

    corrections = {}
    diagnostics = {}

    if pre_years < MIN_YEARS or post_years < MIN_YEARS:
        print(f"    WARNING: {station_name} — insufficient data "
              f"(pre={pre_years:.1f}yr, post={post_years:.1f}yr). Skipping correction.")
        return corrections, diagnostics

    for var in ALL_NUMERIC_VARS:
        if var in SKIP_VARS:
            continue
        corrections[var] = {}
        diagnostics[var] = {"type": None, "months": {}}

        is_mult  = var in MULTIPLICATIVE_VARS
        is_circ  = var == "wind_direction_10m_dominant"

        for m in range(1, 13):
            pre_vals  = pre[var][m]
            post_vals = post[var][m]
            mu_pre    = mean(pre_vals)
            mu_post   = mean(post_vals)

            if mu_pre is None or mu_post is None:
                corrections[var][m] = {"type": "none", "value": 1.0 if is_mult else 0.0}
                continue

            if is_circ:
                # Wind direction: compute angular delta
                import math
                delta = (mu_post - mu_pre + 540) % 360 - 180  # wrap to [-180, 180]
                corrections[var][m] = {"type": "additive_circular", "value": round(delta, 3)}
            elif is_mult:
                ratio = (mu_post / mu_pre) if abs(mu_pre) > 0.001 else 1.0
                # Cap ratio to [0.1, 10] to avoid extreme corrections
                ratio = max(0.1, min(10.0, ratio))
                corrections[var][m] = {"type": "multiplicative", "value": round(ratio, 6)}
            else:
                delta = mu_post - mu_pre
                corrections[var][m] = {"type": "additive", "value": round(delta, 6)}

            diagnostics[var]["type"] = corrections[var][m]["type"]
            diagnostics[var]["months"][m] = {
                "pre_mean":    round(mu_pre,  4),
                "post_mean":   round(mu_post, 4),
                "correction":  round(corrections[var][m]["value"], 6),
                "n_pre":       len(pre_vals),
                "n_post":      len(post_vals),
            }

    return corrections, diagnostics

# ── Step 3: Apply corrections to pre-2016 rows ───────────────────────────────
def apply_corrections(rows, corrections):
    corrected = []
    for row in rows:
        new_row = dict(row)
        new_row["bias_corrected"] = "0"

        if row.get("era5_period") == "pre_2016" and corrections:
            month = month_of(row["date"])
            new_row["bias_corrected"] = "1"

            for var, monthly in corrections.items():
                corr = monthly.get(month)
                if corr is None:
                    continue
                val = safe_float(row.get(var))
                if val is None:
                    continue

                ctype = corr["type"]
                cval  = corr["value"]

                if ctype == "additive":
                    new_row[var] = str(round(val + cval, 6))
                elif ctype == "multiplicative":
                    new_row[var] = str(round(val * cval, 6))
                elif ctype == "additive_circular":
                    new_row[var] = str(round((val + cval) % 360, 3))

        corrected.append(new_row)
    return corrected

# ── Step 4: Save corrected CSVs ───────────────────────────────────────────────
def save_corrected_csv(station_name, rows):
    fname = os.path.join(DATA_DIR, f"{station_name.lower()}_corrected.csv")
    if not rows:
        return fname
    fieldnames = list(rows[0].keys())
    if "bias_corrected" not in fieldnames:
        fieldnames.append("bias_corrected")
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return fname

def save_combined_corrected(all_corrected):
    fname = os.path.join(DATA_DIR, "gb_weather_corrected.csv")
    if not all_corrected:
        return fname
    # Collect all fieldnames
    fieldnames = list(all_corrected[0][0].keys()) if all_corrected[0] else []
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rows in all_corrected:
            w.writerows(rows)
    return fname

# ── Step 5: Validation — print before/after stats ────────────────────────────
def validate(station_name, original_rows, corrected_rows, var="temperature_2m_mean"):
    def monthly_mean(rows, period):
        buckets = defaultdict(list)
        for r in rows:
            if r.get("era5_period") == period:
                v = safe_float(r.get(var))
                if v is not None:
                    buckets[month_of(r["date"])].append(v)
        return {m: round(mean(v), 3) for m, v in buckets.items() if v}

    pre_before  = monthly_mean(original_rows,  "pre_2016")
    pre_after   = monthly_mean(corrected_rows, "pre_2016")
    post        = monthly_mean(original_rows,  "post_2016")

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    print(f"\n    Validation — {station_name} / {var}")
    print(f"    {'Month':<6} {'Pre (raw)':>10} {'Pre (fixed)':>12} {'Post':>10} {'Bias fixed':>12}")
    for m in range(1, 13):
        pb = pre_before.get(m, "-")
        pa = pre_after.get(m,  "-")
        po = post.get(m,       "-")
        diff = round(pa - po, 3) if isinstance(pa, float) and isinstance(po, float) else "-"
        print(f"    {month_names[m-1]:<6} {str(pb):>10} {str(pa):>12} {str(po):>10} {str(diff):>12}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  ERA5 Monthly Delta Bias Correction")
    print(f"  Break date  : {BREAK_DATE}")
    print(f"  Directory   : {DATA_DIR}")
    print("=" * 65)

    print("\nLoading station data...")
    stations = load_station_files()
    if not stations:
        print("No station CSVs found. Run fetch_gb_weather.py first.")
        return

    all_corrected    = []
    full_report      = {}

    for station_name, rows in stations.items():
        print(f"\nProcessing {station_name}...")

        print(f"  Computing monthly corrections ({len(rows):,} days)...")
        corrections, diagnostics = compute_corrections(station_name, rows)

        print(f"  Applying corrections to pre-2016 rows...")
        corrected_rows = apply_corrections(rows, corrections)

        # Validate temperature correction
        if corrections:
            validate(station_name, rows, corrected_rows, "temperature_2m_mean")

        print(f"  Saving {station_name.lower()}_corrected.csv...")
        save_corrected_csv(station_name, corrected_rows)

        all_corrected.append(corrected_rows)

        full_report[station_name] = {
            "total_rows":     len(rows),
            "pre_2016_rows":  sum(1 for r in rows if r.get("era5_period") == "pre_2016"),
            "post_2016_rows": sum(1 for r in rows if r.get("era5_period") == "post_2016"),
            "corrections_applied": bool(corrections),
            "variables_corrected": len(corrections),
            "variable_details": diagnostics,
        }

    print(f"\nSaving combined corrected dataset...")
    combined_path = save_combined_corrected(all_corrected)

    # Save audit report
    report_path = os.path.join(DATA_DIR, "bias_correction_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "method":       "Monthly Delta Bias Correction",
                "break_date":   BREAK_DATE,
                "generated":    datetime.utcnow().isoformat() + "Z",
                "description":  (
                    "Pre-2016 ERA5 data corrected to align with post-2016 baseline. "
                    "Additive correction for temperature/wind/radiation variables. "
                    "Multiplicative correction for precipitation/snowfall variables. "
                    "Corrections computed per calendar month to preserve seasonality."
                ),
                "additive_vars":       ADDITIVE_VARS,
                "multiplicative_vars": MULTIPLICATIVE_VARS,
            },
            "stations": full_report,
        }, f, indent=2, ensure_ascii=False)

    total_rows = sum(len(r) for r in all_corrected)
    print("\n" + "=" * 65)
    print("  BIAS CORRECTION COMPLETE")
    print(f"  Stations processed  : {len(stations)}")
    print(f"  Total rows          : {total_rows:,}")
    print(f"  Combined output     : gb_weather_corrected.csv")
    print(f"  Audit report        : bias_correction_report.json")
    print("=" * 65)
    print("\nTip: Use 'gb_weather_corrected.csv' for model training.")
    print("     The 'bias_corrected' column = 1 where correction was applied.")
    print("     Full correction deltas/ratios in bias_correction_report.json")

if __name__ == "__main__":
    main()
