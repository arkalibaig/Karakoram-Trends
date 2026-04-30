#!/usr/bin/env python3
"""
ERA5 2016 Discontinuity — Clean Accurate Visualization
=======================================================
Noise reduction pipeline:
  1. Aggregate daily → annual means (removes seasonal cycle entirely)
  2. Apply 3-year rolling mean on annual data (smooths inter-annual noise)
  3. Fit separate linear trends pre/post 2016 via numpy polyfit
  4. Show annual dots + smoothed line + trend lines + jump quantification

Output files:
  clean_temperature.png   — temperature all stations
  clean_precipitation.png — precipitation all stations
  clean_jump_proof.png    — side-by-side raw vs corrected jump proof
"""

import csv, math, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from collections import defaultdict
from datetime import datetime

RAW_FILE  = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_combined.csv"
CORR_FILE = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_corrected.csv"
REPORT    = "/Users/mac/Desktop/gb_weather_dataset/bias_correction_report.json"

STATIONS  = ["Gilgit", "Skardu", "Hunza", "Chilas", "Khunjerab"]
ELEVATIONS= {"Gilgit":1500,"Skardu":2228,"Hunza":2438,"Chilas":1250,"Khunjerab":4693}
BREAK     = 2016

PALETTE = {
    "Gilgit":    "#e74c3c",
    "Skardu":    "#3498db",
    "Hunza":     "#2ecc71",
    "Chilas":    "#f39c12",
    "Khunjerab": "#9b59b6",
}

C_BG     = "#ffffff"
C_GRID   = "#eeeeee"
C_BREAK  = "#cc0000"
C_PRE    = "#fdecea"
C_POST   = "#eaf4fb"

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None

def annual_agg(filepath, var, agg="mean"):
    """Daily CSV → {station: {year: value}}"""
    buckets = defaultdict(lambda: defaultdict(list))
    with open(filepath, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                yr = int(row["date"][:4])
            except (ValueError, KeyError):
                continue
            v = safe_float(row.get(var))
            if v is not None:
                buckets[row["station"]][yr].append(v)
    result = {}
    for station, years in buckets.items():
        result[station] = {}
        for yr, vals in years.items():
            if agg == "mean":
                result[station][yr] = sum(vals) / len(vals)
            elif agg == "sum":
                result[station][yr] = sum(vals)
    return result

def rolling3(years, vals):
    """3-year centred rolling mean on annual series."""
    out = []
    for i, (y, v) in enumerate(zip(years, vals)):
        window = [vals[j] for j in range(max(0,i-1), min(len(vals),i+2))
                  if vals[j] is not None]
        out.append(sum(window)/len(window) if window else None)
    return out

def fit_trend(years, vals):
    """Linear trend via polyfit. Returns (years_fine, fitted, slope, intercept, r2)."""
    pairs = [(y,v) for y,v in zip(years,vals) if v is not None]
    if len(pairs) < 3:
        return None
    y_arr = np.array([p[0] for p in pairs], dtype=float)
    v_arr = np.array([p[1] for p in pairs], dtype=float)
    coeffs = np.polyfit(y_arr, v_arr, 1)
    fitted  = np.polyval(coeffs, y_arr)
    ss_res  = np.sum((v_arr - fitted)**2)
    ss_tot  = np.sum((v_arr - np.mean(v_arr))**2)
    r2      = 1 - ss_res/ss_tot if ss_tot > 0 else 0
    yf      = np.linspace(y_arr[0], y_arr[-1], 200)
    return yf, np.polyval(coeffs, yf), coeffs[0], coeffs[1], r2

def style_ax(ax, title="", ylabel="", xlabel=True):
    ax.set_facecolor(C_BG)
    ax.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#cccccc")
    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color="#444")
    if xlabel:
        ax.set_xlabel("Year", fontsize=8, color="#666")
    ax.tick_params(axis="both", labelsize=8, color="#aaa")

