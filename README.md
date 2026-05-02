### Research Origins
This project is an evolution of my original investigation into Karakoram climate anomalies. You can find the initial discovery of the 2016 structural break including the raw logs where a **4.54°C baseline jump** was first identified in my legacy repository:
https://github.com/arkalibaig/hunza-climate-analysis

# Gilgit-Baltistan Historical Weather Dataset
**Period:** 1990 to 2024 | **Stations:** 5 (8 planned) | **Source:** ERA5 via Open-Meteo

---

## What This Dataset Is

A 35-year daily weather dataset for Gilgit-Baltistan, Pakistan. Fetched from the Open-Meteo Historical Archive API which uses ERA5 reanalysis data from ECMWF. Bias-corrected for the known ERA5 2016 discontinuity before any analysis was done.

---

## Stations

| Station | District | Elevation | Latitude | Longitude | Status |
|---|---|---|---|---|---|
| Gilgit | Gilgit | 1500m | 35.9208 | 74.3083 | Downloaded |
| Skardu | Skardu-Baltistan | 2228m | 35.2971 | 75.6875 | Downloaded |
| Hunza | Hunza | 2438m | 36.3167 | 74.6500 | Downloaded |
| Chilas | Diamer | 1250m | 35.4167 | 74.1000 | Downloaded |
| Khunjerab | Hunza | 4693m | 36.8333 | 75.4167 | Downloaded |
| Astore | Astore | 2168m | 35.3667 | 74.9167 | pending |
| Gupis | Ghizer | 2156m | 36.1667 | 73.4000 | pending |
| Bunji | Astore | 760m | 35.6500 | 74.6333 | pending |

---

## Variables (25 daily)

| Category | Variables |
|---|---|
| Temperature | temperature_2m_max, temperature_2m_min, temperature_2m_mean, apparent_temperature_max, apparent_temperature_min, apparent_temperature_mean |
| Precipitation | precipitation_sum, rain_sum, snowfall_sum, precipitation_hours |
| Wind | wind_speed_10m_max, wind_speed_10m_mean, wind_gusts_10m_max, wind_direction_10m_dominant |
| Solar | shortwave_radiation_sum, et0_fao_evapotranspiration, uv_index_max, sunshine_duration, daylight_duration |
| Sky | cloud_cover_mean, weather_code |
| Astronomical | sunrise, sunset |

---

## The ERA5 2016 Problem

ERA5 reanalysis has a known systematic discontinuity around 2016 caused by updates to the ECMWF data assimilation system and changes in satellite input streams. Over complex mountain terrain like GB this creates a hard step change in temperature and precipitation values — not a real climate signal.

**What it looked like in raw data:**

| Station | Fake jump at 2016 |
|---|---|
| Gilgit | +8.9°C step |
| Skardu | +9.4°C step |
| Hunza | +6.8°C step |
| Chilas | +4.5°C step |
| Khunjerab | +2.7°C step |

**Impact on model training:** A linear regression on raw data over 1990 to 2024 produces a warming trend of +1.42°C per decade for GB. The real corrected answer is +0.09°C per decade. The raw data was 16 times too high.

---

## Bias Correction Method

**Method:** Monthly Delta Bias Correction (per station, per variable)

For additive variables (temperature, wind, radiation):
```
delta(month) = mean_post(month) - mean_pre(month)
corrected_pre = raw_pre + delta(month)
```

For multiplicative variables (precipitation, snowfall):
```
ratio(month) = mean_post(month) / mean_pre(month)
corrected_pre = raw_pre x ratio(month)
```

Why monthly instead of annual: A single annual correction factor would fix one season while breaking another. Monthly deltas correct each season independently and preserve seasonality.

---

## Files

