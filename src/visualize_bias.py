#!/usr/bin/env python3
"""
ERA5 2016 Discontinuity — Visual Proof of Jump + Fix
=====================================================
Plots raw vs corrected data with 365-day rolling window
for all 5 stations and key variables.

Output: bias_correction_visual.png
"""

import csv
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from collections import defaultdict
from datetime import datetime

RAW_FILE  = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_combined.csv"
CORR_FILE = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_corrected.csv"
OUT_PNG   = "/Users/mac/Desktop/gb_weather_dataset/bias_correction_visual.png"

STATIONS  = ["Gilgit", "Skardu", "Hunza", "Chilas", "Khunjerab"]
BREAK     = datetime(2016, 1, 1)

# Colours
C_RAW    = "#e07b54"   # warm orange — raw/broken
C_CORR   = "#4a90d9"   # cool blue   — corrected
C_BREAK  = "#cc3333"   # red dashed  — 2016 line
C_SHADE  = "#ffeeee"   # light pink  — pre-2016 zone
C_BG     = "#f8f9fb"

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None

def rolling(dates, vals, window=365):
    """Return (dates, smoothed_vals) using centred rolling mean."""
    n    = len(vals)
    half = window // 2
    out  = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        w  = [v for v in vals[lo:hi] if v is not None]
        out.append(sum(w) / len(w) if w else None)
    return dates, out

def load(filepath, var):
    """Load {station: (dates, values)} for one variable."""
    data = defaultdict(lambda: ([], []))
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d")
            except ValueError:
                continue
            s = row.get("station", "")
            v = safe_float(row.get(var))
            data[s][0].append(d)
            data[s][1].append(v)
    return dict(data)

# ── Main plot ─────────────────────────────────────────────────────────────────
def main():
    print("Loading raw data ...")
    raw_temp   = load(RAW_FILE,  "temperature_2m_mean")
    raw_precip = load(RAW_FILE,  "precipitation_sum")

    print("Loading corrected data ...")
    cor_temp   = load(CORR_FILE, "temperature_2m_mean")
    cor_precip = load(CORR_FILE, "precipitation_sum")

    n_stations = len(STATIONS)

    # Layout: 2 variable columns × n_stations rows  + 1 summary row at top
    fig = plt.figure(figsize=(20, 4 + 4 * n_stations), facecolor=C_BG)
    fig.suptitle(
        "ERA5 2016 Discontinuity — Raw vs Bias-Corrected  |  Gilgit-Baltistan  1990–2024\n"
        "365-day rolling mean applied to reveal systematic jump",
        fontsize=15, fontweight="bold", y=0.995, va="top"
    )

    gs = GridSpec(
        n_stations, 2,
        figure=fig,
        hspace=0.55, wspace=0.28,
        top=0.96, bottom=0.04, left=0.07, right=0.97
    )

    for row_i, station in enumerate(STATIONS):
        for col_i, (var_label, raw_d, cor_d) in enumerate([
            ("Mean Temperature (°C)",  raw_temp,   cor_temp),
            ("Precipitation Sum (mm)", raw_precip, cor_precip),
        ]):
            ax = fig.add_subplot(gs[row_i, col_i])
            ax.set_facecolor(C_BG)
            ax.spines[["top","right"]].set_visible(False)

            if station not in raw_d:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        transform=ax.transAxes, color="gray")
                continue

            dates_r, vals_r = raw_d[station]
            dates_c, vals_c = cor_d[station]

            _, smooth_r = rolling(dates_r, vals_r)
            _, smooth_c = rolling(dates_c, vals_c)

            # Shade pre-2016 region
            ax.axvspan(dates_r[0], BREAK, color=C_SHADE, alpha=0.6, zorder=0)

            # Raw line
            ax.plot(dates_r, smooth_r, color=C_RAW,  lw=1.4, alpha=0.85,
                    label="Raw (broken)", zorder=2)
            # Corrected line
            ax.plot(dates_c, smooth_c, color=C_CORR, lw=1.6, alpha=0.90,
                    label="Corrected",   zorder=3, linestyle="--")

            # 2016 break line
            ax.axvline(BREAK, color=C_BREAK, lw=1.5, linestyle=":", zorder=4)

            # Annotate the jump
            # Find mean of last 2 years of raw pre-2016 vs first 2 years post-2016
            pre_vals  = [v for d, v in zip(dates_r, smooth_r)
                         if v is not None and datetime(2014,1,1) <= d < BREAK]
            post_vals = [v for d, v in zip(dates_r, smooth_r)
                         if v is not None and BREAK <= d < datetime(2018,1,1)]
            if pre_vals and post_vals:
                jump = (sum(post_vals)/len(post_vals)) - (sum(pre_vals)/len(pre_vals))
                unit = "°C" if "Temp" in var_label else "mm"
                arrow_y = sum(post_vals)/len(post_vals)
                ax.annotate(
                    f"Jump: {jump:+.2f}{unit}",
                    xy=(BREAK, arrow_y),
                    xytext=(20, 0),
                    textcoords="offset points",
                    fontsize=8, color=C_BREAK, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=C_BREAK, lw=1.2),
                    va="center"
                )

            # Compute residual (how much correction closed the gap)
            post_raw  = [v for d, v in zip(dates_r, smooth_r)
                         if v is not None and BREAK <= d < datetime(2020,1,1)]
            post_cor  = [v for d, v in zip(dates_c, smooth_c)
                         if v is not None and BREAK <= d < datetime(2020,1,1)]
            if post_raw and post_cor:
                residual = abs((sum(post_raw)/len(post_raw)) - (sum(post_cor)/len(post_cor)))
                unit = "°C" if "Temp" in var_label else "mm"
                ax.text(0.97, 0.06,
                        f"Post-2016 residual: {residual:.3f}{unit}",
                        transform=ax.transAxes, fontsize=7.5,
                        ha="right", va="bottom", color="#555",
                        bbox=dict(fc="white", ec="#ccc", pad=2, alpha=0.8))

            # Labels
            elev_map = {"Gilgit": 1500, "Skardu": 2228, "Hunza": 2438,
                        "Chilas": 1250, "Khunjerab": 4693}
            elev = elev_map.get(station, "?")
            if col_i == 0:
                ax.set_ylabel(f"{station}\n({elev}m)", fontsize=9, fontweight="bold",
                              rotation=90, labelpad=6)
            if row_i == 0:
                ax.set_title(var_label, fontsize=11, fontweight="bold", pad=8)

            ax.set_xlim(dates_r[0], dates_r[-1])
            ax.tick_params(axis="both", labelsize=7.5)
            ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(5))
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))

            if row_i == 0 and col_i == 0:
                ax.legend(fontsize=8, loc="upper left", framealpha=0.85,
                          handles=[
                              mpatches.Patch(color=C_RAW,  label="Raw (with jump)"),
                              mpatches.Patch(color=C_CORR, label="Bias-corrected"),
                              mpatches.Patch(color=C_SHADE, alpha=0.6, label="Pre-2016 period"),
                          ])

    # ── Bottom annotation ──────────────────────────────────────────────────────
    fig.text(
        0.5, 0.005,
        "Method: Monthly delta bias correction  |  Additive for temperature  |  "
        "Multiplicative for precipitation  |  ERA5 © ECMWF via Open-Meteo",
        ha="center", fontsize=8, color="#777"
    )

    print(f"Saving → {OUT_PNG}")
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print("Done.")

    # ── Also produce a focused 'jump zoom' plot ────────────────────────────────
    plot_jump_zoom(raw_temp, cor_temp, raw_precip, cor_precip)

