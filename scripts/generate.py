#!/usr/bin/env python3
"""从 data/ 读取历史快照，生成苹果风仪表盘"""

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, median

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

tz = timezone(timedelta(hours=8))


def load_all_snapshots():
    """加载所有日期的快照，返回 (日期, 快照列表) 的列表"""
    result = []
    for f in sorted(DATA_DIR.glob("snapshot-*.json")):
        date_str = f.stem.replace("snapshot-", "")
        try:
            snaps = json.loads(f.read_text(encoding="utf-8"))
            result.append((date_str, snaps))
        except (json.JSONDecodeError, ValueError):
            continue
    return result


def load_today():
    today = datetime.now(tz).strftime("%Y-%m-%d")
    snap_file = DATA_DIR / f"snapshot-{today}.json"
    if not snap_file.exists():
        return []
    return json.loads(snap_file.read_text(encoding="utf-8"))


def build_dashboard():
    all_data = load_all_snapshots()
    today_snaps = load_today()

    # ---- 今日数据 ----
    latest = today_snaps[-1] if today_snaps else None
    planes = latest["planes"] if latest else []
    ts = latest["timestamp"] if latest else ""
    total_today = sum(s["count"] for s in today_snaps)

    alts = [p["altitude"] for p in planes if p["altitude"] is not None]
    avg_alt = mean(alts) if alts else 0
    max_alt = max(alts) if alts else 0
    min_alt = min(alts) if alts else 0
    on_ground = sum(1 for p in planes if p["on_ground"])

    # ---- 今日每小时统计 ----
    hourly = defaultdict(int)
    for s in today_snaps:
        try:
            h = datetime.fromisoformat(s["timestamp"]).hour
            hourly[h] += s["count"]
        except (ValueError, KeyError):
            continue
    hourly_labels = sorted(hourly.keys())
    hourly_values = [hourly[h] for h in hourly_labels]

    # ---- 每日总量统计 ----
    daily_totals = []
    for date_str, snaps in all_data:
        daily_totals.append({"date": date_str, "total": sum(s["count"] for s in snaps)})

    # ---- 今日高度分布 ----
    alt_bins = {"0-1000m": 0, "1000-3000m": 0, "3000-6000m": 0, "6000-9000m": 0, "9000m+": 0}
    for a in alts:
        if a < 1000: alt_bins["0-1000m"] += 1
        elif a < 3000: alt_bins["1000-3000m"] += 1
        elif a < 6000: alt_bins["3000-6000m"] += 1
        elif a < 9000: alt_bins["6000-9000m"] += 1
        else: alt_bins["9000m+"] += 1

    # ---- 回放数据：最近24小时的时间线 ----
    replay_data = []
    for date_str, snaps in all_data:
        for s in snaps:
            try:
                t = datetime.fromisoformat(s["timestamp"])
                replay_data.append({
                    "time": t.strftime("%m-%d %H:%M"),
                    "count": s["count"],
                })
            except (ValueError, KeyError):
                continue
    # 只取最近24小时
    replay_data = replay_data[-48:]

    # ---- 今日飞机表格 ----
    rows = ""
    for i, p in enumerate(sorted(planes, key=lambda x: x.get("altitude") or 0, reverse=True)):
        alt = f'{p["altitude"]:.0f} m' if p["altitude"] else "-"
        spd = f'{p["velocity"]:.0f} m/s' if p["velocity"] else "-"
        hdg = f'{p["heading"]:.0f}°' if p["heading"] is not None else "-"
        callsign = p["callsign"] or "-"
        lat = f'{p["latitude"]:.4f}' if p["latitude"] else "-"
        lon = f'{p["longitude"]:.4f}' if p["longitude"] else "-"
        rows += f"""<tr>
            <td>{callsign}</td><td>{alt}</td><td>{spd}</td><td>{hdg}</td><td>{lat}, {lon}</td>
        </tr>"""

    # ---- 回放JS数据 ----
    replay_js = json.dumps(replay_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>藁城上空 · SkyWatch</title>
<style>
:root {{
    --bg: #f5f5f7;
    --card: rgba(255,255,255,0.72);
    --card-hover: rgba(255,255,255,0.88);
    --text: #1d1d1f;
    --secondary: #86868b;
    --accent: #0071e3;
    --green: #34c759;
    --orange: #ff9500;
    --red: #ff3b30;
    --border: rgba(0,0,0,0.06);
    --shadow: 0 8px 32px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.02);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 40px 48px;
    -webkit-font-smoothing: antialiased;
}}
header {{ margin-bottom: 36px; }}
header h1 {{ font-size: 32px; font-weight: 700; letter-spacing: -0.5px; }}
header p {{ color: var(--secondary); font-size: 15px; margin-top: 6px; }}