# ── Plot 1: Temperature — all stations, raw vs corrected ─────────────────────
def plot_temperature():
    print("  Building temperature plot...")
    raw  = annual_agg(RAW_FILE,  "temperature_2m_mean", "mean")
    corr = annual_agg(CORR_FILE, "temperature_2m_mean", "mean")

    fig, axes = plt.subplots(len(STATIONS), 2, figsize=(18, 4*len(STATIONS)),
                              facecolor=C_BG, sharex=False)
    fig.suptitle("Mean Temperature — Raw ERA5  vs  Bias-Corrected\n"
                 "Annual means + 3-year rolling smooth + linear trend lines (pre/post 2016)",
                 fontsize=14, fontweight="bold", y=1.005)

    for row_i, station in enumerate(STATIONS):
        elev = ELEVATIONS[station]
        col  = PALETTE[station]

        for col_i, (data, panel_label) in enumerate([
            (raw,  "RAW  (with ERA5 2016 jump)"),
            (corr, "CORRECTED  (jump removed)"),
        ]):
            ax = axes[row_i][col_i]
            style_ax(ax, ylabel=f"{station} ({elev}m)\nTemp (°C)" if col_i==0 else "")

            if station not in data:
                ax.text(0.5,0.5,"No data",ha="center",va="center",transform=ax.transAxes)
                continue

            ydict = data[station]
            years = sorted(ydict)
            vals  = [ydict[y] for y in years]
            smooth= rolling3(years, vals)

            pre_years  = [y for y in years if y < BREAK]
            post_years = [y for y in years if y >= BREAK]
            pre_vals   = [ydict[y] for y in pre_years]
            post_vals  = [ydict[y] for y in post_years]
            pre_smooth = [smooth[i] for i,y in enumerate(years) if y < BREAK]
            post_smooth= [smooth[i] for i,y in enumerate(years) if y >= BREAK]

            # Background zones
            ax.axvspan(min(years), BREAK,      color=C_PRE,  alpha=0.7, zorder=0)
            ax.axvspan(BREAK,      max(years), color=C_POST, alpha=0.7, zorder=0)
            ax.axvline(BREAK, color=C_BREAK, lw=1.8, linestyle="--", zorder=5)

            # Annual dots (muted)
            ax.scatter(years, vals, color=col, s=12, alpha=0.3, zorder=2)

            # 3-year smooth line
            smooth_valid = [(y,v) for y,v in zip(years,smooth) if v is not None]
            if smooth_valid:
                sy, sv = zip(*smooth_valid)
                ax.plot(sy, sv, color=col, lw=2.2, alpha=0.85, zorder=3,
                        label="3-yr rolling mean")

            # Pre-trend line
            tr_pre = fit_trend(pre_years, pre_vals)
            if tr_pre:
                yf, vf, slope, _, r2 = tr_pre
                ax.plot(yf, vf, color="#555555", lw=1.8, linestyle="-",
                        zorder=4, alpha=0.9)
                ax.text(pre_years[len(pre_years)//2], min(vals)*0.995,
                        f"trend: {slope*10:+.2f}°C/dec\nR²={r2:.2f}",
                        fontsize=7.5, color="#333", ha="center",
                        bbox=dict(fc="white", ec="#ccc", pad=2, alpha=0.85))

            # Post-trend line
            tr_post = fit_trend(post_years, post_vals)
            if tr_post:
                yf, vf, slope, _, r2 = tr_post
                ax.plot(yf, vf, color="#222222", lw=1.8, linestyle="-",
                        zorder=4, alpha=0.9)
                ax.text(post_years[len(post_years)//2], min(vals)*0.995,
                        f"trend: {slope*10:+.2f}°C/dec\nR²={r2:.2f}",
                        fontsize=7.5, color="#222", ha="center",
                        bbox=dict(fc="white", ec="#ccc", pad=2, alpha=0.85))

            # Jump annotation (raw panel only)
            if col_i == 0 and pre_vals and post_vals:
                pre_last  = np.mean(pre_vals[-3:])
                post_first= np.mean(post_vals[:3])
                jump      = post_first - pre_last
                mid       = (max(vals) + np.mean(vals)) / 2
                ax.annotate(
                    f"Jump: {jump:+.1f}°C",
                    xy=(BREAK, post_first),
                    xytext=(-55, 20),
                    textcoords="offset points",
                    fontsize=9, fontweight="bold", color=C_BREAK,
                    arrowprops=dict(arrowstyle="->", color=C_BREAK, lw=1.5),
                    bbox=dict(fc="#fff0f0", ec=C_BREAK, pad=3)
                )

            # Corrected panel: show residual
            if col_i == 1 and pre_vals and post_vals:
                pre_last  = np.mean(pre_vals[-3:])
                post_first= np.mean(post_vals[:3])
                residual  = post_first - pre_last
                ax.text(BREAK+0.3, np.mean(vals),
                        f"Residual: {residual:+.2f}°C",
                        fontsize=8, color="#1a7fc1", fontweight="bold",
                        bbox=dict(fc="#eaf4fb", ec="#1a7fc1", pad=3))

            if row_i == 0:
                ax.set_title(panel_label, fontsize=10, fontweight="bold",
                             color="#c0392b" if col_i==0 else "#1a5276", pad=10)

            ax.set_xlim(min(years)-0.5, max(years)+0.5)
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))

    plt.tight_layout(rect=[0,0,1,0.99])
    path = "/Users/mac/Desktop/gb_weather_dataset/clean_temperature.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print(f"  Saved → {path}")
    plt.close(fig)

