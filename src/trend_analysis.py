#!/usr/bin/env python3
"""
GB Weather — Rolling Window + Decadal Trend + Pre/Post 2016 Analysis
=====================================================================
Steps:
  1. Load bias-corrected dataset
  2. Apply 365-day rolling mean per station to remove seasonal noise
  3. Fit linear trends (numpy polyfit) per station per decade
  4. Pre-2016 vs Post-2016 comparative analysis
  5. Print structured report with clear change identification
"""

import csv
import math
import os
import numpy as np
from collections import defaultdict
from datetime import datetime, date

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "gb_weather_corrected.csv")
BREAK_YEAR = 2016

# Variables to analyse
TEMP_VARS   = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean"]
PRECIP_VARS = ["precipitation_sum", "snowfall_sum", "rain_sum"]
WIND_VARS   = ["wind_speed_10m_max", "wind_speed_10m_mean"]
OTHER_VARS  = ["cloud_cover_mean", "et0_fao_evapotranspiration", "shortwave_radiation_sum"]
ALL_VARS    = TEMP_VARS + PRECIP_VARS + WIND_VARS + OTHER_VARS

DECADES = {
    "1990s": (1990, 1999),
    "2000s": (2000, 2009),
    "2010s": (2010, 2019),
    "2020s": (2020, 2024),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None

def mean(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None

def std(vals):
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))

def trend_per_decade(years, values):
    """Returns slope (units/year) and R² from linear polyfit."""
    pairs = [(y, v) for y, v in zip(years, values) if v is not None]
    if len(pairs) < 3:
        return None, None
    y_arr = np.array([p[0] for p in pairs], dtype=float)
    v_arr = np.array([p[1] for p in pairs], dtype=float)
    coeffs = np.polyfit(y_arr, v_arr, 1)
    slope = coeffs[0]  # units/year
    fitted  = np.polyval(coeffs, y_arr)
    ss_res  = np.sum((v_arr - fitted) ** 2)
    ss_tot  = np.sum((v_arr - np.mean(v_arr)) ** 2)
    r2      = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, r2

def rolling_mean_365(dates_vals, window=365):
    """
    dates_vals: list of (date_obj, float|None) sorted by date.
    Returns list of (date_obj, smoothed_float|None).
    """
    n = len(dates_vals)
    result = []
    half = window // 2
    vals = [v for _, v in dates_vals]
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        window_vals = [v for v in vals[lo:hi] if v is not None]
        result.append((dates_vals[i][0], mean(window_vals)))
    return result

# ── Load Data ─────────────────────────────────────────────────────────────────
def load_data():
    """Returns {station: [(date_obj, {var: float|None}, period), ...]}"""
    stations = defaultdict(list)
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            station = row["station"]
            period  = row.get("era5_period", "")
            vals    = {var: safe_float(row.get(var)) for var in ALL_VARS}
            stations[station].append((d, vals, period))
    for s in stations:
        stations[s].sort(key=lambda x: x[0])
    return dict(stations)

# ── Annual means from rolling-smoothed data ───────────────────────────────────
def annual_smoothed_means(station_rows):
    """
    For each variable:
      1. Build (date, value) series
      2. Apply 365-day rolling mean
      3. Aggregate to annual means
    Returns {var: {year: smoothed_annual_mean}}
    """
    result = {}
    for var in ALL_VARS:
        series = [(d, vals.get(var)) for d, vals, _ in station_rows]
        smoothed = rolling_mean_365(series)
        by_year = defaultdict(list)
        for d, v in smoothed:
            if v is not None:
                by_year[d.year].append(v)
        result[var] = {yr: mean(vs) for yr, vs in by_year.items()}
    return result

# ── Decadal trend ─────────────────────────────────────────────────────────────
def compute_decadal_trends(annual_data):
    """Returns {decade_label: {var: {slope, r2, decade_mean}}}"""
    trends = {}
    for decade, (y0, y1) in DECADES.items():
        trends[decade] = {}
        for var in ALL_VARS:
            years_in  = [y for y in range(y0, y1 + 1)]
            ydata     = annual_data.get(var, {})
            years     = [y for y in years_in if y in ydata]
            vals      = [ydata[y] for y in years]
            slope, r2 = trend_per_decade(years, vals)
            dm        = mean(vals)
            trends[decade][var] = {
                "slope":        round(slope * 10, 4) if slope is not None else None,
                "r2":           round(r2,   3) if r2 is not None else None,
                "decade_mean":  round(dm,   3) if dm is not None else None,
                "n_years":      len(years),
            }
    return trends

