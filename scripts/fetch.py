#!/usr/bin/env python3
"""
抓取藁城区上空飞机数据（OpenSky Network API）
坐标范围：纬度 37.95~38.1，经度 114.7~115.0（覆盖藁城及周边）
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# 藁城区地理范围（稍微放大覆盖周边航线）
LAMIN = 37.90   # 南
LAMAX = 38.15   # 北
LOMIN = 114.60  # 西
LOMAX = 115.05  # 东

API_URL = "https://opensky-network.org/api/states/all"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "PlaneTracker/1.0 (GitHub Actions; personal project)"
}

tz = timezone(timedelta(hours=8))  # UTC+8


def fetch_states() -> list[dict]:
    params = {
        "lamin": LAMIN,
        "lomin": LOMIN,
        "lamax": LAMAX,
        "lomax": LOMAX,
    }
    r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    states = data.get("states") or []
    result = []
    for s in states:
        result.append({
            "icao24":      s[0],                         # ICAO24 识别码
            "callsign":    (s[1] or "").strip(),          # 呼号
            "origin":      s[2] or "",                    # 始发国
            "longitude":   s[5],                          # 经度
            "latitude":    s[6],                          # 纬度
            "altitude":    s[7],                          # 气压高度(m)
            "on_ground":   s[8],                          # 是否在地面
            "velocity":    s[9],                          # 速度(m/s)
            "heading":     s[10],                         # 航向(度)
            "vertical":    s[11],                         # 垂直速率(m/s)
        })
    return result


def main():
    print(f"[{datetime.now(tz).isoformat()}] Fetching plane data...")
    try:
        planes = fetch_states()
    except Exception as e:
        print(f"Fetch failed: {e}")
        planes = []

    timestamp = datetime.now(tz).isoformat()
    record = {
        "timestamp": timestamp,
        "count": len(planes),
        "bbox": {"lamin": LAMIN, "lamax": LAMAX, "lomin": LOMIN, "lomax": LOMAX},
        "planes": planes,
    }

    # 保存当天快照
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    snap_file = DATA_DIR / f"snapshot-{date_str}.json"

    existing = []
    if snap_file.exists():
        try:
            existing = json.loads(snap_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            existing = []

    existing.append(record)
    snap_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保留最近30天
    all_snaps = sorted(DATA_DIR.glob("snapshot-*.json"))
    if len(all_snaps) > 30:
        for old in all_snaps[:-30]:
            old.unlink()

    print(f"Done. {len(planes)} planes, saved to {snap_file}")


if __name__ == "__main__":
    main()
