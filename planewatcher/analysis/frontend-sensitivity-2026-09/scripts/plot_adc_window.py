#!/usr/bin/env python3
"""Plot one raw ADC window at a chosen Pluto gain beside a source-off window.

Picks the window with the longest PPM data run, aligns the bit clock the same
way as adc_bit_margin.py, and marks the decided bit for each 1 us period.

  uv run --project ~/plane_watcher/tools --no-sync python plot_adc_window.py --gain -61
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).parent  # expects raw captures in HERE / "adc" (not committed)
sys.path.insert(0, str(Path(__file__).parent))  # adc_bit_margin.py alongside
from adc_bit_margin import SPB, windows  # noqa: E402

INK, MUTED, GRID, SURFACE = "#1f2328", "#6e7781", "#d8dee4", "#ffffff"
TRACE = "#2f6fdb"  # single series: first categorical slot of the reference palette


def best_run(w: np.ndarray):
    """Return (start, stop, phase) of the longest data run in a window."""
    med = np.median(w)
    h = np.percentile(w, 97) - med
    sm = np.convolve(w - med, np.ones(2 * SPB) / (2 * SPB), "same")
    act = sm > h / 8
    edges = np.flatnonzero(np.diff(np.r_[0, act.astype(int), 0]))
    runs = [(a + SPB, b - SPB) for a, b in zip(edges[::2], edges[1::2]) if b - a > 14 * SPB]
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    scores = []
    for ph in range(SPB):
        n = (b - a - ph) // SPB
        seg = w[a + ph : a + ph + n * SPB].reshape(n, SPB)
        scores.append(np.abs(seg[:, :16].mean(1) - seg[:, 16:].mean(1)).sum())
    return a, b, int(np.argmax(scores))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain", type=int, default=-61)
    ap.add_argument("--span-us", type=float, default=40.0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    cap = HERE / "adc"
    sig = windows(cap / f"df17{args.gain}.pwcap")
    off = windows(cap / "source-off.pwcap")
    picks = [(i, best_run(w)) for i, w in enumerate(sig)]
    i, (a, b, ph) = max(((i, r) for i, r in picks if r), key=lambda t: t[1][1] - t[1][0])
    w = sig[i]
    n_span = int(args.span_us * 32)
    s0 = max(0, a + ph - 4 * SPB)
    t = (np.arange(n_span)) / 32.0  # us at 32 MS/s
    base = np.median(w)

    fig, axes = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True, sharey=True,
                             gridspec_kw={"height_ratios": [1.25, 1]}, facecolor=SURFACE)
    ax = axes[0]
    ax.plot(t, w[s0 : s0 + n_span] - base, color=TRACE, lw=1.2)
    # Bit decisions: first half vs second half of each 1 us period.
    k0 = a + ph
    for k in range(k0, min(b, s0 + n_span) - SPB + 1, SPB):
        seg = w[k : k + SPB]
        bit = 1 if seg[:16].mean() > seg[16:].mean() else 0
        x = (k - s0) / 32.0
        ax.axvline(x, color=GRID, lw=0.8, zorder=0)
        ax.text(x + 0.5, 1.02, str(bit), transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=8, color=MUTED)
    ax.set_title(f"Pluto gain {args.gain} dB: PlaneWatcher decodes 0.4%, Beast 93.5% "
                 f"— raw ADC window {i}, baseline removed", loc="left", fontsize=10, color=INK, pad=16)
    ax.set_ylabel("ADC codes", color=MUTED)
    axes[1].plot(t, off[0][:n_span] - np.median(off[0]), color=MUTED, lw=1.0)
    axes[1].set_title("Source off (noise only), same scale", loc="left", fontsize=10, color=INK)
    axes[1].set_ylabel("ADC codes", color=MUTED)
    axes[1].set_xlabel("time (µs); grid = 1 µs bit periods, digits = decided bit", color=MUTED)
    for a_ in axes:
        a_.set_facecolor(SURFACE)
        a_.grid(axis="y", color=GRID, lw=0.6)
        for side in ("top", "right"):
            a_.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            a_.spines[side].set_color(GRID)
        a_.tick_params(colors=MUTED, labelsize=8)
    fig.tight_layout()
    out = args.out or HERE / f"adc-window{args.gain}.png"
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