# ── Pre/Post 2016 stats ───────────────────────────────────────────────────────
def pre_post_stats(station_rows, annual_data):
    """Returns {var: {pre: {...}, post: {...}, delta: float, pct_change: float, direction: str}}"""
    result = {}
    for var in ALL_VARS:
        ydata = annual_data.get(var, {})
        pre_vals  = [v for y, v in ydata.items() if y <  BREAK_YEAR and v is not None]
        post_vals = [v for y, v in ydata.items() if y >= BREAK_YEAR and v is not None]

        pre_mean  = mean(pre_vals)
        post_mean = mean(post_vals)
        pre_std   = std(pre_vals)
        post_std  = std(post_vals)

        if pre_mean is None or post_mean is None or pre_mean == 0:
            continue

        delta      = post_mean - pre_mean
        pct_change = (delta / abs(pre_mean)) * 100

        pre_years  = sorted(y for y in ydata if y <  BREAK_YEAR)
        post_years = sorted(y for y in ydata if y >= BREAK_YEAR)

        pre_slope,  pre_r2  = trend_per_decade(pre_years,  [ydata[y] for y in pre_years])
        post_slope, post_r2 = trend_per_decade(post_years, [ydata[y] for y in post_years])

        result[var] = {
            "pre_mean":    round(pre_mean,  3),
            "post_mean":   round(post_mean, 3),
            "pre_std":     round(pre_std,   3) if pre_std  else None,
            "post_std":    round(post_std,  3) if post_std else None,
            "delta":       round(delta,     3),
            "pct_change":  round(pct_change,1),
            "pre_trend_per_decade":  round(pre_slope  * 10, 4) if pre_slope  else None,
            "post_trend_per_decade": round(post_slope * 10, 4) if post_slope else None,
            "volatility_change": round((post_std or 0) - (pre_std or 0), 3),
        }
    return result

# ── Print helpers ─────────────────────────────────────────────────────────────
UNITS = {
    "temperature_2m_max":          "°C",
    "temperature_2m_min":          "°C",
    "temperature_2m_mean":         "°C",
    "apparent_temperature_max":    "°C",
    "apparent_temperature_min":    "°C",
    "apparent_temperature_mean":   "°C",
    "precipitation_sum":           "mm",
    "rain_sum":                    "mm",
    "snowfall_sum":                "cm",
    "precipitation_hours":         "hrs",
    "wind_speed_10m_max":          "km/h",
    "wind_speed_10m_mean":         "km/h",
    "wind_gusts_10m_max":          "km/h",
    "cloud_cover_mean":            "%",
    "et0_fao_evapotranspiration":  "mm",
    "shortwave_radiation_sum":     "MJ/m²",
    "uv_index_max":                "index",
    "sunshine_duration":           "sec",
    "daylight_duration":           "sec",
}

VAR_LABELS = {
    "temperature_2m_max":          "Temp Max",
    "temperature_2m_min":          "Temp Min",
    "temperature_2m_mean":         "Temp Mean",
    "precipitation_sum":           "Precipitation",
    "rain_sum":                    "Rainfall",
    "snowfall_sum":                "Snowfall",
    "wind_speed_10m_max":          "Wind Max",
    "wind_speed_10m_mean":         "Wind Mean",
    "cloud_cover_mean":            "Cloud Cover",
    "et0_fao_evapotranspiration":  "Evapotranspiration",
    "shortwave_radiation_sum":     "Solar Radiation",
}

def arrow(val):
    if val is None:   return "  n/a  "
    if val > 0.05:    return "  UP ▲ "
    if val < -0.05:   return " DOWN ▼"
    return "  FLAT ─"

def sig(r2):
    if r2 is None: return "   "
    if r2 >= 0.7:  return "***"
    if r2 >= 0.4:  return " **"
    if r2 >= 0.2:  return "  *"
    return "   "

def trend_str(slope, r2, unit):
    if slope is None: return "     n/a"
    s = f"{slope:+.3f}{unit}/dec"
    return f"{s} (R²={r2:.2f}){sig(r2)}"

def section(title, width=72):
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)

