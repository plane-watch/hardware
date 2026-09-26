#!/usr/bin/env python3
"""Compare PlaneWatcher /api/coverage snapshots bearing by bearing.

  python3 compare_coverage.py BASELINE.json [OTHER.json ...] CURRENT.json

Each file is a coverage snapshot: either the board's /api/coverage JSON
(max_range_nm per 1-degree bearing) or this report's scrubbed data/coverage
files (max_range_km). Every earlier snapshot is compared with the last one.
Ranges are reported in km.
"""

from __future__ import annotations

import json
import statistics as st
import sys

NM = 1.852
SECTORS = {"North 330-30": (330, 30), "East 60-120": (60, 120),
           "South 150-210": (150, 210), "West 240-300": (240, 300)}


def load(path: str) -> tuple[str, dict[int, dict]]:
    data = json.load(open(path))
    return data.get("generated", path), {b["bearing_deg"]: b for b in data["bins"]}


def in_sector(deg: int, lo: int, hi: int) -> bool:
    return lo <= deg or deg < hi if lo > hi else lo <= deg < hi


def km(b: dict) -> float:
    if "max_range_km" in b:
        return b["max_range_km"] or 0.0
    return (b.get("max_range_nm") or 0.0) * NM


def compare(base: dict[int, dict], cur: dict[int, dict]) -> None:
    common = [d for d in cur if d in base and km(cur[d]) > 0 and km(base[d]) > 0]
    beat = [d for d in common if km(cur[d]) > km(base[d]) + 0.1]
    print(f"  bearings where current exceeds this snapshot: {len(beat)} of {len(common)}")
    print(f"  median range {st.median(km(base[d]) for d in common):.1f} -> "
          f"{st.median(km(cur[d]) for d in common):.1f} km; farthest "
          f"{max(km(b) for b in base.values()):.1f} -> {max(km(b) for b in cur.values()):.1f} km")
    for name, (lo, hi) in SECTORS.items():
        ds = [d for d in common if in_sector(d, lo, hi)]
        print(f"  {name:>13}: {st.median(km(base[d]) for d in ds):5.0f} -> {st.median(km(cur[d]) for d in ds):5.0f} km")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    snaps = [load(p) for p in sys.argv[1:]]
    cur_label, cur = snaps[-1]
    top = sorted(cur.values(), key=km, reverse=True)[:5]
    print(f"current {cur_label}: farthest bins " + ", ".join(
        f"{b['bearing_deg']} deg {km(b):.0f} km @ {b.get('alt_ft')} ft" for b in top))
    for label, base in snaps[:-1]:
        print(f"vs {label}:")
        compare(base, cur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