/* Stats grid */
.stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}
.stat-card {{
    background: var(--card);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 18px;
    padding: 20px 24px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: transform 0.2s, background 0.2s;
}}
.stat-card:hover {{ background: var(--card-hover); transform: translateY(-2px); }}
.stat-card .value {{ font-size: 34px; font-weight: 700; letter-spacing: -1px; }}
.stat-card .label {{ font-size: 13px; color: var(--secondary); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
.value.blue {{ color: var(--accent); }}
.value.green {{ color: var(--green); }}
.value.orange {{ color: var(--orange); }}

/* Panel */
.panel {{
    background: var(--card);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 18px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    padding: 28px;
    margin-bottom: 24px;
}}
.panel h2 {{
    font-size: 20px; font-weight: 600; margin-bottom: 20px;
    display: flex; align-items: center; gap: 10px;
}}

/* Replay */
.replay-controls {{
    display: flex; gap: 12px; margin-bottom: 16px; align-items: center;
}}
.btn {{
    padding: 8px 18px; border-radius: 20px; border: 1px solid rgba(0,0,0,0.12);
    background: rgba(255,255,255,0.6); font-size: 13px; font-weight: 500;
    cursor: pointer; font-family: inherit; color: var(--text);
    transition: all 0.15s;
}}
.btn:hover {{ background: rgba(0,0,0,0.04); }}
.btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.replay-bar {{
    height: 6px; background: rgba(0,0,0,0.06); border-radius: 3px;
    position: relative; overflow: hidden; flex: 1; margin: 0 8px;
}}
.replay-progress {{
    height: 100%; background: var(--accent); border-radius: 3px;
    transition: width 0.3s;
}}
.replay-label {{ font-size: 12px; color: var(--secondary); min-width: 70px; text-align: center; }}

/* Hourly chart */
.bars {{
    display: flex; align-items: flex-end; gap: 8px; height: 140px;
    padding-top: 8px;
}}
.bar {{
    flex: 1; background: var(--accent); border-radius: 6px 6px 0 0;
    min-height: 4px; opacity: 0.8; transition: opacity 0.2s;
    position: relative;
}}
.bar:hover {{ opacity: 1; }}
.bar .tip {{
    position: absolute; top: -22px; left: 50%; transform: translateX(-50%);
    font-size: 11px; color: var(--secondary); white-space: nowrap;
    opacity: 0; transition: opacity 0.2s;
}}
.bar:hover .tip {{ opacity: 1; }}
.bar .hour {{
    position: absolute; bottom: -22px; left: 50%; transform: translateX(-50%);
    font-size: 11px; color: var(--secondary);
}}

/* Altitude distribution */
.alt-bars {{
    display: flex; gap: 12px; flex-wrap: wrap;
}}
.alt-bar {{
    flex: 1; min-width: 90px; text-align: center;
}}
.alt-bar .fill {{
    height: 80px; background: rgba(0,0,0,0.06); border-radius: 10px;
    position: relative; overflow: hidden; margin-bottom: 8px;
}}
.alt-bar .level {{
    position: absolute; bottom: 0; width: 100%;
    background: linear-gradient(180deg, var(--accent), rgba(0,113,227,0.3));
    border-radius: 10px 10px 0 0; transition: height 0.4s;
}}
.alt-bar .num {{ font-size: 15px; font-weight: 600; }}
.alt-bar .range {{ font-size: 11px; color: var(--secondary); }}

/* Table */
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 12px 16px; font-size: 12px; color: var(--secondary); text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }}
td {{ padding: 11px 16px; font-size: 14px; border-bottom: 1px solid var(--border); }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(0,0,0,0.02); }}

/* Daily totals */
.daily-list {{
    display: flex; gap: 12px; flex-wrap: wrap;
}}
.daily-item {{
    flex: 1; min-width: 100px; text-align: center;
    background: rgba(0,0,0,0.02); border-radius: 12px; padding: 14px 10px;
}}
.daily-item .num {{ font-size: 20px; font-weight: 700; }}
.daily-item .date {{ font-size: 11px; color: var(--secondary); margin-top: 4px; }}

footer {{
    text-align: center; color: var(--secondary); font-size: 12px;
    margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--border);
}}