def subsection(title, width=72):
    print(f"\n  ── {title} " + "─" * (width - len(title) - 6))

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 72)
    print("  GB WEATHER TREND ANALYSIS  (365-day rolling + decadal linear trend)")
    print("  Dataset  : gb_weather_corrected.csv (ERA5 bias-corrected)")
    print("  Stations : Chilas, Gilgit, Hunza, Khunjerab, Skardu")
    print("  Period   : 1990–2024  |  Break: 2016")
    print("=" * 72)

    print("\nLoading data...")
    stations_data = load_data()
    print(f"  Loaded {len(stations_data)} stations, "
          f"{sum(len(v) for v in stations_data.values()):,} rows total\n")

    all_station_results = {}

    for station, rows in sorted(stations_data.items()):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            elevation = "?"
            for r in csv.DictReader(f):
                if r["station"] == station:
                    elevation = r.get("elevation_m", "?")
                    break

        section(f"STATION: {station.upper()}  (elevation {elevation}m)")

        print(f"\n  Building annual smoothed series (365-day rolling window)...")
        annual = annual_smoothed_means(rows)

        print(f"  Fitting decadal trends (numpy polyfit degree-1)...")
        decade_trends = compute_decadal_trends(annual)

        print(f"  Computing pre-2016 vs post-2016 statistics...")
        pp = pre_post_stats(rows, annual)
        all_station_results[station] = {"annual": annual, "decade_trends": decade_trends, "pre_post": pp}

        # ── Decadal trend table ──
        subsection("DECADAL LINEAR TRENDS  (per decade, from annual smoothed means)")
        print(f"\n  {'Variable':<22} {'1990s':>18} {'2000s':>18} {'2010s':>18} {'2020s*':>16}")
        print(f"  {'':<22} {'slope R²':>18} {'slope R²':>18} {'slope R²':>18} {'slope R²':>16}")
        print("  " + "-" * 70)

        for var in TEMP_VARS + PRECIP_VARS + WIND_VARS + OTHER_VARS:
            if var not in pp:
                continue
            label = VAR_LABELS.get(var, var[:20])
            unit  = UNITS.get(var, "")
            row_parts = [f"  {label:<22}"]
            for decade in ["1990s", "2000s", "2010s", "2020s"]:
                t = decade_trends[decade].get(var, {})
                sl = t.get("slope")
                r2 = t.get("r2")
                if sl is None:
                    row_parts.append(f"{'n/a':>18}")
                else:
                    cell = f"{sl:+.3f}{unit}{sig(r2)}"
                    row_parts.append(f"{cell:>18}")
            print("".join(row_parts))

        print("\n  * 2020s = 2020–2024 only (partial decade, treat with caution)")
        print("  Significance: *** R²≥0.7  ** R²≥0.4  * R²≥0.2")

        # ── Pre/Post 2016 comparison ──
        subsection("PRE-2016 vs POST-2016 COMPARISON  (365-day smoothed annual means)")
        print(f"\n  {'Variable':<22} {'Pre Mean':>10} {'Post Mean':>10} {'Δ Change':>10} "
              f"{'% Change':>10} {'Direction':>10} {'Pre Trend/dec':>15} {'Post Trend/dec':>15}")
        print("  " + "-" * 100)

        for var in TEMP_VARS + PRECIP_VARS + WIND_VARS + OTHER_VARS:
            if var not in pp:
                continue
            p     = pp[var]
            label = VAR_LABELS.get(var, var[:20])
            unit  = UNITS.get(var, "")
            pre_t = p.get("pre_trend_per_decade")
            pst_t = p.get("post_trend_per_decade")
            pre_ts = f"{pre_t:+.3f}{unit}" if pre_t is not None else "n/a"
            pst_ts = f"{pst_t:+.3f}{unit}" if pst_t is not None else "n/a"
            direction = arrow(p["delta"])
            print(f"  {label:<22} {str(p['pre_mean'])+unit:>10} {str(p['post_mean'])+unit:>10} "
                  f"{str(p['delta'])+unit:>10} {str(p['pct_change'])+'%':>10} "
                  f"{direction:>10} {pre_ts:>15} {pst_ts:>15}")

        # ── Key findings ──
        subsection("KEY FINDINGS")

        temp_mean = pp.get("temperature_2m_mean", {})
        precip    = pp.get("precipitation_sum", {})
        snow      = pp.get("snowfall_sum", {})
        cloud     = pp.get("cloud_cover_mean", {})
        rad       = pp.get("shortwave_radiation_sum", {})
        wind      = pp.get("wind_speed_10m_mean", {})
        et0       = pp.get("et0_fao_evapotranspiration", {})

        findings = []

        if temp_mean:
            d     = temp_mean["delta"]
            pct   = temp_mean["pct_change"]
            pre_t = temp_mean.get("pre_trend_per_decade")
            pst_t = temp_mean.get("post_trend_per_decade")
            if pre_t and pst_t:
                findings.append(
                    f"  TEMPERATURE  Mean temp shifted {d:+.2f}°C ({pct:+.1f}%) post-2016.\n"
                    f"               Pre-2016 warming rate: {pre_t:+.3f}°C/decade  →  "
                    f"Post-2016: {pst_t:+.3f}°C/decade"
                )
            else:
                findings.append(f"  TEMPERATURE  Mean temp shifted {d:+.2f}°C ({pct:+.1f}%) post-2016.")

        if precip:
            d   = precip["delta"]
            pct = precip["pct_change"]
            vc  = precip.get("volatility_change", 0)
            findings.append(
                f"  PRECIPITATION  Annual total changed {d:+.2f}mm ({pct:+.1f}%) post-2016.\n"
                f"               Variability (std) {'increased' if vc > 0 else 'decreased'} "
                f"by {abs(vc):.2f}mm — {'more' if vc > 0 else 'less'} erratic rainfall."
            )

        if snow:
            d   = snow["delta"]
            pct = snow["pct_change"]
            findings.append(f"  SNOWFALL     Annual snowfall changed {d:+.2f}cm ({pct:+.1f}%) post-2016.")

        if cloud:
            d = cloud["delta"]
            findings.append(f"  CLOUD COVER  Changed {d:+.1f}% post-2016 "
                            f"({'cloudier' if d > 0 else 'clearer'} skies).")

        if rad:
            d   = rad["delta"]
            pct = rad["pct_change"]
            findings.append(f"  SOLAR RAD    Shortwave radiation changed {d:+.2f}MJ/m² ({pct:+.1f}%) post-2016.")

        if wind:
            d   = wind["delta"]
            pct = wind["pct_change"]
            findings.append(f"  WIND         Mean wind speed changed {d:+.2f}km/h ({pct:+.1f}%) post-2016.")

        if et0:
            d   = et0["delta"]
            pct = et0["pct_change"]
            findings.append(f"  EVAPOTRANS   ET₀ changed {d:+.2f}mm ({pct:+.1f}%) post-2016 "
                            f"— {'more' if d > 0 else 'less'} atmospheric water demand.")

        for f in findings:
            print(f"\n{f}")

    # ── Cross-station summary ──
    section("CROSS-STATION SUMMARY  —  CONSISTENT SIGNALS ACROSS ALL STATIONS")

    vars_to_summarise = TEMP_VARS + PRECIP_VARS + WIND_VARS + OTHER_VARS
    print(f"\n  {'Variable':<22} ", end="")
    for s in sorted(all_station_results):
        print(f"{s[:9]:>10}", end="")
    print(f"  {'GB Mean Δ':>12}  {'Signal':>8}")
    print("  " + "-" * (22 + 10 * len(all_station_results) + 22))

    for var in vars_to_summarise:
        label  = VAR_LABELS.get(var, var[:20])
        unit   = UNITS.get(var, "")
        deltas = []
        row = f"  {label:<22} "
        for s in sorted(all_station_results):
            pp = all_station_results[s]["pre_post"]
            if var in pp:
                d = pp[var]["delta"]
                deltas.append(d)
                row += f"{str(d)+unit:>10}"
            else:
                row += f"{'n/a':>10}"

        if deltas:
            gb_mean    = mean(deltas)
            consistent = all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
            signal     = "CONSISTENT" if consistent else "MIXED"
            row += f"  {str(round(gb_mean,3))+unit:>12}  {signal:>8}"
        print(row)

    print("\n  CONSISTENT = all stations show same direction of change")
    print("  MIXED      = stations differ in direction\n")

    section("ANALYSIS COMPLETE")
    print("  Methodology:")
    print("  • 365-day rolling window applied before all statistics (noise reduction)")
    print("  • Linear trends: numpy.polyfit(degree=1) on annual smoothed means")
    print("  • Trend units: change per decade (slope × 10)")
    print("  • Pre-2016 period: 1990–2015 (26 years)")
    print("  • Post-2016 period: 2016–2024 (9 years)")
    print("  • All data bias-corrected (ERA5 2016 discontinuity removed)")
    print()


if __name__ == "__main__":
    main()
