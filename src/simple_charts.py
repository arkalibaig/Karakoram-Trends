#!/usr/bin/env python3
"""
Simple, plain-English charts for GB weather data.
Anyone can understand these — no technical background needed.
"""

import csv, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict

RAW_FILE  = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_combined.csv"
CORR_FILE = "/Users/mac/Desktop/gb_weather_dataset/gb_weather_corrected.csv"

STATIONS  = ["Gilgit", "Skardu", "Hunza", "Chilas", "Khunjerab"]
ELEV      = {"Gilgit":1500, "Skardu":2228, "Hunza":2438, "Chilas":1250, "Khunjerab":4693}
PALETTE   = {"Gilgit":"#e74c3c","Skardu":"#3498db","Hunza":"#27ae60",
             "Chilas":"#f39c12","Khunjerab":"#8e44ad"}

def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except: return None

def load_annual(filepath, var, agg="mean"):
    b = defaultdict(lambda: defaultdict(list))
    with open(filepath, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try: yr = int(row["date"][:4])
            except: continue
            v = safe_float(row.get(var))
            if v is not None:
                b[row["station"]][yr].append(v)
    return {s: {y: (sum(vs)/len(vs) if agg=="mean" else sum(vs))
                for y,vs in ys.items()} for s,ys in b.items()}

def smooth3(years, vals):
    out = []
    for i in range(len(vals)):
        w = [vals[j] for j in range(max(0,i-1), min(len(vals),i+2)) if vals[j] is not None]
        out.append(sum(w)/len(w) if w else None)
    return out

def decade_mean(ydict, y0, y1):
    vs = [ydict[y] for y in range(y0, y1+1) if y in ydict]
    return round(sum(vs)/len(vs), 2) if vs else None

# ═══════════════════════════════════════════════════════════════════════════════
# CHART 1 — "The Problem Explained"
# Simple side-by-side: broken data vs fixed data for ONE station (Gilgit)
# ═══════════════════════════════════════════════════════════════════════════════
def chart1_the_problem():
    raw  = load_annual(RAW_FILE,  "temperature_2m_mean")
    corr = load_annual(CORR_FILE, "temperature_2m_mean")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), facecolor="#fafafa")
    fig.suptitle("Gilgit Temperature  —  The Data Problem & The Fix",
                 fontsize=18, fontweight="bold", y=1.02)

    for ax, data, title, color, is_raw in [
        (ax1, raw,  "❌  BROKEN  (before fix)\nThe data has a fake jump in 2016",
         "#e74c3c", True),
        (ax2, corr, "✅  FIXED  (after correction)\nThe data now tells the true story",
         "#27ae60", False),
    ]:
        ax.set_facecolor("white")
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color("#ccc")
        ax.grid(axis="y", color="#eeeeee", lw=1)

        ydict = data.get("Gilgit", {})
        years = sorted(ydict)
        vals  = [ydict[y] for y in years]
        sm    = smooth3(years, vals)

        # Colour bars by era
        bar_colors = ["#ffcdd2" if y < 2016 else "#bbdefb" for y in years]
        ax.bar(years, vals, color=bar_colors, width=0.8, zorder=1, alpha=0.7)

        # Smooth line
        sv = [(y,v) for y,v in zip(years,sm) if v is not None]
        sy, sv2 = zip(*sv)
        ax.plot(sy, sv2, color=color, lw=3, zorder=3)

        # 2016 line
        ax.axvline(2016, color="#333", lw=2, linestyle="--", zorder=4)

        ax.set_title(title, fontsize=13, fontweight="bold",
                     color="#c0392b" if is_raw else "#1a7a45", pad=14, loc="left")
        ax.set_xlabel("Year", fontsize=11)
        ax.set_ylabel("Average Temperature (°C)", fontsize=11)
        ax.tick_params(labelsize=10)
        ax.set_xlim(1989, 2025)

        # Decade average lines
        decade_means = [
            ("1990s", 1990, 1999, "#999"),
            ("2000s", 2000, 2009, "#999"),
            ("2010s", 2010, 2015, "#999"),
            ("2016+", 2016, 2024, "#555"),
        ]
        for label, y0, y1, lc in decade_means:
            dm = decade_mean(ydict, y0, y1)
            if dm:
                ax.hlines(dm, y0, y1, colors=lc, lw=2.5, linestyles="-", zorder=5)
                ax.text((y0+y1)/2, dm+0.12, f"{dm:.1f}°C",
                        ha="center", fontsize=9, color=lc, fontweight="bold")

        # Annotations
        if is_raw:
            pre_avg  = decade_mean(ydict, 2013, 2015)
            post_avg = decade_mean(ydict, 2016, 2018)
            if pre_avg and post_avg:
                jump = post_avg - pre_avg
                ax.annotate(
                    f"Sudden jump of\n+{jump:.1f}°C in one year\n(not real warming!)",
                    xy=(2016, post_avg), xytext=(2005, post_avg + 1.5),
                    fontsize=11, color="#c0392b", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=2),
                    bbox=dict(fc="#fff0f0", ec="#c0392b", pad=6, boxstyle="round")
                )
        else:
            ax.text(1992, min(vals)+0.3,
                    "Smooth, continuous\ntemperature record\nno fake jumps",
                    fontsize=11, color="#1a7a45", fontweight="bold",
                    bbox=dict(fc="#f0fff4", ec="#27ae60", pad=6, boxstyle="round"))

        # Legend
        ax.legend(handles=[
            mpatches.Patch(color="#ffcdd2", alpha=0.7, label="Before 2016"),
            mpatches.Patch(color="#bbdefb", alpha=0.7, label="2016 onwards"),
            plt.Line2D([0],[0], color=color, lw=3, label="3-year average"),
        ], fontsize=9, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    path = "/Users/mac/Desktop/gb_weather_dataset/chart1_problem.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fafafa")
    print(f"  Saved → {path}")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CHART 2 — "How Much Did Each Station Actually Warm?"