| File | Description |
|---|---|
| fetch_gb_weather.py | Downloads all station data from Open-Meteo API |
| bias_correct.py | Applies monthly delta bias correction |
| trend_analysis.py | Decadal trends + pre/post 2016 comparison |
| visualize_clean.py | Clean accurate plots (annual agg + 3-year rolling) |
| simple_charts.py | Plain-English charts for non-technical readers |
| report.py | Generates GB_Climate_Report.png |
| gb_weather_combined.csv | Raw uncorrected combined dataset |
| gb_weather_corrected.csv | Bias-corrected dataset — use this for training |
| bias_correction_report.json | Full audit trail of all correction factors applied |
| GB_Climate_Report.png | Visual report with findings and reasons |

## Repository Structure

```
gb_weather_analysis/
├── data
│  └──gb_weather_corrected.csv
├── figures
│   ├── bias_correction_visual.png
│   ├── bias_heatmap.png
│   ├── bias_jump_zoom.png
│   ├── chart1_problem.png
│   ├── chart2_decades.png
│   ├── chart3_fake_vs_real.png
│   ├── chart4_timeline.png
│   ├── chart5_rain_snow.png
│   ├── clean_decades.png
│   ├── clean_jump_proof.png
│   ├── clean_precipitation.png
│   ├── clean_temperature.png
│   └── GB_Climate_Report.png
├── README.md
├── reports
│   ├── bias_correction_report.json
│   ├── gb_weather_summary.json
│   └── report.py
├── requirements.txt
└── src
    ├── actual_trend.py
    ├── bias_correct.py
    ├── fetch_gb_weather.py
    ├── simple_charts.py
    ├── trend_analysis.py
    ├── visualize_bias.py
    └── visualize_clean.py

```

---

## Key Findings

**Temperature**
Real warming rate is +0.09°C per decade across GB. Over 35 years that is approximately +0.3°C total. Consistent with IPCC Hindu Kush Himalaya regional estimates of 0.2 to 0.5°C per decade for high mountain Asia. Valley stations warm faster than high-altitude stations. Pre-2016 most high-altitude stations showed flat or slightly cooling trends. Post-2016 all stations show accelerating warming.

**Rainfall**
Annual rainfall dropped 2 to 6 percent across most stations compared to the 1990s. Variability increased — rain arrives in heavier shorter bursts rather than steady showers. No consistent regional drying or wetting signal; GB complex terrain fragments precipitation patterns.

**Snowfall**
Stations below 2,500m (Gilgit, Chilas, Skardu) recorded 5 to 9 percent less snowfall per year. Higher stations like Khunjerab saw a small increase. Rain is replacing snow at lower elevations as the freezing level climbs higher each decade.

**Reasons for changes**
1. Global greenhouse gas emissions driving background warming
2. Altitude amplification — thin cold air magnifies temperature changes
3. Black carbon soot from South Asian pollution settling on glaciers
4. Shrinking snow cover exposing heat-absorbing dark rock
5. Weakening Western Disturbances delivering less winter moisture
6. Indian Monsoon shifting later and shorter each year
7. Jet stream moving northward pushing storm tracks away from GB
8. Karakoram Anomaly (glacier growth phenomenon) weakening

---

## For Model Training

Use `gb_weather_corrected.csv` as the primary dataset.

**Column guidance:**
- `bias_corrected` = 1 means this row was adjusted (pre-2016). Keep as a feature.
- `era5_period` = pre_2016 or post_2016. Include as categorical feature.
- Do not use `gb_weather_combined.csv` for training — it contains the uncorrected jump.

**Noise reduction used in analysis:**
1. Aggregate daily data to annual means
2. Apply 3-year rolling mean on annual data
3. Fit linear trends via numpy polyfit on smoothed annual series

---

## Pending Work

- Re-run `fetch_gb_weather.py` to download Astore, Gupis and Bunji (rate-limited during first run)
- Re-run `bias_correct.py` after downloading the remaining 3 stations
- These stations cover the eastern valleys and Ghizer district which have different precipitation patterns than the Karakoram corridor stations

---

## Data Sources and License

- **API:** Open-Meteo Historical Weather API (free, no key required)
- **Underlying data:** ERA5 reanalysis, ECMWF
- **License:** CC BY 4.0 (Open-Meteo) | ERA5 © Copernicus Climate Change Service
- **API endpoint:** https://archive-api.open-meteo.com/v1/archive