@media (max-width: 768px) {{
    body {{ padding: 20px 16px; }}
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>

<header>
    <h1>SkyWatch</h1>
    <p>藁城上空 · 实时飞行追踪 — 数据来源 OpenSky Network · 更新时间 {ts}</p>
</header>

<!-- 统计卡片 -->
<div class="stats">
    <div class="stat-card">
        <div class="value blue">{len(planes)}</div>
        <div class="label">当前空域</div>
    </div>
    <div class="stat-card">
        <div class="value">{total_today}</div>
        <div class="label">今日累计观测</div>
    </div>
    <div class="stat-card">
        <div class="value green">{avg_alt:.0f}m</div>
        <div class="label">平均高度</div>
    </div>
    <div class="stat-card">
        <div class="value orange">{max_alt:.0f}m</div>
        <div class="label">最高飞行</div>
    </div>
    <div class="stat-card">
        <div class="value">{min_alt:.0f}m</div>
        <div class="label">最低飞行</div>
    </div>
    <div class="stat-card">
        <div class="value">{on_ground}</div>
        <div class="label">地面停靠</div>
    </div>
</div>

<!-- 回放面板 -->
<div class="panel">
    <h2>⏯ 24小时回放</h2>
    <div class="replay-controls">
        <button class="btn" onclick="replayStart()">▶ 播放</button>
        <button class="btn" onclick="replayPause()">⏸ 暂停</button>
        <button class="btn" onclick="replayReset()">↺ 重置</button>
        <div class="replay-bar"><div class="replay-progress" id="replayBar"></div></div>
        <span class="replay-label" id="replayLabel">--</span>
    </div>
</div>

<!-- 今日每小时统计 -->
<div class="panel">
    <h2>📊 今日每小时观测量</h2>
    <div class="bars">
        {"".join(
            f'<div class="bar" style="height:{max(4, int(v / (max(hourly_values) or 1)*130))}px"><span class="tip">{v}</span><span class="hour">{h}时</span></div>'
            for h, v in zip(hourly_labels, hourly_values)
        ) if hourly_values else '<p style="color:var(--secondary)">数据采集中…</p>'}
    </div>
</div>

<!-- 高度分布 -->
<div class="panel">
    <h2>📐 今日高度分布</h2>
    <div class="alt-bars">
        {''.join(
            f'<div class="alt-bar"><div class="fill"><div class="level" style="height:{max(4, int(c/max(alt_bins.values())*80) if max(alt_bins.values())>0 else 4)}px"></div></div><div class="num">{c}</div><div class="range">{k}</div></div>'
            for k, c in alt_bins.items()
        )}
    </div>
</div>

<!-- 每日总量 -->
<div class="panel">
    <h2>📅 每日飞行总量</h2>
    <div class="daily-list">
        {''.join(
            f'<div class="daily-item"><div class="num">{d["total"]}</div><div class="date">{d["date"][-5:]}</div></div>'
            for d in daily_totals[-14:]
        ) if daily_totals else '<p style="color:var(--secondary)">数据采集中…</p>'}
    </div>
</div>

<!-- 当前飞机列表 -->
<div class="panel">
    <h2>🛩 当前空域 ({len(planes)} 架)</h2>
    <table>
    <tr><th>呼号</th><th>高度</th><th>速度</th><th>航向</th><th>位置</th></tr>
    {rows if rows else '<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--secondary)">暂无数据，等待采集…</td></tr>'}
    </table>
</div>

<footer>
    SkyWatch · 藁城上空飞行追踪 · 数据来源 OpenSky Network · 每小时自动更新 · Powered by GitHub Actions
</footer>

<script>
const replayData = {replay_js};
let replayIdx = 0;
let replayTimer = null;

function updateReplay() {{
    if (replayIdx >= replayData.length) {{ replayPause(); return; }}
    const d = replayData[replayIdx];
    document.getElementById('replayBar').style.width = ((replayIdx+1)/replayData.length*100) + '%';
    document.getElementById('replayLabel').textContent = d.time + ' · ' + d.count + '架';
    replayIdx++;
}}

function replayStart() {{ replayPause(); replayTimer = setInterval(updateReplay, 300); }}
function replayPause() {{ clearInterval(replayTimer); }}
function replayReset() {{ replayPause(); replayIdx = 0; document.getElementById('replayBar').style.width = '0'; document.getElementById('replayLabel').textContent = '--'; }}
</script>

</body>
</html>"""

    return html


def main():
    html = build_dashboard()
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Generated docs/index.html ({len(html)} chars)")


if __name__ == "__main__":
    main()