def plot_jump_zoom(raw_temp, cor_temp, raw_precip, cor_precip):
    """Zoomed ±4 years around 2016 break showing the discontinuity clearly."""
    OUT2 = "/Users/mac/Desktop/gb_weather_dataset/bias_jump_zoom.png"

    WIN_START = datetime(2012, 1, 1)
    WIN_END   = datetime(2020, 6, 1)

    fig, axes = plt.subplots(2, len(STATIONS), figsize=(22, 8), facecolor=C_BG)
    fig.suptitle(
        "ERA5 2016 Jump — Zoomed View ±4 Years Around Break\n"
        "Orange = raw data with discontinuity  |  Blue dashed = bias-corrected",
        fontsize=13, fontweight="bold", y=1.01
    )

    for col_i, station in enumerate(STATIONS):
        elev_map = {"Gilgit": 1500, "Skardu": 2228, "Hunza": 2438,
                    "Chilas": 1250, "Khunjerab": 4693}
        elev = elev_map.get(station, "?")

        for row_i, (var_label, raw_d, cor_d, unit) in enumerate([
            ("Mean Temp (°C)",   raw_temp,   cor_temp,   "°C"),
            ("Precip (mm/day)",  raw_precip, cor_precip, "mm"),
        ]):
            ax = axes[row_i][col_i]
            ax.set_facecolor(C_BG)
            ax.spines[["top","right"]].set_visible(False)

            if station not in raw_d:
                ax.axis("off")
                continue

            dates_r, vals_r = raw_d[station]
            dates_c, vals_c = cor_d[station]

            _, smooth_r = rolling(dates_r, vals_r)
            _, smooth_c = rolling(dates_c, vals_c)

            # Clip to zoom window
            mask_r = [(d, v) for d, v in zip(dates_r, smooth_r)
                      if WIN_START <= d <= WIN_END]
            mask_c = [(d, v) for d, v in zip(dates_c, smooth_c)
                      if WIN_START <= d <= WIN_END]

            if not mask_r:
                continue

            dr, vr = zip(*[(d, v) for d, v in mask_r if v is not None])
            dc, vc = zip(*[(d, v) for d, v in mask_c if v is not None])

            ax.axvspan(WIN_START, BREAK, color=C_SHADE, alpha=0.5)
            ax.plot(dr, vr, color=C_RAW,  lw=2.0, alpha=0.9, label="Raw")
            ax.plot(dc, vc, color=C_CORR, lw=2.0, alpha=0.9, label="Corrected",
                    linestyle="--")
            ax.axvline(BREAK, color=C_BREAK, lw=2, linestyle=":")

            # Measure the jump at break
            pre_w  = [v for d, v in zip(dr, vr)
                      if datetime(2014,6,1) <= d < BREAK]
            post_w = [v for d, v in zip(dr, vr)
                      if BREAK <= d < datetime(2017,6,1)]
            if pre_w and post_w:
                jump = (sum(post_w)/len(post_w)) - (sum(pre_w)/len(pre_w))
                mid_y = max(vr) * 0.97 if row_i == 0 else max(vr) * 0.95
                ax.text(BREAK, mid_y, f" {jump:+.2f}{unit}",
                        color=C_BREAK, fontsize=9, fontweight="bold", va="top")

            # Fill area between raw and corrected (shows magnitude of correction)
            all_dates = sorted(set(dr) & set(dc))
            r_interp = {d: v for d, v in zip(dr, vr)}
            c_interp = {d: v for d, v in zip(dc, vc)}
            common_dates = [d for d in all_dates if d in r_interp and d in c_interp]
            if common_dates:
                yr = [r_interp[d] for d in common_dates]
                yc = [c_interp[d] for d in common_dates]
                ax.fill_between(common_dates, yr, yc, alpha=0.12, color="#9b59b6",
                                label="Correction magnitude")

            if row_i == 0:
                ax.set_title(f"{station}\n({elev}m)", fontsize=10, fontweight="bold")
            if col_i == 0:
                ax.set_ylabel(var_label, fontsize=9)

            ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(2))
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
            ax.tick_params(axis="both", labelsize=8)

            if row_i == 0 and col_i == 0:
                ax.legend(fontsize=8, loc="lower left", framealpha=0.85)

    plt.tight_layout()
    print(f"Saving → {OUT2}")
    fig.savefig(OUT2, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print("Done.")

    # ── Third plot: per-station monthly correction heatmap ────────────────────
    plot_correction_heatmap()

def plot_correction_heatmap():
    """Show the monthly correction deltas as a heatmap — temperature and precip ratio."""
    import json
    OUT3 = "/Users/mac/Desktop/gb_weather_dataset/bias_heatmap.png"

    with open("/Users/mac/Desktop/gb_weather_dataset/bias_correction_report.json") as f:
        report = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(16, 5), facecolor=C_BG)
    fig.suptitle("Bias Correction Magnitudes by Station & Month\n"
                 "Left: Temperature delta (°C)  |  Right: Precipitation ratio (×)",
                 fontsize=12, fontweight="bold")

    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    for ax_i, (var, label, fmt, cmap) in enumerate([
        ("temperature_2m_mean", "Temp Δ (°C)", ".2f", "RdBu_r"),
        ("precipitation_sum",   "Precip ratio (×)", ".3f", "PuOr"),
    ]):
        matrix = []
        row_labels = []

        for station in STATIONS:
            if station not in report["stations"]:
                continue
            details = report["stations"][station].get("variable_details", {})
            if var not in details:
                continue
            var_detail = details[var]
            row = []
            for m in range(1, 13):
                month_data = var_detail.get("months", {}).get(str(m), {})
                corr = month_data.get("correction", 0.0)
                row.append(corr)
            matrix.append(row)
            row_labels.append(station)

        if not matrix:
            ax_i_ax = axes[ax_i]
            ax_i_ax.text(0.5, 0.5, "No data", ha="center", va="center",
                         transform=ax_i_ax.transAxes)
            continue

        mat = np.array(matrix)
        ax  = axes[ax_i]

        # Centre colormap at 0 for delta, at 1.0 for ratio
        vcenter = 0.0 if ax_i == 0 else 1.0
        vmax = max(abs(mat.min() - vcenter), abs(mat.max() - vcenter))
        vmin = vcenter - vmax
        vmax = vcenter + vmax

        im = ax.imshow(mat, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

        ax.set_xticks(range(12))
        ax.set_xticklabels(months, fontsize=9)
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, fontsize=9)
        ax.set_title(label, fontsize=10, pad=8)

        # Annotate cells
        for r in range(len(row_labels)):
            for c in range(12):
                val = mat[r, c]
                text_col = "white" if abs(val - vcenter) > vmax * 0.5 else "black"
                ax.text(c, r, f"{val:{fmt}}", ha="center", va="center",
                        fontsize=7.5, color=text_col, fontweight="bold")

        plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)

    plt.tight_layout()
    print(f"Saving → {OUT3}")
    fig.savefig(OUT3, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print("Done.")

if __name__ == "__main__":
    main()
