#!/usr/bin/env python3
"""Fetch a Radarcape's raw hourly range files and reduce them to max range per azimuth.

The Radarcape range page (statistics_range.html) draws its polar plot from hourly
files http://HOST/ranges/YYYYMMDDHH-v1-ADSB.png: 360 x 40 16-bit greyscale, one
column per degree of azimuth, one row per 1000 ft altitude bucket (row 0 holds
the highest band; the page's own reader indexes from the other end), value / 64
= max range in km. Only the all-altitude maximum per azimuth is reported. A file's timestamp is the end of its accumulation hour. This
reproduces the page's "all altitudes" view as JSON (and caches the raw files).

  uv run --with pillow python fetch_radarcape_range.py \\
      --start 2026-06-01T11 --end 2026-06-30T11 --out radarcape-june.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image


def hours(start: dt.datetime, end: dt.datetime):
    t = start + dt.timedelta(hours=1)  # first file is stamped at the end of the first hour
    while t <= end:
        yield t
        t += dt.timedelta(hours=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="radarcape.local")
    ap.add_argument("--start", required=True, help="UTC, e.g. 2026-06-01T11")
    ap.add_argument("--end", required=True)
    ap.add_argument("--source", default="ADSB", help="ADSB, MLAT, FLARM, ...")
    ap.add_argument("--cache", type=Path, default=Path("radarcape-ranges"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    start = dt.datetime.strptime(args.start, "%Y-%m-%dT%H")
    end = dt.datetime.strptime(args.end, "%Y-%m-%dT%H")
    args.cache.mkdir(parents=True, exist_ok=True)
    best = np.zeros((40, 360))
    got = missing = 0
    for t in hours(start, end):
        name = f"{t:%Y%m%d%H}-v1-{args.source}.png"
        path = args.cache / name
        if not path.exists():
            try:
                with urllib.request.urlopen(f"http://{args.host}/ranges/{name}", timeout=10) as r:
                    path.write_bytes(r.read())
            except urllib.error.URLError:
                missing += 1
                continue
        a = np.asarray(Image.open(path)).astype(float)
        if a.shape != (40, 360):
            missing += 1
            continue
        best = np.maximum(best, a / 64.0)
        got += 1
    per_az = best.max(axis=0)
    out = {
        "host": args.host, "source": args.source, "start": args.start, "end": args.end,
        "hourly_files": got, "missing": missing,
        "bins": [{"bearing_deg": d, "max_range_km": float(per_az[d])} for d in range(360)],
    }
    args.out.write_text(json.dumps(out, indent=1))
    print(f"{got} hourly files ({missing} missing); farthest {per_az.max():.1f} km @ {int(per_az.argmax())} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