# Simple decade-by-decade temperature for all 5 stations
# ═══════════════════════════════════════════════════════════════════════════════
def chart2_warming_by_decade():
    corr = load_annual(CORR_FILE, "temperature_2m_mean")

    DECADES = [("1990s", 1990,1999), ("2000s", 2000,2009),
               ("2010s", 2010,2015), ("2016+", 2016,2024)]
    DEC_COLORS = ["#aed6f1","#5dade2","#2874a6","#1a5276"]

    fig, axes = plt.subplots(1, len(STATIONS), figsize=(20, 7), facecolor="#fafafa")
    fig.suptitle("How Has Temperature Changed Each Decade?\n"
                 "(Using corrected, accurate data — higher bar = warmer)",
                 fontsize=16, fontweight="bold", y=1.03)

    for i, station in enumerate(STATIONS):
        ax = axes[i]
        ax.set_facecolor("white")
        ax.spines[["top","right","bottom"]].set_visible(False)
        ax.spines["left"].set_color("#ccc")
        ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)

        ydict = corr.get(station, {})
        means = [decade_mean(ydict, y0, y1) for _, y0, y1 in DECADES]
        labels= [d[0] for d in DECADES]

        bars = ax.bar(labels, means, color=DEC_COLORS, width=0.6,
                      zorder=2, edgecolor="white", linewidth=1.5)

        # Value labels
        for bar, val in zip(bars, means):
            if val is not None:
                ax.text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + 0.1,
                        f"{val:.1f}°C",
                        ha="center", va="bottom",
                        fontsize=11, fontweight="bold", color="#333")

        # Change arrow from 1990s to 2016+
        if means[0] and means[3]:
            change = means[3] - means[0]
            ax.annotate(
                f"+{change:.1f}°C\nsince 1990s",
                xy=(3, means[3]), xytext=(2.5, means[3] + 0.8),
                fontsize=9, color="#c0392b", fontweight="bold",
                ha="center",
                arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.5),
                bbox=dict(fc="#fff0f0", ec="#c0392b", pad=4, boxstyle="round")
            )

        ax.set_title(f"{station}\n({ELEV[station]}m elevation)",
                     fontsize=11, fontweight="bold", pad=10)
        ax.set_ylabel("Avg Temperature (°C)" if i == 0 else "", fontsize=10)
        ax.tick_params(labelsize=10)
        ymin = min(v for v in means if v) - 1.5
        ymax = max(v for v in means if v) + 2.5
        ax.set_ylim(ymin, ymax)

    # Colour legend
    fig.legend(handles=[mpatches.Patch(color=c, label=l)
                        for (l,_,_), c in zip(DECADES, DEC_COLORS)],
               loc="lower center", ncol=4, fontsize=11,
               bbox_to_anchor=(0.5, -0.06), framealpha=0.9)

    plt.tight_layout()
    path = "/Users/mac/Desktop/gb_weather_dataset/chart2_decades.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fafafa")
    print(f"  Saved → {path}")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CHART 3 — "Fake vs Real: What the Model Was Told vs Truth"