# ── Plot 2: Precipitation ─────────────────────────────────────────────────────
def plot_precipitation():
    print("  Building precipitation plot...")
    raw  = annual_agg(RAW_FILE,  "precipitation_sum", "sum")
    corr = annual_agg(CORR_FILE, "precipitation_sum", "sum")

    fig, axes = plt.subplots(len(STATIONS), 2, figsize=(18, 4*len(STATIONS)),
                              facecolor=C_BG)
    fig.suptitle("Annual Precipitation — Raw ERA5  vs  Bias-Corrected\n"
                 "Annual totals + 3-year rolling smooth + linear trend lines (pre/post 2016)",
                 fontsize=14, fontweight="bold", y=1.005)

    for row_i, station in enumerate(STATIONS):
        elev = ELEVATIONS[station]
        col  = PALETTE[station]

        for col_i, (data, panel_label) in enumerate([
            (raw,  "RAW  (with ERA5 2016 jump)"),
            (corr, "CORRECTED  (jump removed)"),
        ]):
            ax = axes[row_i][col_i]
            style_ax(ax, ylabel=f"{station} ({elev}m)\nPrecip (mm/yr)" if col_i==0 else "")

            if station not in data:
                continue

            ydict = data[station]
            years = sorted(ydict)
            vals  = [ydict[y] for y in years]
            smooth= rolling3(years, vals)

            pre_years  = [y for y in years if y < BREAK]
            post_years = [y for y in years if y >= BREAK]
            pre_vals   = [ydict[y] for y in pre_years]
            post_vals  = [ydict[y] for y in post_years]

            ax.axvspan(min(years), BREAK,      color=C_PRE,  alpha=0.7, zorder=0)
            ax.axvspan(BREAK,      max(years), color=C_POST, alpha=0.7, zorder=0)
            ax.axvline(BREAK, color=C_BREAK, lw=1.8, linestyle="--", zorder=5)

            # Bar chart for annual totals
            bar_colors = [C_PRE.replace("ea","f9") if y < BREAK else C_POST.replace("ea","b8")
                          for y in years]
            ax.bar(years, vals, color=col, alpha=0.25, width=0.8, zorder=1)

            # 3-year smooth
            smooth_valid = [(y,v) for y,v in zip(years,smooth) if v is not None]
            if smooth_valid:
                sy, sv = zip(*smooth_valid)
                ax.plot(sy, sv, color=col, lw=2.5, alpha=0.9, zorder=3)

            # Trend lines
            tr_pre = fit_trend(pre_years, pre_vals)
            if tr_pre:
                yf, vf, slope, _, r2 = tr_pre
                ax.plot(yf, vf, color="#555", lw=2, zorder=4)
                ax.text(np.mean(pre_years), max(vals)*0.97,
                        f"{slope*10:+.1f}mm/dec  R²={r2:.2f}",
                        fontsize=8, color="#333", ha="center",
                        bbox=dict(fc="white", ec="#ccc", pad=2, alpha=0.9))

            tr_post = fit_trend(post_years, post_vals)
            if tr_post:
                yf, vf, slope, _, r2 = tr_post
                ax.plot(yf, vf, color="#222", lw=2, zorder=4)
                ax.text(np.mean(post_years), max(vals)*0.97,
                        f"{slope*10:+.1f}mm/dec  R²={r2:.2f}",
                        fontsize=8, color="#222", ha="center",
                        bbox=dict(fc="white", ec="#ccc", pad=2, alpha=0.9))

            # Jump annotation
            if col_i == 0 and pre_vals and post_vals:
                pre_mean  = np.mean(pre_vals[-5:])
                post_mean = np.mean(post_vals[:5])
                jump      = post_mean - pre_mean
                pct       = jump / pre_mean * 100
                ax.annotate(
                    f"Jump: {jump:+.0f}mm ({pct:+.0f}%)",
                    xy=(BREAK, post_mean),
                    xytext=(-65, 25),
                    textcoords="offset points",
                    fontsize=9, fontweight="bold", color=C_BREAK,
                    arrowprops=dict(arrowstyle="->", color=C_BREAK, lw=1.5),
                    bbox=dict(fc="#fff0f0", ec=C_BREAK, pad=3)
                )

            if col_i == 1 and pre_vals and post_vals:
                pre_mean  = np.mean(pre_vals[-5:])
                post_mean = np.mean(post_vals[:5])
                residual  = post_mean - pre_mean
                ax.text(BREAK+0.3, np.mean(vals)*1.05,
                        f"Residual: {residual:+.1f}mm",
                        fontsize=8, color="#1a7fc1", fontweight="bold",
                        bbox=dict(fc="#eaf4fb", ec="#1a7fc1", pad=3))

            if row_i == 0:
                ax.set_title(panel_label, fontsize=10, fontweight="bold",
                             color="#c0392b" if col_i==0 else "#1a5276", pad=10)

            ax.set_xlim(min(years)-0.5, max(years)+0.5)
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))

    plt.tight_layout(rect=[0,0,1,0.99])
    path = "/Users/mac/Desktop/gb_weather_dataset/clean_precipitation.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print(f"  Saved → {path}")
    plt.close(fig)

