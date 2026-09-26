#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "scipy>=1.11"]
# ///
"""Estimate how much of the receiver noise floor comes from the ADL5513 itself.

Offline only: reads saved R51 pad 2 scope waveforms, never touches instruments.

Observables (all at R51 pad 2, converted to dB with the measured log slope):
  * terminated-input baseline mean and fluctuation (6 Sep, stock board);
  * CW means and fluctuations at Pluto gain -50/-40/-30 dB (13 Sep).

Model: the detector output is an ideal log of the instantaneous envelope of
  CW + chain noise (band-limited by the SAW pair, noise bandwidth Bn)
     + detector-intrinsic noise (white over a wide bandwidth Bw),
followed by a single-pole video filter.  Narrowband chain noise produces
large, slow envelope fluctuations that pass the ~10 MHz video filter; wideband
intrinsic noise is mostly averaged away.  The measured fluctuation size
therefore constrains the chain/intrinsic power ratio independently of any
absolute RF level calibration.

Usage:
  uv run scripts/noise_floor_analysis.py \
      --output /path/to/result.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

ART = Path.home() / ("plane_watcher/artifacts/tools/frontend")
BASELINE = (
    ART
    / "20260906T144013396213Z_stock-terminated-microscope-lights-off"
    / "20260906_224014_microscope-lights-off.waveforms.npz"
)
CW = {
    -50: ART / "20260913T050705Z_r51_cw_gain_minus50" / "waveform.npz",
    -40: ART / "20260913T050739Z_r51_cw_level_check" / "gain_-40.npz",
    -30: ART / "20260913T050739Z_r51_cw_level_check" / "gain_-30.npz",
}
# Receiver-plane CW levels from CW_EVIDENCE_AUDIT_20260919.md (pre-level-cal tinySA).
CW_SMA_DBM = {-50: -86.9375, -40: -76.9375, -30: -66.9375}
SCOPE_NOISE_V = 0.001090753878296832  # grounded-probe RMS, same scope settings
DETECTOR_INTERCEPT_DBM = -88.0  # ADL5513 typical, 900 MHz
DETECTOR_FLOOR_DBM = -70.0  # ADL5513 "sensitivity"/noise floor, typical


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_measurements() -> dict:
    base = np.load(BASELINE)["C1_y"]
    cw = {g: np.load(p)["y"] for g, p in CW.items()}
    gains = sorted(cw)
    p = np.array([CW_SMA_DBM[g] for g in gains])
    v = np.array([cw[g].mean() for g in gains])
    slope, icpt = np.polyfit(p, v, 1)  # V per dBm at SMA plane

    def std_db(y: np.ndarray) -> float:
        s = math.sqrt(max(y.var() - SCOPE_NOISE_V**2, 0.0))
        return s / slope

    floor_cw_eq = (base.mean() - icpt) / slope
    return {
        "slope_mv_per_db": slope * 1e3,
        "sma_intercept_dbm": -icpt / slope,
        "implied_gain_db": DETECTOR_INTERCEPT_DBM - (-icpt / slope),
        "baseline_mean_v": float(base.mean()),
        "baseline_std_db": std_db(base),
        "floor_cw_equivalent_sma_dbm": float(floor_cw_eq),
        "cw": {
            str(g): {
                "sma_dbm": CW_SMA_DBM[g],
                "mean_v": float(cw[g].mean()),
                "above_floor_db": float((cw[g].mean() - base.mean()) / slope),
                "std_db": std_db(cw[g]),
            }
            for g in gains
        },
        "inputs": {str(k): sha256(p) for k, p in {"baseline": BASELINE, **CW}.items()},
    }


class Detector:
    """Complex-baseband Monte Carlo of the log detector and video filter."""

    def __init__(self, bn_hz, bw_hz, video_hz, fs=4e9, n=2**19, seed=1):
        rng = np.random.default_rng(seed)
        f = np.fft.fftfreq(n, 1 / fs)

        def white():
            return (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / math.sqrt(2)

        # Chain noise: 4th-order Butterworth magnitude, scaled to noise bandwidth bn_hz.
        h = 1 / np.sqrt(1 + (2 * f / bn_hz) ** 8)
        h /= math.sqrt(np.sum(h**2) * fs / n / bn_hz)  # noise bandwidth -> bn_hz
        chain = np.fft.ifft(np.fft.fft(white()) * h)
        det = np.fft.ifft(np.fft.fft(white()) * (np.abs(f) < bw_hz / 2))
        self.chain = chain / np.sqrt(np.mean(abs(chain) ** 2))  # unit power
        self.det = det / np.sqrt(np.mean(abs(det) ** 2))
        a = math.exp(-2 * math.pi * video_hz / fs)
        self.filt = ([1 - a], [1, -a])
        self.skip = int(20 * fs / (2 * math.pi * video_hz))

    def reading(self, frac_chain: float, cw_power: float = 0.0):
        """Mean and std (dB) with total noise power 1 split by frac_chain."""
        x = math.sqrt(cw_power) + math.sqrt(frac_chain) * self.chain
        x = x + math.sqrt(1 - frac_chain) * self.det
        y = lfilter(*self.filt, 10 * np.log10(np.abs(x) ** 2 + 1e-30))[self.skip :]
        return float(y.mean()), float(y.std())

    def cw_curve(self, frac_chain: float, floor_mean: float):
        """Mean offset above floor and std (dB) over a grid of CW-to-noise ratios."""
        snr = np.arange(-6.0, 45.0, 1.5)
        ms = np.array([self.reading(frac_chain, 10 ** (x / 10)) for x in snr])
        return snr, ms[:, 0] - floor_mean, ms[:, 1]


def fit(meas: dict, bn_hz: float, bw_hz: float, video_hz: float) -> dict:
    det = Detector(bn_hz, bw_hz, video_hz)
    fracs = np.linspace(0.04, 1.0, 25)
    rows = []
    for fc in fracs:
        fm, fs_ = det.reading(fc)
        snr, off, std = det.cw_curve(fc, fm)
        cw = {
            g: {
                "std_db": float(np.interp(c["above_floor_db"], off, std)),
                "cw_to_noise_db": float(np.interp(c["above_floor_db"], off, snr)),
            }
            for g, c in meas["cw"].items()
        }
        rows.append({"frac_chain": float(fc), "floor_std_db": fs_, "floor_bias_db": fm, "cw": cw})
    # Fit using baseline std and the -50 dB CW std (the two noise-sensitive observables).
    obs = np.array([meas["baseline_std_db"], meas["cw"]["-50"]["std_db"]])
    err = [
        np.sum(np.log(np.array([r["floor_std_db"], r["cw"]["-50"]["std_db"]]) / obs) ** 2)
        for r in rows
    ]
    best = rows[int(np.argmin(err))]
    return {
        "bn_mhz": bn_hz / 1e6,
        "bw_mhz": bw_hz / 1e6,
        "video_mhz": video_hz / 1e6,
        "best": best,
        "curve": [
            {
                "frac_chain": r["frac_chain"],
                "floor_std_db": r["floor_std_db"],
                "cw50_std_db": r["cw"]["-50"]["std_db"],
            }
            for r in rows
        ],
    }


def chip_separation(det: Detector, frac_chain: float, pulse_power: float, chip_s=0.5e-6) -> float:
    """Separation (d') of 0.5 us chip-averaged log output, pulse on versus off.

    A decoder-agnostic proxy for PPM chip decisions; not the FPGA algorithm.
    """
    fs = 4e9
    w = int(chip_s * fs)

    def chips(cw):
        x = math.sqrt(cw) + math.sqrt(frac_chain) * det.chain + math.sqrt(1 - frac_chain) * det.det
        y = lfilter(*det.filt, 10 * np.log10(np.abs(x) ** 2 + 1e-30))[det.skip :]
        return y[: len(y) // w * w].reshape(-1, w).mean(axis=1)

    on, off = chips(pulse_power), chips(0.0)
    return float((on.mean() - off.mean()) / math.sqrt((on.var() + off.var()) / 2))


def mds_improvement_db(frac0: float, knee_offset_db: float, gains_db, video_hz=10e6, bn_hz=10e6):
    """Input-referred pulse power reduction for equal chip separation after added gain."""
    det = Detector(bn_hz, 2e9, video_hz, n=2**21, seed=7)
    fm, _ = det.reading(frac0)
    snr, off, _ = det.cw_curve(frac0, fm)
    s_knee = 10 ** (np.interp(knee_offset_db, off, snr) / 10)  # re original total noise
    d_knee = chip_separation(det, frac0, s_knee)
    out = {"knee_pulse_to_noise_db": 10 * math.log10(s_knee), "knee_chip_separation": d_knee}
    for g_db in gains_db:
        g = 10 ** (g_db / 10)
        total = frac0 * g + (1 - frac0)
        frac = frac0 * g / total
        lo, hi = -15.0, 10 * math.log10(s_knee) + 1
        for _ in range(22):  # bisection on input-referred pulse power (dB)
            mid = (lo + hi) / 2
            d = chip_separation(det, frac, 10 ** (mid / 10) * g / total)
            lo, hi = (mid, hi) if d < d_knee else (lo, mid)
        out[f"{g_db}dB_added"] = 10 * math.log10(s_knee) - hi
    return out


def floor_improvement_db(frac_chain: float, added_gain_db: float) -> float:
    """Input-referred noise floor reduction from noiseless gain ahead of the detector."""
    nc, nd = frac_chain, 1 - frac_chain
    return 10 * math.log10((nc + nd) / (nc + nd * 10 ** (-added_gain_db / 10)))


def budget(meas: dict) -> dict:
    """Absolute-level cross-check: expected chain noise versus detector floor."""
    g = meas["implied_gain_db"]
    out = []
    for nf in (1.0, 2.0):
        for bn in (6e6, 10e6, 20e6):
            chain_det = -174 + nf + 10 * math.log10(bn) + g
            out.append(
                {
                    "nf_db": nf,
                    "bn_mhz": bn / 1e6,
                    "chain_noise_at_detector_dbm": chain_det,
                    "margin_below_detector_floor_db": DETECTOR_FLOOR_DBM - chain_det,
                }
            )
    return {"gain_db_used": g, "detector_floor_dbm": DETECTOR_FLOOR_DBM, "cases": out}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--quick", action="store_true", help="single model case (for testing)")
    args = ap.parse_args()

    meas = load_measurements()
    cases = [(8e6, 2e9, 10e6)] if args.quick else [
        (bn, bw, vid)
        for bn in (6e6, 10e6, 16e6)
        for bw in (1e9, 3e9)
        for vid in (8e6, 12e6)
    ]
    fits = [fit(meas, *c) for c in cases]
    fracs = [f["best"]["frac_chain"] for f in fits]
    result = {
        "measurements": meas,
        "budget": budget(meas),
        "fits": fits,
        "frac_chain_range": [min(fracs), max(fracs)],
        "floor_improvement_db": {
            f"{gain}dB_added": [
                floor_improvement_db(max(fracs), gain),
                floor_improvement_db(min(fracs), gain),
            ]
            for gain in (6, 10, 14, 100)
        },
    }
    # Conducted decode knee ~ -95.5 dBm at the SMA (DEC-KNEE-1DB, 7 Sep; 50 % point).
    knee_offset = -95.5 - meas["floor_cw_equivalent_sma_dbm"]
    result["mds_proxy"] = {
        "knee_sma_dbm": -95.5,
        "knee_offset_above_floor_db": knee_offset,
        "by_chain_fraction": {
            f"{fc:.2f}": mds_improvement_db(fc, knee_offset, (6, 10, 14))
            for fc in sorted({min(fracs), 0.25, max(fracs)})
        },
    }
    args.output.write_text(json.dumps(result, indent=2))
    m = meas
    print(f"slope {m['slope_mv_per_db']:.2f} mV/dB, implied gain {m['implied_gain_db']:.1f} dB")
    print(f"floor (CW-equivalent, SMA) {m['floor_cw_equivalent_sma_dbm']:.1f} dBm, "
          f"baseline std {m['baseline_std_db']:.2f} dB")
    for g, c in m["cw"].items():
        print(f"  CW {g}: {c['above_floor_db']:.1f} dB above floor, std {c['std_db']:.3f} dB")
    for f in fits:
        b = f["best"]
        print(f"Bn {f['bn_mhz']:.0f} MHz Bw {f['bw_mhz']:.0f} MHz video {f['video_mhz']:.0f} MHz: "
              f"chain fraction {b['frac_chain']:.2f}; floor std {b['floor_std_db']:.2f}; "
              + ", ".join(f"CW{g} std {v['std_db']:.3f}" for g, v in b["cw"].items()))
    for fc, v in result["mds_proxy"]["by_chain_fraction"].items():
        print(f"chain fraction {fc}: knee pulse/noise {v['knee_pulse_to_noise_db']:.1f} dB; "
              "MDS-proxy improvement " + ", ".join(
                  f"{k}: {x:.2f} dB" for k, x in v.items() if k.endswith("added")))
    print("input-referred floor reduction [min, max] dB:", {k: [round(x, 2) for x in v]
                                                for k, v in result["floor_improvement_db"].items()})


if __name__ == "__main__":
    main()