# One clear bar for each station showing raw slope vs corrected slope
# ═══════════════════════════════════════════════════════════════════════════════
def chart3_fake_vs_real():
    raw_data  = load_annual(RAW_FILE,  "temperature_2m_mean")
    corr_data = load_annual(CORR_FILE, "temperature_2m_mean")

    def get_slope(ydict):
        years = sorted(ydict)
        vals  = [ydict[y] for y in years]
        sm    = smooth3(years, vals)
        pairs = [(y,v) for y,v in zip(years,sm) if v is not None]
        if len(pairs) < 3: return None
        y_arr = np.array([p[0] for p in pairs])
        v_arr = np.array([p[1] for p in pairs])
        return np.polyfit(y_arr, v_arr, 1)[0] * 10

    fig, ax = plt.subplots(figsize=(14, 7), facecolor="#fafafa")
    ax.set_facecolor("white")
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#ccc")
    ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)

    x       = np.arange(len(STATIONS))
    w       = 0.35
    raw_sl  = [get_slope(raw_data.get(s,{}))  for s in STATIONS]
    corr_sl = [get_slope(corr_data.get(s,{})) for s in STATIONS]

    br = ax.bar(x - w/2, raw_sl,  w, color="#e74c3c", alpha=0.85,
                label="❌  What the model was told\n    (broken data)",
                zorder=2, edgecolor="white", linewidth=1.5)
    bc = ax.bar(x + w/2, corr_sl, w, color="#27ae60", alpha=0.85,
                label="✅  Real warming\n    (corrected data)",
                zorder=2, edgecolor="white", linewidth=1.5)

    # Value labels
    for bar, val in zip(list(br)+list(bc), raw_sl+corr_sl):
        if val is not None:
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.03,
                    f"{val:+.2f}°C",
                    ha="center", va="bottom",
                    fontsize=10, fontweight="bold",
                    color="#c0392b" if bar in br else "#1a7a45")

    # Inflation labels
    for i, (rs, cs) in enumerate(zip(raw_sl, corr_sl)):
        if rs and cs:
            fake = rs - cs
            ax.text(i, max(rs, cs) + 0.25,
                    f"Fake: +{fake:.2f}°C",
                    ha="center", fontsize=9, color="#888",
                    style="italic")

    ax.axhline(0, color="#333", lw=1, linestyle="-")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s}\n({ELEV[s]}m)" for s in STATIONS], fontsize=11)
    ax.set_ylabel("Warming per Decade (°C)", fontsize=12)
    ax.set_title("What Was the Model Told vs What Is Actually Happening?\n"
                 "Temperature change per decade — all data 1990 to 2024",
                 fontsize=14, fontweight="bold", pad=12)
    ax.legend(fontsize=11, loc="upper right", framealpha=0.95)
    ax.tick_params(labelsize=10)

    # Callout box
    avg_real = sum(v for v in corr_sl if v) / len([v for v in corr_sl if v])
    avg_fake = sum(v for v in raw_sl  if v) / len([v for v in raw_sl  if v])
    ax.text(0.01, 0.97,
            f"GB average warming:\n"
            f"  Broken data told model:  {avg_fake:+.2f}°C per decade\n"
            f"  Real corrected answer:   {avg_real:+.2f}°C per decade\n"
            f"  The data was {avg_fake/avg_real:.0f}× too high",
            transform=ax.transAxes, fontsize=11,
            va="top", ha="left",
            bbox=dict(fc="#fffde7", ec="#f39c12", pad=10, boxstyle="round"))

    plt.tight_layout()
    path = "/Users/mac/Desktop/gb_weather_dataset/chart3_fake_vs_real.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fafafa")
    print(f"  Saved → {path}")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CHART 4 — "35 Years of Weather in GB" — simple summary timeline
