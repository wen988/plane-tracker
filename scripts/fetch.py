#!/usr/bin/env python3
"""
抓取石家庄及周边上空飞机数据（OpenSky Network API）
坐标范围：纬度 37.5~38.6，经度 114.0~115.8（覆盖石家庄市区、正定机场、晋州、栾城、邢台北部）"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# 石家庄及周边地理范围（覆盖市区、正定机场、晋州、栾城、邢台北部）
LAMIN = 37.50   # 南
LAMAX = 38.60   # 北
LOMIN = 114.00  # 西
LOMAX = 115.80  # 东

API_URL = "https://opensky-network.org/api/states/all"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_PARAMS = {
    "latitude": 38.05,
    "longitude": 114.90,
    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weather_code,visibility",
}
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_PARAMS = {
    "latitude": 38.05,
    "longitude": 114.90,
    "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,weather_code,visibility",
    "timezone": "Asia/Shanghai",
    "forecast_days": 1,
}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "PlaneTracker/1.0 (GitHub Actions; personal project)"
}

tz = timezone(timedelta(hours=8))  # UTC+8


def fetch_states() -> list[dict]:
    """抓取石家庄及周边上空飞机状态（带 OpenSky 认证）"""
    import os
    client_id = os.environ.get("OPENSKY_CLIENT_ID", "")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET", "")
    params = {
        "lamin": LAMIN,
        "lomin": LOMIN,
        "lamax": LAMAX,
        "lomax": LOMAX,
    }
    try:
        if client_id and client_secret:
            auth_resp = requests.post(
                "https://opensky-network.org/api/token",
                json={"client_id": client_id, "client_secret": client_secret},
                timeout=10
            )
            auth_resp.raise_for_status()
            token = auth_resp.json().get("access_token", "")
            req_headers = {**HEADERS, "Authorization": f"Bearer {token}"}
            r = requests.get(API_URL, params=params, headers=req_headers, timeout=30)
        else:
            r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        states = data.get("states") or []
        result = []
        for s in states:
            result.append({
                "icao24":      s[0],
                "callsign":    (s[1] or "").strip(),
                "origin":      s[2] or "",
                "longitude":   s[5],
                "latitude":    s[6],
                "altitude":    s[7],
                "on_ground":   s[8],
                "velocity":    s[9],
                "heading":     s[10],
                "vertical":    s[11],
            })
        return result
    except Exception as e:
        print(f"States fetch failed: {e}")
        return []


def fetch_weather() -> dict:
    """抓取藁城区实时天气（Open-Meteo，免费无限调用）"""
    try:
        r = requests.get(WEATHER_URL, params=WEATHER_PARAMS, timeout=10)
        r.raise_for_status()
        return r.json()  # 返回原始结构 {"current": {"temperature_2m": ..., ...}}
    except Exception as e:
        print(f"Weather fetch failed: {e}")
        return {"current": {}}


def fetch_forecast() -> dict:
    """抓取藁城区24小时天气预报"""
    try:
        r = requests.get(FORECAST_URL, params=FORECAST_PARAMS, timeout=10)
        r.raise_for_status()
        data = r.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        result = []
        for i, t in enumerate(times):
            result.append({
                "time": t,
                "temperature": hourly.get("temperature_2m", [None])[i] if i < len(hourly.get("temperature_2m", [])) else None,
                "humidity": hourly.get("relative_humidity_2m", [None])[i] if i < len(hourly.get("relative_humidity_2m", [])) else None,
                "precip_prob": hourly.get("precipitation_probability", [None])[i] if i < len(hourly.get("precipitation_probability", [])) else None,
                "wind_speed": hourly.get("wind_speed_10m", [None])[i] if i < len(hourly.get("wind_speed_10m", [])) else None,
                "wind_direction": hourly.get("wind_direction_10m", [None])[i] if i < len(hourly.get("wind_direction_10m", [])) else None,
                "weather_code": hourly.get("weather_code", [None])[i] if i < len(hourly.get("weather_code", [])) else None,
                "visibility": hourly.get("visibility", [None])[i] if i < len(hourly.get("visibility", [])) else None,
            })
        return {"hourly": result}
    except Exception as e:
        print(f"Forecast fetch failed: {e}")
        return {"hourly": []}


def main():
    print(f"[{datetime.now(tz).isoformat()}] Fetching plane data...")
    try:
        planes = fetch_states()
    except Exception as e:
        print(f"Fetch failed: {e}")
        planes = []

    print("Fetching weather...")
    weather = fetch_weather()
    forecast = fetch_forecast()

    timestamp = datetime.now(tz).isoformat()
    record = {
        "timestamp": timestamp,
        "count": len(planes),
        "bbox": {"lamin": LAMIN, "lamax": LAMAX, "lomin": LOMIN, "lomax": LOMAX},
        "planes": planes,
        "weather": weather,
        "forecast": forecast,
    }

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

    all_snaps = sorted(DATA_DIR.glob("snapshot-*.json"))
    if len(all_snaps) > 30:
        for old in all_snaps[:-30]:
            old.unlink()

    print(f"Done. {len(planes)} planes, saved to {snap_file}")


if __name__ == "__main__":
    main()
