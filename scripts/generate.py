#!/usr/bin/env python3
"""从 data/ 目录读取飞机快照，生成 docs/index.html 仪表盘页面"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

tz = timezone(timedelta(hours=8))


def load_today():
    today = datetime.now(tz).strftime("%Y-%m-%d")
    snap_file = DATA_DIR / f"snapshot-{today}.json"
    if not snap_file.exists():
        return []
    return json.loads(snap_file.read_text(encoding="utf-8"))


def build_html(snapshots: list[dict]) -> str:
    # 取最新一条快照
    latest = snapshots[-1] if snapshots else None
    planes = latest["planes"] if latest else []
    ts = latest["timestamp"] if latest else ""

    # 统计
    total_today = sum(s["count"] for s in snapshots)
    avg_alt = 0
    on_ground = 0
    if planes:
        alts = [p["altitude"] for p in planes if p["altitude"] is not None]
        avg_alt = sum(alts) / len(alts) if alts else 0
        on_ground = sum(1 for p in planes if p["on_ground"])

    # 生成飞机行
    rows = ""
    for p in sorted(planes, key=lambda x: x.get("altitude") or 0, reverse=True):
        alt = f"{p['altitude']:.0f} m" if p["altitude"] else "-"
        spd = f"{p['velocity']:.0f} m/s" if p["velocity"] else "-"
        hdg = f"{p['heading']:.0f}°" if p["heading"] is not None else "-"
        callsign = p["callsign"] or "-"
        icao = p["icao24"]
        lat = f"{p['latitude']:.4f}" if p["latitude"] else "-"
        lon = f"{p['longitude']:.4f}" if p["longitude"] else "-"
        rows += f"""<tr>
            <td>{callsign}</td><td>{icao}</td><td>{alt}</td>
            <td>{spd}</td><td>{hdg}</td><td>{lat}, {lon}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>藁城上空 · 飞机追踪面板</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, sans-serif; background:#0a0e17; color:#c8d6e5; padding:24px; }}
h1 {{ font-size:22px; color:#54a0ff; margin-bottom:4px; }}
.sub {{ font-size:13px; color:#8395a7; margin-bottom:20px; }}
.cards {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
.card {{ background:#1e272e; border-radius:10px; padding:18px 24px; min-width:150px; }}
.card .num {{ font-size:32px; font-weight:700; color:#feca57; }}
.card .label {{ font-size:13px; color:#8395a7; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; background:#1e272e; border-radius:10px; overflow:hidden; }}
th {{ text-align:left; padding:12px 16px; background:#2c3e50; font-size:13px; color:#54a0ff; }}
td {{ padding:10px 16px; font-size:13px; border-bottom:1px solid #2c3e50; }}
tr:hover {{ background:#2c3e50; }}
.footer {{ margin-top:20px; font-size:12px; color:#576574; text-align:center; }}
.footer a {{ color:#54a0ff; }}
</style>
</head>
<body>
<h1>🛩 藁城上空 · 实时飞机追踪</h1>
<p class="sub">数据来源 OpenSky Network · 每小时自动更新 · 范围 37.90°~38.15°N, 114.60°~115.05°E</p>

<div class="cards">
    <div class="card">
        <div class="num">{len(planes)}</div>
        <div class="label">当前空域飞机</div>
    </div>
    <div class="card">
        <div class="num">{total_today}</div>
        <div class="label">今日累计观测</div>
    </div>
    <div class="card">
        <div class="num">{avg_alt:.0f} m</div>
        <div class="label">平均高度</div>
    </div>
    <div class="card">
        <div class="num">{on_ground}</div>
        <div class="label">地面停靠</div>
    </div>
</div>

<table>
<tr>
    <th>呼号</th><th>ICAO24</th><th>高度</th><th>速度</th><th>航向</th><th>位置</th>
</tr>
{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:30px;">暂无数据，等待下一次采集...</td></tr>'}
</table>

<p class="footer">
    更新时间：{ts} (UTC+8) · 
    数据来源 <a href="https://opensky-network.org">OpenSky Network</a> · 
    自动更新于 GitHub Actions
</p>
</body>
</html>"""


def main():
    snapshots = load_today()
    html = build_html(snapshots)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print("Generated docs/index.html")


if __name__ == "__main__":
    main()