# All 5 stations on one clean chart, corrected data only
# ═══════════════════════════════════════════════════════════════════════════════
def chart4_timeline():
    corr = load_annual(CORR_FILE, "temperature_2m_mean")

    fig, ax = plt.subplots(figsize=(16, 7), facecolor="#fafafa")
    ax.set_facecolor("white")
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#ccc")
    ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)

    for station in STATIONS:
        ydict = corr.get(station, {})
        years = sorted(ydict)
        vals  = [ydict[y] for y in years]
        sm    = smooth3(years, vals)
        sv    = [(y,v) for y,v in zip(years,sm) if v is not None]
        if not sv: continue
        sy, sv2 = zip(*sv)

        col = PALETTE[station]
        ax.plot(sy, sv2, color=col, lw=2.5, zorder=3, alpha=0.9)
        ax.scatter(years, vals, color=col, s=8, alpha=0.2, zorder=2)

        # End label
        ax.text(sy[-1]+0.3, sv2[-1], f" {station}\n ({ELEV[station]}m)",
                fontsize=9.5, color=col, fontweight="bold", va="center")

    # Decade shading
    for y0, y1, label, col in [(1990,1999,"1990s","#f5f5f5"),
                                (2000,2009,"2000s","#eeeeee"),
                                (2010,2015,"2010–15","#f5f5f5"),
                                (2016,2024,"2016+","#e8f4fd")]:
        ax.axvspan(y0, y1+0.9, color=col, alpha=0.5, zorder=0)
        ax.text((y0+y1)/2+0.45, ax.get_ylim()[0] if ax.get_ylim()[0] > -20 else -15.5,
                label, ha="center", fontsize=9, color="#aaa", style="italic")

    ax.axvline(2016, color="#c0392b", lw=1.5, linestyle="--", alpha=0.5, zorder=1)
    ax.text(2016.2, 19, "Data corrected\nfrom here →",
            fontsize=9, color="#c0392b", style="italic")

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Average Temperature (°C)", fontsize=12)
    ax.set_title("35 Years of Temperature in Gilgit-Baltistan  (1990 – 2024)\n"
                 "Corrected accurate data  |  Each line = one weather station",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_xlim(1989, 2027)
    ax.tick_params(labelsize=10)

    # Simple note
    ax.text(0.01, 0.04,
            "Higher line = warmer location  |  Lower line = colder (higher altitude)\n"
            "Khunjerab sits at 4,693m — always coldest.  Chilas at 1,250m — always warmest.",
            transform=ax.transAxes, fontsize=9, color="#666",
            bbox=dict(fc="white", ec="#ddd", pad=6, boxstyle="round"))

    plt.tight_layout()
    path = "/Users/mac/Desktop/gb_weather_dataset/chart4_timeline.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fafafa")
    print(f"  Saved → {path}")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CHART 5 — Rain & Snow by decade
