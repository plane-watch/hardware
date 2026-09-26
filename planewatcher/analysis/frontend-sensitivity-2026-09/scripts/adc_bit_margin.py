#!/usr/bin/env python3
"""Measure ADS-B PPM bit-decision margin in saved raw ADC captures.

Offline only. For each capture of the known DF17 test waveform, finds data
runs (every 1 us bit carries exactly one 0.5 us pulse), aligns the bit clock
and forms D = mean(first half-bit) - mean(second half-bit) per bit.  The
magnitude |D| clusters at the pulse contrast mu; its spread gives sigma.  An
ideal hard-decision decoder with these statistics has bit error Q(mu/sigma)
and 112-bit frame success (1 - Q)^112, ignoring preamble detection and CRC
correction.  Compare with the FPGA decode rate measured at the same source
setting to see whether RF noise or the digital detection chain sets the knee.

Run with the plane_watcher tools environment (for pwcap):
  uv run --project ~/plane_watcher/tools --no-sync python \
      scripts/adc_bit_margin.py \
      --output result.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "plane_watcher" / "tools"))
import pwcap  # noqa: E402

RAW = Path.home() / ("plane_watcher/artifacts/tools/frontend/raw-adc")
SUMMARY = RAW / "20260907_df17_gain_sweep_summary.csv"
KNEE = Path.home() / "plane_watcher/artifacts/tools/frontend/decode-sweeps/20260907_remote_knee_1db_10s.csv"
SPB = 32  # samples per 1 us bit at 32 MS/s
FRAME_BITS = 112


def q(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2))


def windows(path: Path) -> np.ndarray:
    return np.array([r.codes.astype(float) for r in pwcap.read_pwcap(path)])


def bit_contrasts(x: np.ndarray, min_bits: int = 12) -> list[np.ndarray]:
    """Signed per-bit contrasts for each candidate data run in one window."""
    med = np.median(x)
    h = np.percentile(x, 97) - med
    if h <= 0:
        return []
    # A 2 us average always holds at least one 0.5 us pulse inside a PPM data
    # block (worst case "1,0" leaves a 1 us gap), so it stays above h / 8.
    sm = np.convolve(x - med, np.ones(2 * SPB) / (2 * SPB), "same")
    active = sm > h / 8
    out: list[np.ndarray] = []
    edges = np.flatnonzero(np.diff(np.r_[0, active.astype(int), 0]))
    for start, stop in zip(edges[::2], edges[1::2]):
        start, stop = start + SPB, stop - SPB  # trim partial bits at run edges
        if stop - start < min_bits * SPB:
            continue
        best = None
        for phase in range(SPB):
            n = (stop - start - phase) // SPB
            seg = x[start + phase : start + phase + n * SPB].reshape(n, SPB)
            d = seg[:, : SPB // 2].mean(1) - seg[:, SPB // 2 :].mean(1)
            score = np.abs(d).sum()
            if best is None or score > best[0]:
                best = (score, d)
        out.append(best[1])
    return out


def noise_sigma(path: Path) -> float:
    """Contrast spread with the source off: arbitrary half-bit splits of noise."""
    w = windows(path)
    seg = w[:, : w.shape[1] // SPB * SPB].reshape(-1, SPB)
    return float(np.std(seg[:, : SPB // 2].mean(1) - seg[:, SPB // 2 :].mean(1)))


def stats(runs: list[np.ndarray], sigma_off: float) -> dict:
    # Reject candidate runs without PPM structure (baseline excursions with no
    # frame): a data run's median |D| must clear 3x the source-off spread.
    kept = [r for r in runs if np.median(np.abs(r)) >= 3 * sigma_off]
    d = np.concatenate(kept) if kept else np.array([])
    a = np.abs(d)
    mu = float(np.median(a))
    sigma = float(1.4826 * np.median(np.abs(a - mu)))
    p = q(mu / sigma)
    return {
        "runs_kept": len(kept),
        "runs_rejected": len(runs) - len(kept),
        "ambiguous_bits_below_quarter_mu": int(np.sum(a < mu / 4)),
        "mu_over_sigma_off": mu / sigma_off,
        "bits": int(len(d)),
        "mu_codes": mu,
        "sigma_codes": sigma,
        "mu_over_sigma": mu / sigma,
        "ideal_bit_error": p,
        "ideal_frame_success": (1 - p) ** FRAME_BITS,
    }


def decode_rates(path: Path | None) -> dict[int, float]:
    if path is None:
        return {}
    with path.open() as fh:
        return {int(float(r["tx-gain-db"])): float(r["decode %"]) for r in csv.DictReader(fh)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--captures", type=Path,
                    help="directory with source-off.pwcap and df17<gain>.pwcap (default: 7 Sep set)")
    ap.add_argument("--pw-sweep", type=Path, help="PlaneWatcher decode sweep CSV for the same session")
    ap.add_argument("--beast-sweep", type=Path, help="Beast decode sweep CSV for the same session")
    args = ap.parse_args()

    if args.captures:
        sigma_off = noise_sigma(args.captures / "source-off.pwcap")
        items = sorted(
            ((int(p.stem[4:]), p, None) for p in args.captures.glob("df17-*.pwcap")), reverse=True
        )
        fpga, beast = decode_rates(args.pw_sweep), decode_rates(args.beast_sweep)
    else:
        sigma_off = noise_sigma(RAW / "20260907_source-off_baseline.pwcap")
        with SUMMARY.open() as fh:
            items = [(int(r["pluto_gain_db"]), RAW / r["artifact"], float(r["estimated_receiver_plane_dbm"]))
                     for r in csv.DictReader(fh)]
        fpga, beast = decode_rates(KNEE), {}
    rows = []
    for gain, path, sma in items:
        runs = [r for w in windows(path) for r in bit_contrasts(w)]
        rows.append(
            {
                "pluto_gain_db": gain,
                # Without an absolute source reference, use Pluto gain as the relative axis.
                "sma_dbm_estimate": sma if sma is not None else float(gain),
                "fpga_decode_percent": fpga.get(gain),
                "beast_decode_percent": beast.get(gain),
                "artifact": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **stats(runs, sigma_off),
            }
        )
    # Extrapolate mu (linear-in-power regime) to the ideal-decoder 50 % point.
    p = np.array([r["sma_dbm_estimate"] for r in rows])
    mu = np.array([r["mu_codes"] for r in rows])
    sig = float(np.median([r["sigma_codes"] for r in rows]))
    k, c = np.polyfit(p, 10 * np.log10(mu), 1)  # dB of contrast per dB input
    need = 2.50 * sig  # Q^-1(1 - 0.5**(1/112)) ~= 2.50
    p50 = (10 * math.log10(need) - c) / k
    result = {
        "rows": rows,
        "contrast_db_per_input_db": k,
        "sigma_codes_median": sig,
        "sigma_codes_source_off": sigma_off,
        "ideal_decoder_50pct_sma_dbm_extrapolated": p50,
        "fpga_50pct_sma_dbm_approx": -95.5,
        "notes": "Ideal hard-decision bound; ignores preamble detection, timing search, CRC repair. "
        "Absolute dBm inherits pre-level-calibration tinySA references; differences are relative.",
    }
    args.output.write_text(json.dumps(result, indent=2))
    for r in rows:
        print(
            f"gain {r['pluto_gain_db']} ({r['sma_dbm_estimate']:.1f} dBm): bits {r['bits']}, "
            f"mu {r['mu_codes']:.1f}, sigma {r['sigma_codes']:.1f}, mu/sigma {r['mu_over_sigma']:.2f}, "
            f"(vs noise-only {r['mu_over_sigma_off']:.1f}), "
            f"ambiguous {r['ambiguous_bits_below_quarter_mu']}, "
            f"rejected runs {r['runs_rejected']}, "
            f"ideal frame {100 * r['ideal_frame_success']:.1f}%  FPGA {r['fpga_decode_percent']}%  "
            f"Beast {r['beast_decode_percent']}%"
        )
    print(f"contrast slope {k:.2f} dB/dB; ideal-decoder 50% point extrapolates to {p50:.1f} (x-axis units)")


if __name__ == "__main__":
    main()
