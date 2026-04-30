#!/usr/bin/env python3
"""
Gilgit-Baltistan Historical Weather Dataset
============================================
Source  : Open-Meteo Historical Weather API (ERA5 reanalysis)
Coverage: 1990-01-01 to 2024-12-31  (~35 years)
Stations: 6 key locations across GB
Output  : CSV per station + combined CSV + summary JSON

Variables fetched (daily):
  - temperature_2m_max / min / mean     (°C)
  - apparent_temperature_max / min      (°C, feels-like)
  - precipitation_sum                   (mm)
  - snowfall_sum                        (cm)
  - rain_sum                            (mm)
  - snow_depth                          (m)  — ERA5 Land
  - wind_speed_10m_max                  (km/h)
  - wind_gusts_10m_max                  (km/h)
  - wind_direction_10m_dominant         (°)
  - shortwave_radiation_sum             (MJ/m²)
  - et0_fao_evapotranspiration          (mm)
  - sunrise / sunset                    (ISO8601)
  - daylight_duration                   (seconds)
  - sunshine_duration                   (seconds)
  - uv_index_max                        (0-11+)
  - cloud_cover_mean                    (%)
  - relative_humidity_2m_mean           (%)
  - pressure_msl_mean                   (hPa)
  - soil_temperature_0_to_7cm_mean      (°C)
  - soil_moisture_0_to_7cm_mean         (m³/m³)
  - freezing_level_height_mean          (m)
"""

import requests
import json
import csv
import os
import time
from datetime import datetime, date

# ── Configuration ─────────────────────────────────────────────────────────────
START_DATE = "1990-01-01"
END_DATE   = "2024-12-31"
OUT_DIR    = os.path.dirname(os.path.abspath(__file__))

STATIONS = [
    {"name": "Gilgit",    "lat": 35.9208, "lon": 74.3083, "elevation": 1500, "district": "Gilgit"},
    {"name": "Skardu",    "lat": 35.2971, "lon": 75.6875, "elevation": 2228, "district": "Skardu-Baltistan"},
    {"name": "Hunza",     "lat": 36.3167, "lon": 74.6500, "elevation": 2438, "district": "Hunza"},
    {"name": "Astore",    "lat": 35.3667, "lon": 74.9167, "elevation": 2168, "district": "Astore"},
    {"name": "Gupis",     "lat": 36.1667, "lon": 73.4000, "elevation": 2156, "district": "Ghizer"},
    {"name": "Khunjerab", "lat": 36.8333, "lon": 75.4167, "elevation": 4693, "district": "Hunza"},
    {"name": "Chilas",    "lat": 35.4167, "lon": 74.1000, "elevation": 1250, "district": "Diamer"},
    {"name": "Bunji",     "lat": 35.6500, "lon": 74.6333, "elevation": 760,  "district": "Astore"},
]

DAILY_VARS = [
    # Temperature
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "apparent_temperature_mean",
    # Precipitation
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    # Wind
    "wind_speed_10m_max",
    "wind_speed_10m_mean",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    # Solar / radiation
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "uv_index_max",
    "sunshine_duration",
    "daylight_duration",
    # Sky / cloud
    "cloud_cover_mean",
    # Astronomical
    "sunrise",
    "sunset",
    # Weather code (WMO)
    "weather_code",
]

# ERA5 reanalysis has a known discontinuity around 2016 (model/assimilation
# update) that causes systematic shifts in precipitation and temperature over
# complex mountain terrain. We flag each row so models can account for it.
ERA5_BREAK_DATE = "2016-01-01"

API_URL = "https://archive-api.open-meteo.com/v1/archive"

# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch_station(station):
    """Fetch full historical data for one station."""
    params = {
        "latitude":        station["lat"],
        "longitude":       station["lon"],
        "start_date":      START_DATE,
        "end_date":        END_DATE,
        "daily":           ",".join(DAILY_VARS),
        "timezone":        "Asia/Karachi",
        "temperature_unit":"celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    print(f"  Fetching {station['name']:12s} ({station['lat']:.4f}N, {station['lon']:.4f}E, {station['elevation']}m)...", end="", flush=True)
    t0 = time.time()

    for attempt in range(5):
        try:
            r = requests.get(API_URL, params=params, timeout=90)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f" rate-limited, waiting {wait}s...", end="", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except requests.exceptions.RequestException as e:
            if attempt < 4:
                time.sleep(15)
                continue
            print(f" FAILED: {e}")
            return None
    else:
        print(f" FAILED after retries")
        return None

    elapsed = time.time() - t0
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    print(f" {len(dates):,} days ({elapsed:.1f}s)")
    return daily

def era5_period(date_str):
    """Flag ERA5 reanalysis period to mark the known 2016 discontinuity."""
    return "post_2016" if date_str >= ERA5_BREAK_DATE else "pre_2016"

def save_station_csv(station, daily):
    """Save per-station CSV."""
    dates = daily.get("time", [])
    if not dates:
        return 0

    fname = os.path.join(OUT_DIR, f"{station['name'].lower()}_weather.csv")
    header = ["date", "era5_period", "station", "district", "lat", "lon", "elevation_m"] + DAILY_VARS

    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, d in enumerate(dates):
            row = [
                d,
                era5_period(d),
                station["name"],
                station["district"],
                station["lat"],
                station["lon"],
                station["elevation"],
            ]
            for var in DAILY_VARS:
                vals = daily.get(var, [])
                row.append(vals[i] if i < len(vals) else "")
            w.writerow(row)

    return len(dates)

def save_combined_csv(all_data):
    """Save one big combined CSV with all stations."""
    fname = os.path.join(OUT_DIR, "gb_weather_combined.csv")
    header = ["date", "era5_period", "station", "district", "lat", "lon", "elevation_m"] + DAILY_VARS

    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for station, daily in all_data:
            dates = daily.get("time", [])
            for i, d in enumerate(dates):
                row = [
                    d,
                    era5_period(d),
                    station["name"],
                    station["district"],
                    station["lat"],
                    station["lon"],
                    station["elevation"],
                ]
                for var in DAILY_VARS:
                    vals = daily.get(var, [])
                    row.append(vals[i] if i < len(vals) else "")
                w.writerow(row)

    return fname

def compute_summary(all_data):
    """Compute station-level climate summaries."""
    summaries = []
    for station, daily in all_data:
        temps    = [v for v in daily.get("temperature_2m_mean", []) if v is not None]
        tmax     = [v for v in daily.get("temperature_2m_max",  []) if v is not None]
        tmin     = [v for v in daily.get("temperature_2m_min",  []) if v is not None]
        precip   = [v for v in daily.get("precipitation_sum",   []) if v is not None]
        snow     = [v for v in daily.get("snowfall_sum",        []) if v is not None]
        wind     = [v for v in daily.get("wind_speed_10m_max",  []) if v is not None]
        humidity = [v for v in daily.get("relative_humidity_2m_mean", []) if v is not None]
        freeze   = [v for v in daily.get("freezing_level_height_mean",[]) if v is not None]

        frost_days  = sum(1 for t in tmin if t <= 0)
        hot_days    = sum(1 for t in tmax if t >= 35)
        rain_days   = sum(1 for p in precip if p > 1)
        heavy_rain  = sum(1 for p in precip if p >= 20)
        snow_days   = sum(1 for s in snow if s > 0)

        summaries.append({
            "station":             station["name"],
            "district":            station["district"],
            "lat":                 station["lat"],
            "lon":                 station["lon"],
            "elevation_m":         station["elevation"],
            "period":              f"{START_DATE} to {END_DATE}",
            "total_days":          len(daily.get("time", [])),
            "climate": {
                "temp_mean_c":          round(sum(temps)/len(temps), 2) if temps else None,
                "temp_max_ever_c":      round(max(tmax), 1) if tmax else None,
                "temp_min_ever_c":      round(min(tmin), 1) if tmin else None,
                "annual_precip_mm":     round(sum(precip) / (len(daily.get("time",[]))/365.25), 1) if precip else None,
                "annual_snowfall_cm":   round(sum(snow)   / (len(daily.get("time",[]))/365.25), 1) if snow else None,
                "frost_days_per_year":  round(frost_days / (len(daily.get("time",[]))/365.25), 1) if tmin else None,
                "hot_days_per_year":    round(hot_days   / (len(daily.get("time",[]))/365.25), 1) if tmax else None,
                "rain_days_per_year":   round(rain_days  / (len(daily.get("time",[]))/365.25), 1) if precip else None,
                "heavy_rain_days_yr":   round(heavy_rain / (len(daily.get("time",[]))/365.25), 1) if precip else None,
                "snow_days_per_year":   round(snow_days  / (len(daily.get("time",[]))/365.25), 1) if snow else None,
                "wind_max_kmh":         round(max(wind), 1) if wind else None,
                "wind_mean_max_kmh":    round(sum(wind)/len(wind), 1) if wind else None,
                "humidity_mean_pct":    round(sum(humidity)/len(humidity), 1) if humidity else None,
                "freeze_level_mean_m":  round(sum(freeze)/len(freeze)) if freeze else None,
            }
        })
    return summaries

def save_summary(summaries):
    fname = os.path.join(OUT_DIR, "gb_weather_summary.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "title":       "Gilgit-Baltistan Historical Weather Dataset",
                "source":      "Open-Meteo Historical Weather API (ERA5 reanalysis, ECMWF)",
                "period":      f"{START_DATE} to {END_DATE}",
                "generated":   datetime.utcnow().isoformat() + "Z",
                "variables":   DAILY_VARS,
                "stations":    len(summaries),
                "license":     "CC BY 4.0 (Open-Meteo) — ERA5 © Copernicus Climate Change Service",
                "data_quality_notes": {
                    "era5_discontinuity": {
                        "break_date": ERA5_BREAK_DATE,
                        "description": (
                            "ERA5 reanalysis has a known systematic discontinuity around 2016 "
                            "caused by updates to the ECMWF data assimilation system and changes "
                            "in satellite input streams. Over complex terrain like Gilgit-Baltistan "
                            "this manifests as jumps in precipitation totals and temperature bias. "
                            "The 'era5_period' column flags pre_2016 vs post_2016 rows. "
                            "For ML training: either (a) use post-2016 data only, "
                            "(b) add era5_period as a categorical feature, or "
                            "(c) apply per-station bias correction between periods."
                        ),
                        "affected_variables": [
                            "precipitation_sum", "rain_sum", "snowfall_sum",
                            "temperature_2m_mean", "cloud_cover_mean"
                        ],
                        "recommendation": "Use era5_period as a covariate or train only on post_2016 data."
                    },
                    "mountain_terrain": (
                        "ERA5 grid resolution (~9km) cannot fully resolve the extreme "
                        "elevation gradients of GB. Values at high-altitude stations like "
                        "Khunjerab (4693m) should be treated as area-averaged estimates."
                    ),
                }
            },
            "stations": summaries,
        }, f, indent=2, ensure_ascii=False)
    return fname

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Gilgit-Baltistan Weather Dataset Fetcher")
    print(f"  Period : {START_DATE}  →  {END_DATE}")
    print(f"  Output : {OUT_DIR}")
    print("=" * 60)

    all_data = []
    total_rows = 0

    for station in STATIONS:
        # Skip if already fetched
        existing = os.path.join(OUT_DIR, f"{station['name'].lower()}_weather.csv")
        if os.path.exists(existing):
            print(f"  Skipping   {station['name']:12s} (already downloaded)")
            # reload from disk
            import collections
            daily_reload = collections.defaultdict(list)
            with open(existing, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    for var in ["time"] + DAILY_VARS:
                        key = "date" if var == "time" else var
                        daily_reload.setdefault(var if var != "time" else "time", [])
                        daily_reload["time" if var == "time" else var].append(row.get(key if var != "time" else "date", ""))
            all_data.append((station, dict(daily_reload)))
            total_rows += len(daily_reload.get("time", []))
            continue

        daily = fetch_station(station)
        if daily is None:
            continue
        n = save_station_csv(station, daily)
        total_rows += n
        all_data.append((station, daily))
        time.sleep(12)  # respect rate limits (free tier ~5 req/min)

    if not all_data:
        print("\nNo data fetched. Check your internet connection.")
        return

    print("\nSaving combined dataset...")
    combined_path = save_combined_csv(all_data)

    print("Computing climate summaries...")
    summaries = compute_summary(all_data)
    summary_path = save_summary(summaries)

    print("\n" + "=" * 60)
    print("  DONE")
    print(f"  Total rows   : {total_rows:,}")
    print(f"  Stations     : {len(all_data)}")
    print(f"  Combined CSV : {os.path.basename(combined_path)}")
    print(f"  Summary JSON : {os.path.basename(summary_path)}")
    print("=" * 60)
    print("\nClimate Highlights:")
    for s in summaries:
        c = s["climate"]
        print(f"\n  {s['station']:12s} ({s['elevation_m']}m)")
        print(f"    Mean temp      : {c['temp_mean_c']} °C")
        print(f"    Max ever       : {c['temp_max_ever_c']} °C")
        print(f"    Min ever       : {c['temp_min_ever_c']} °C")
        print(f"    Annual precip  : {c['annual_precip_mm']} mm")
        print(f"    Annual snow    : {c['annual_snowfall_cm']} cm")
        print(f"    Frost days/yr  : {c['frost_days_per_year']}")
        print(f"    Snow days/yr   : {c['snow_days_per_year']}")

if __name__ == "__main__":
    main()