# ═══════════════════════════════════════════════════════════════════════════════
def chart5_rain_snow():
    rain = load_annual(CORR_FILE, "rain_sum",     "sum")
    snow = load_annual(CORR_FILE, "snowfall_sum", "sum")

    DECADES_LABELS = ["1990s","2000s","2010–15","2016+"]
    DECADES_RANGES = [(1990,1999),(2000,2009),(2010,2015),(2016,2024)]

    fig, axes = plt.subplots(2, len(STATIONS), figsize=(20, 10), facecolor="#fafafa")
    fig.suptitle("Has Rain and Snow Changed Over the Decades?\n"
                 "(Corrected accurate data  |  Taller bar = more rain or snow)",
                 fontsize=16, fontweight="bold", y=1.02)

    RAIN_COLS = ["#aed6f1","#5dade2","#2874a6","#1a5276"]
    SNOW_COLS = ["#d5e8d4","#82b366","#4a7c4e","#2d5a27"]

    for col_i, station in enumerate(STATIONS):
        for row_i, (data, ylabel, colors, unit) in enumerate([
            (rain, "Annual Rainfall (mm)", RAIN_COLS, "mm"),
            (snow, "Annual Snowfall (cm)", SNOW_COLS, "cm"),
        ]):
            ax = axes[row_i][col_i]
            ax.set_facecolor("white")
            ax.spines[["top","right","bottom"]].set_visible(False)
            ax.spines["left"].set_color("#ccc")
            ax.grid(axis="y", color="#eeeeee", lw=1, zorder=0)

            ydict = data.get(station, {})
            means = [decade_mean(ydict, y0, y1) for y0,y1 in DECADES_RANGES]

            if not any(means):
                ax.text(0.5,0.5,"No data",ha="center",va="center",
                        transform=ax.transAxes, color="#aaa")
                continue

            bars = ax.bar(DECADES_LABELS, means, color=colors,
                          width=0.6, zorder=2, edgecolor="white", lw=1.5)

            for bar, val in zip(bars, means):
                if val is not None:
                    ax.text(bar.get_x()+bar.get_width()/2,
                            bar.get_height()+max(means)*0.02,
                            f"{val:.1f}{unit}",
                            ha="center", va="bottom",
                            fontsize=9, fontweight="bold", color="#333")

            # Change annotation
            valid = [(l,v) for l,v in zip(DECADES_LABELS, means) if v]
            if len(valid) >= 2:
                first_v, last_v = valid[0][1], valid[-1][1]
                change = last_v - first_v
                pct    = change / first_v * 100 if first_v else 0
                symbol = "▲" if change > 0 else "▼"
                col_txt= "#c0392b" if change > 0 else "#1a7a45"
                ax.text(0.97, 0.95,
                        f"{symbol} {abs(pct):.0f}%\nsince 1990s",
                        transform=ax.transAxes, ha="right", va="top",
                        fontsize=10, fontweight="bold", color=col_txt,
                        bbox=dict(fc="white", ec=col_txt, pad=4, boxstyle="round"))

            if row_i == 0:
                ax.set_title(f"{station}\n({ELEV[station]}m)",
                             fontsize=11, fontweight="bold", pad=8)
            if col_i == 0:
                ax.set_ylabel(ylabel, fontsize=10)
            ax.tick_params(labelsize=9)

    plt.tight_layout()
    path = "/Users/mac/Desktop/gb_weather_dataset/chart5_rain_snow.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fafafa")
    print(f"  Saved → {path}")
    plt.close()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Generating simple charts...")
    chart1_the_problem()
    chart2_warming_by_decade()
    chart3_fake_vs_real()
    chart4_timeline()
    chart5_rain_snow()
    print("\nDone. All 5 charts saved:")
    print("  chart1_problem.png    — What the data problem looked like & the fix")
    print("  chart2_decades.png    — Temperature each decade, all stations")
    print("  chart3_fake_vs_real.png — What the model was told vs the truth")
    print("  chart4_timeline.png   — 35-year overview, all stations")
    print("  chart5_rain_snow.png  — Rain & snow change by decade")

if __name__ == "__main__":
    main()
