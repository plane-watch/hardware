#!/usr/bin/env python3
"""Regenerate this report's summary plots from the committed data only.

  uv run --with matplotlib python scripts/make_plots.py

Coverage data holds bearing, max range and altitude only (no site or aircraft
coordinates). Two PlaneWatcher bins on 26 Sep (264 and 285 deg, 603 and 566
km) lie beyond the radio horizon for their altitudes; they are bad position
decodes and are drawn at their smaller neighbour's range, marked in the title.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA, PLOTS = HERE / "data", HERE / "plots"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#dcdad4", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
BOGUS = (264, 285)


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ax.spines.values():
        side.set_color(GRID)


def knee() -> None:
    def load(path, gain_key="tx-gain-db", pct="decode %"):
        rows = list(csv.DictReader(open(path)))[:-1]  # last row is the -45 dB control
        return [float(r[gain_key]) for r in rows], [float(r[pct]) for r in rows]

    series = [
        ("Mode-S Beast", load(DATA / "sweeps/beast-sweep.csv"), BLUE),
        ("PlaneWatcher, threshold 2000 (old)", load(DATA / "sweeps/pw-sweep.csv"), ORANGE),
    ]
    rows = json.load(open(DATA / "sweeps/threshold/power_threshold-700.json"))[1:]
    series.append(("PlaneWatcher, threshold 700 (new)",
                   ([r["tx-gain-db"] for r in rows],
                    [100 * r["_counters"]["df17_ct"] / r["frames_sent"] for r in rows]), AQUA))
    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=SURFACE)
    for label, (x, y), colour in series:
        ax.plot(x, [min(v, 100) for v in y], color=colour, lw=2, marker="o", ms=4, label=label)
    ax.axhline(50, color=GRID, lw=1, zorder=0)
    ax.set_xlim(-65.5, -56.5)
    ax.set_xlabel("Pluto TX gain (dB, same attenuator and cable for all receivers)", color=MUTED)
    ax.set_ylabel("DF17 frames decoded (%)", color=MUTED)
    ax.set_title("Conducted decode knee, same stimulus: 700 closes most of the gap to the Beast",
                 loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    style(ax)
    fig.tight_layout()
    fig.savefig(PLOTS / "decode-knee.png", dpi=130)


def ranges(name: str, mask: bool = False) -> np.ndarray:
    bins = json.load(open(DATA / "coverage" / name))["bins"]
    r = np.array([b["max_range_km"] for b in sorted(bins, key=lambda b: b["bearing_deg"])])
    if mask:
        for d in BOGUS:
            r[d] = min(r[(d - 1) % 360], r[(d + 1) % 360])
    return r


def polar(pairs, title: str, out: str) -> None:
    theta = np.deg2rad(np.arange(361))
    fig = plt.figure(figsize=(7.5, 7.8), facecolor=SURFACE)
    ax = fig.add_subplot(projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    for label, r, colour in pairs:
        rr = np.append(r, r[0])
        ax.plot(theta, rr, color=colour, lw=1.6, label=label)
        ax.fill(theta, rr, color=colour, alpha=0.08)
    ax.set_rlabel_position(160)
    ax.set_ylim(0, 400)
    ax.set_yticks([100, 200, 300, 400])
    ax.set_yticklabels(["100 km", "200 km", "300 km", "400 km"], color=MUTED, fontsize=8)
    ax.grid(color=GRID, lw=0.6)
    style(ax)
    ax.set_title(title, loc="left", fontsize=10, color=INK, pad=18)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper center",
              bbox_to_anchor=(0.5, -0.05), ncol=1)
    fig.tight_layout()
    fig.savefig(PLOTS / out, dpi=130)


def main() -> None:
    PLOTS.mkdir(exist_ok=True)
    knee()
    new = ranges("planewatcher-20260926T1437Z.json", mask=True)
    polar([("Old settings: all-time map to 23 Sep", ranges("planewatcher-20260923T1447Z-old-settings-alltime.json"), ORANGE),
           ("New settings: 24-26 Sep", new, BLUE)],
          "Max range per bearing, same site (26 Sep spikes at 264/285 deg masked)", "coverage-old-vs-new.png")
    polar([("Radarcape, June 2026 (282 h, same site and antenna)", ranges("radarcape-june2026.json"), ORANGE),
           ("PlaneWatcher, new settings, 24-26 Sep", new, BLUE)],
          "PlaneWatcher vs Radarcape (26 Sep spikes at 264/285 deg masked)", "coverage-vs-radarcape.png")
    print("plots written to", PLOTS)


if __name__ == "__main__":
    main()