# ── Plot 3: Combined jump proof — all vars, all stations ─────────────────────
def plot_jump_proof():
    print("  Building jump proof panel...")

    vars_cfg = [
        ("temperature_2m_mean",  "mean", "Mean Temp (°C)",    "°C"),
        ("temperature_2m_max",   "mean", "Max Temp (°C)",     "°C"),
        ("precipitation_sum",    "sum",  "Precipitation (mm/yr)","mm"),
        ("snowfall_sum",         "sum",  "Snowfall (cm/yr)",  "cm"),
        ("wind_speed_10m_mean",  "mean", "Wind Mean (km/h)",  "km/h"),
        ("cloud_cover_mean",     "mean", "Cloud Cover (%)",   "%"),
    ]

    n_vars = len(vars_cfg)
    fig, axes = plt.subplots(n_vars, len(STATIONS),
                              figsize=(22, 3.5*n_vars), facecolor=C_BG)
    fig.suptitle(
        "ERA5 2016 Jump — All Variables  |  Annual Aggregated + 3-Year Smooth\n"
        "Orange = raw  |  Blue = corrected  |  Dashed red = 2016 break  |  Lines = trend",
        fontsize=13, fontweight="bold", y=1.005
    )

    for v_i, (var, agg, label, unit) in enumerate(vars_cfg):
        raw  = annual_agg(RAW_FILE,  var, agg)
        corr = annual_agg(CORR_FILE, var, agg)

        for s_i, station in enumerate(STATIONS):
            ax = axes[v_i][s_i]
            ax.set_facecolor(C_BG)
            ax.grid(True, color=C_GRID, lw=0.7, zorder=0)
            ax.spines[["top","right"]].set_visible(False)
            ax.spines[["left","bottom"]].set_color("#ccc")

            if station not in raw:
                ax.axis("off")
                continue

            # Raw
            ydict_r = raw[station]
            years_r = sorted(ydict_r)
            vals_r  = [ydict_r[y] for y in years_r]
            sm_r    = rolling3(years_r, vals_r)

            # Corrected
            ydict_c = corr.get(station, {})
            years_c = sorted(ydict_c)
            vals_c  = [ydict_c[y] for y in years_c]
            sm_c    = rolling3(years_c, vals_c)

            ax.axvspan(min(years_r), BREAK,      color=C_PRE,  alpha=0.5, zorder=0)
            ax.axvspan(BREAK,        max(years_r),color=C_POST, alpha=0.5, zorder=0)
            ax.axvline(BREAK, color=C_BREAK, lw=1.5, linestyle="--", zorder=5)

            # Raw smooth (orange)
            sv_r = [(y,v) for y,v in zip(years_r, sm_r) if v is not None]
            if sv_r:
                sy, sv = zip(*sv_r)
                ax.plot(sy, sv, color="#e67e22", lw=2, alpha=0.9, zorder=3, label="Raw")

            # Corrected smooth (blue)
            sv_c = [(y,v) for y,v in zip(years_c, sm_c) if v is not None]
            if sv_c:
                sy, sv = zip(*sv_c)
                ax.plot(sy, sv, color="#2980b9", lw=2, alpha=0.9, zorder=3,
                        linestyle="--", label="Corrected")

            # Trend lines — raw pre/post
            pre_r  = [(y,ydict_r[y]) for y in years_r if y <  BREAK]
            post_r = [(y,ydict_r[y]) for y in years_r if y >= BREAK]
            for seg, lc, ls in [(pre_r,"#c0392b","-"), (post_r,"#922b21","-")]:
                if len(seg) >= 3:
                    yy = [p[0] for p in seg]; vv = [p[1] for p in seg]
                    tr = fit_trend(yy, vv)
                    if tr:
                        ax.plot(tr[0], tr[1], color=lc, lw=1.3, ls=ls,
                                alpha=0.7, zorder=4)

            # Jump label
            pre_end  = [ydict_r[y] for y in years_r if BREAK-3 <= y < BREAK]
            post_beg = [ydict_r[y] for y in years_r if BREAK <= y < BREAK+3]
            if pre_end and post_beg:
                jump = np.mean(post_beg) - np.mean(pre_end)
                pct  = jump / abs(np.mean(pre_end)) * 100 if np.mean(pre_end) else 0
                ypos = np.percentile(vals_r, 85)
                ax.text(BREAK+0.3, ypos,
                        f"{jump:+.1f}{unit}\n({pct:+.0f}%)",
                        fontsize=7.5, color=C_BREAK, fontweight="bold",
                        va="top", bbox=dict(fc="#fff3f3", ec=C_BREAK,
                                             pad=2, alpha=0.9))

            # Axis labels
            if v_i == 0:
                ax.set_title(f"{station}\n({ELEVATIONS[station]}m)",
                             fontsize=9, fontweight="bold")
            if s_i == 0:
                ax.set_ylabel(label, fontsize=8)

            ax.set_xlim(min(years_r)-0.5, max(years_r)+0.5)
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(10))
            ax.tick_params(axis="both", labelsize=7.5)

    # Legend
    legend_handles = [
        Line2D([0],[0], color="#e67e22", lw=2, label="Raw (with jump)"),
        Line2D([0],[0], color="#2980b9", lw=2, ls="--", label="Bias-corrected"),
        Line2D([0],[0], color=C_BREAK,  lw=1.5, ls="--", label="2016 break"),
        mpatches.Patch(color=C_PRE,  alpha=0.5, label="Pre-2016"),
        mpatches.Patch(color=C_POST, alpha=0.5, label="Post-2016"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=5,
               fontsize=9, framealpha=0.9, bbox_to_anchor=(0.5,-0.01))

    plt.tight_layout(rect=[0,0,1,0.995])
    path = "/Users/mac/Desktop/gb_weather_dataset/clean_jump_proof.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print(f"  Saved → {path}")
    plt.close(fig)

# ── Plot 4: Decade summary bar chart ─────────────────────────────────────────
def plot_decade_bars():
    print("  Building decade summary bars...")

    temp_raw  = annual_agg(RAW_FILE,  "temperature_2m_mean", "mean")
    temp_corr = annual_agg(CORR_FILE, "temperature_2m_mean", "mean")
    prec_raw  = annual_agg(RAW_FILE,  "precipitation_sum",   "sum")
    prec_corr = annual_agg(CORR_FILE, "precipitation_sum",   "sum")

    decades = {"1990s":(1990,1999),"2000s":(2000,2009),
               "2010s":(2010,2015),"2016+":(2016,2024)}

    fig, axes = plt.subplots(2, len(STATIONS), figsize=(20, 9), facecolor=C_BG)
    fig.suptitle(
        "Decadal Mean Comparison — Raw vs Corrected\n"
        "Reveals how the ERA5 jump inflates post-2016 statistics in raw data",
        fontsize=13, fontweight="bold", y=1.01
    )

    for s_i, station in enumerate(STATIONS):
        elev = ELEVATIONS[station]

        for v_i, (raw_d, corr_d, ylabel) in enumerate([
            (temp_raw, temp_corr, "Mean Temp (°C)"),
            (prec_raw, prec_corr, "Annual Precip (mm)"),
        ]):
            ax = axes[v_i][s_i]
            style_ax(ax, xlabel=False)

            raw_means  = []
            corr_means = []
            dec_labels = []

            for dec, (y0, y1) in decades.items():
                rv = [raw_d[station][y]  for y in range(y0,y1+1)
                      if station in raw_d  and y in raw_d[station]]
                cv = [corr_d[station][y] for y in range(y0,y1+1)
                      if station in corr_d and y in corr_d[station]]
                if rv and cv:
                    raw_means.append(np.mean(rv))
                    corr_means.append(np.mean(cv))
                    dec_labels.append(dec)

            if not dec_labels:
                continue

            x   = np.arange(len(dec_labels))
            w   = 0.35
            br  = ax.bar(x - w/2, raw_means,  w, label="Raw",       color="#e67e22", alpha=0.85)
            bc  = ax.bar(x + w/2, corr_means, w, label="Corrected", color="#2980b9", alpha=0.85)

            # Value labels on bars
            for bar in list(br) + list(bc):
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, h + abs(h)*0.005,
                        f"{h:.1f}", ha="center", va="bottom", fontsize=7.5)

            # Highlight 2016+ bar pair — show the difference
            idx_2016 = dec_labels.index("2016+") if "2016+" in dec_labels else None
            if idx_2016 is not None:
                diff = raw_means[idx_2016] - corr_means[idx_2016]
                ax.annotate(
                    f"Raw inflated\nby {diff:+.1f}",
                    xy=(idx_2016, max(raw_means[idx_2016], corr_means[idx_2016])),
                    xytext=(0, 15), textcoords="offset points",
                    ha="center", fontsize=8, color=C_BREAK, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=C_BREAK),
                    bbox=dict(fc="#fff3f3", ec=C_BREAK, pad=2)
                )

            ax.set_xticks(x)
            ax.set_xticklabels(dec_labels, fontsize=9)
            if s_i == 0:
                ax.set_ylabel(ylabel, fontsize=9)
            if v_i == 0:
                ax.set_title(f"{station}\n({elev}m)", fontsize=9, fontweight="bold")
            if s_i == len(STATIONS)-1 and v_i == 0:
                ax.legend(fontsize=8, loc="upper right")

    plt.tight_layout(rect=[0,0,1,0.995])
    path = "/Users/mac/Desktop/gb_weather_dataset/clean_decades.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=C_BG)
    print(f"  Saved → {path}")
    plt.close(fig)

# ── Main ──────────────────────────────────────────────────────────────────────
import matplotlib.ticker

def main():
    print("=" * 60)
    print("  GB Weather — Clean Visualizations")
    print("  Noise reduction: annual agg → 3-year rolling")
    print("=" * 60)
    plot_temperature()
    plot_precipitation()
    plot_jump_proof()
    plot_decade_bars()
    print("\nAll plots saved to Desktop/gb_weather_dataset/")
    print("  clean_temperature.png")
    print("  clean_precipitation.png")
    print("  clean_jump_proof.png")
    print("  clean_decades.png")

if __name__ == "__main__":
    main()
