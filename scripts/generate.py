#!/usr/bin/env python3
"""生成苹果风藁城上空飞行追踪仪表盘（含地图、气象、密码保护）"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
from statistics import mean

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

tz = timezone(timedelta(hours=8))

# --- 密码哈希（默认：gaocheng，想改密码就改下面一行）---
PASSWORD_HASH = hashlib.sha256("gaocheng".encode()).hexdigest()

CENTER_LAT, CENTER_LNG = 37.94, 114.84

WEATHER_LABELS = {
    0: "晴", 1: "大部晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇", 51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "中阵雨", 82: "大阵雨", 95: "雷暴", 96: "冰雹雷暴", 99: "强冰雹雷暴",
}


def load_all_snapshots():
    result = []
    for f in sorted(DATA_DIR.glob("snapshot-*.json")):
        date_str = f.stem.replace("snapshot-", "")
        try:
            result.append((date_str, json.loads(f.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, ValueError):
            continue
    return result


def load_today():
    today = datetime.now(tz).strftime("%Y-%m-%d")
    f = DATA_DIR / f"snapshot-{today}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def build():
    all_data = load_all_snapshots()
    today_snaps = load_today()

    latest = today_snaps[-1] if today_snaps else None
    planes = latest["planes"] if latest else []
    weather = latest.get("weather", {}) if latest else {}
    ts = latest["timestamp"] if latest else ""

    total_today = sum(s["count"] for s in today_snaps)
    alts = [p["altitude"] for p in planes if p["altitude"] is not None]
    avg_alt = mean(alts) if alts else 0
    max_alt = max(alts) if alts else 0
    on_ground = sum(1 for p in planes if p.get("on_ground"))

    wcode = weather.get("weather_code")
    weather_desc = WEATHER_LABELS.get(wcode, "—") if wcode is not None else "—"
    temp = weather.get("temperature", "—")
    humidity = weather.get("humidity", "—")
    wind_speed = weather.get("wind_speed", "—")
    wind_dir = weather.get("wind_direction", "—")
    visibility = weather.get("visibility", "—")

    markers_js_parts = []
    for p in planes:
        lat = p.get("latitude")
        lng = p.get("longitude")
        if lat is None or lng is None:
            continue
        alt = f'{p["altitude"]:.0f}m' if p.get("altitude") else "?"
        spd = f'{p["velocity"]:.0f}m/s' if p.get("velocity") else "?"
        cs = p.get("callsign") or "N/A"
        hdg = p.get("heading")
        rotate = f"rotate({hdg}deg)" if hdg is not None else "rotate(0deg)"
        on_gnd = p.get("on_ground", False)
        color = "#34c759" if on_gnd else "#0071e3"
        markers_js_parts.append(
            f'L.marker([{lat},{lng}],{{icon:L.divIcon({{className:"plane-icon",html:\'<div style="transform:{rotate};color:{color};font-size:18px">✈</div>\',iconSize:[28,28],iconAnchor:[14,14]}})}}).bindPopup(\'<b>{cs}</b><br>高度:{alt}<br>速度:{spd}\').addTo(map);'
        )
    markers_js = "\n".join(markers_js_parts)

    rows = ""
    for p in sorted(planes, key=lambda x: x.get("altitude") or 0, reverse=True):
        alt = f'{p["altitude"]:.0f} m' if p["altitude"] else "—"
        spd = f'{p["velocity"]:.0f} m/s' if p["velocity"] else "—"
        hdg = f'{p["heading"]:.0f}°' if p.get("heading") is not None else "—"
        cs = p.get("callsign") or "—"
        status = "地面" if p.get("on_ground") else "飞行中"
        lat = f'{p["latitude"]:.4f}' if p.get("latitude") else "—"
        lng = f'{p["longitude"]:.4f}' if p.get("longitude") else "—"
        rows += f'<tr><td><span class="callsign">{cs}</span></td><td>{alt}</td><td>{spd}</td><td>{hdg}</td><td>{status}</td><td class="coord">{lat}, {lng}</td></tr>'

    daily_totals = []
    for date_str, snaps in all_data:
        daily_totals.append({"date": date_str, "total": sum(s["count"] for s in snaps)})

    daily_items = ""
    for d in daily_totals[-7:]:
        daily_items += f'<div class="daily-item"><span class="daily-num">{d["total"]}</span><span class="daily-date">{d["date"][-5:]}</span></div>'

    hourly = defaultdict(int)
    for s in today_snaps:
        try:
            h = datetime.fromisoformat(s["timestamp"]).hour
            hourly[h] += s["count"]
        except (ValueError, KeyError):
            continue
    hourly_labels = sorted(hourly.keys())
    hourly_values = [hourly[h] for h in hourly_labels]
    max_hourly = max(hourly_values) if hourly_values else 1
    bar_chart = ""
    for h, v in zip(hourly_labels, hourly_values):
        pct = max(4, int(v / max_hourly * 100))
        bar_chart += f'<div class="hbar"><div class="hbar-fill" style="height:{pct}%"></div><span class="hbar-val">{v}</span><span class="hbar-label">{h}:00</span></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>SkyWatch · 藁城</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{{--bg:#fff;--card:#fff;--text:#1d1d1f;--sec:#86868b;--accent:#0071e3;--green:#34c759;--orange:#ff9500;--border:rgba(0,0,0,.06);--shadow:0 1px 3px rgba(0,0,0,.04),0 1px 2px rgba(0,0,0,.02)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","PingFang SC",sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;line-height:1.6}}
.auth-overlay{{position:fixed;inset:0;background:rgba(255,255,255,.96);backdrop-filter:blur(20px);z-index:9999;display:flex;align-items:center;justify-content:center}}
.auth-box{{text-align:center;padding:48px;max-width:360px;width:100%}}
.auth-box h2{{font-size:24px;font-weight:500;margin-bottom:8px;letter-spacing:-.3px}}
.auth-box p{{color:var(--sec);font-size:15px;margin-bottom:24px}}
.auth-box input{{width:100%;padding:12px 16px;border:1px solid rgba(0,0,0,.12);border-radius:10px;font-size:16px;font-family:inherit;outline:none;transition:border-color .2s}}
.auth-box input:focus{{border-color:var(--accent)}}
.auth-box .err{{color:#ff3b30;font-size:13px;margin-top:8px;display:none}}
nav{{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.72);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(0,0,0,.06);padding:0 32px;height:52px;display:flex;align-items:center;justify-content:space-between}}
nav .logo{{font-size:18px;font-weight:600;letter-spacing:-.3px}}
nav .time{{font-size:13px;color:var(--sec)}}
#map{{height:520px;width:100%;margin-top:52px}}
.leaflet-container{{background:#f5f5f7}}
.plane-icon div{{transition:transform .3s}}
.content{{max-width:1100px;margin:0 auto;padding:0 32px}}
.stats-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;padding:32px 0 24px}}
.stat{{text-align:center;padding:16px 12px;border-radius:16px;background:var(--card);box-shadow:var(--shadow);border:1px solid var(--border)}}
.stat-val{{font-size:32px;font-weight:600;letter-spacing:-1px;color:var(--accent)}}
.stat-lbl{{font-size:12px;color:var(--sec);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.stat-val.green{{color:var(--green)}}
.stat-val.orange{{color:var(--orange)}}
.panel{{background:var(--card);border-radius:20px;box-shadow:var(--shadow);border:1px solid var(--border);padding:28px;margin-bottom:20px}}
.panel h3{{font-size:18px;font-weight:600;margin-bottom:16px;letter-spacing:-.2px}}
.weather-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px}}
.weather-item{{text-align:center;padding:12px 8px;border-radius:12px;background:rgba(0,0,0,.02)}}
.weather-item .w-val{{font-size:20px;font-weight:600;color:var(--text)}}
.weather-item .w-lbl{{font-size:11px;color:var(--sec);margin-top:2px}}
.hbars{{display:flex;align-items:flex-end;gap:8px;height:120px;padding-top:4px}}
.hbar{{flex:1;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;position:relative}}
.hbar-fill{{width:100%;background:var(--accent);border-radius:6px 6px 0 0;min-height:2px;opacity:.75}}
.hbar-val{{font-size:11px;color:var(--sec);margin-bottom:4px}}
.hbar-label{{font-size:10px;color:var(--sec);margin-top:6px;position:absolute;bottom:-18px}}
.daily-row{{display:flex;gap:8px}}
.daily-item{{flex:1;text-align:center;padding:10px;border-radius:12px;background:rgba(0,0,0,.02)}}
.daily-num{{display:block;font-size:18px;font-weight:600}}
.daily-date{{display:block;font-size:11px;color:var(--sec);margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{text-align:left;padding:10px 12px;font-size:11px;color:var(--sec);text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border);font-weight:500}}
td{{padding:9px 12px;border-bottom:1px solid var(--border)}}
tr:last-child td{{border-bottom:none}}
.callsign{{font-weight:500}}
.coord{{font-size:12px;color:var(--sec);font-family:"SF Mono",monospace}}
.fade-in{{opacity:0;transform:translateY(24px);transition:opacity .6s ease,transform .6s ease}}
.fade-in.visible{{opacity:1;transform:translateY(0)}}
footer{{text-align:center;padding:32px;color:var(--sec);font-size:12px;border-top:1px solid var(--border);margin-top:40px}}
@media(max-width:768px){{nav{{padding:0 16px}}#map{{height:360px}}.content{{padding:0 16px}}.stats-row{{grid-template-columns:repeat(3,1fr);gap:8px}}}}
</style>
</head>
<body>
<div class="auth-overlay" id="auth">
  <div class="auth-box"><h2>SkyWatch</h2><p>藁城上空飞行追踪</p>
  <input type="password" id="pwd" placeholder="请输入密码" autofocus onkeydown="if(event.key==='Enter')unlock()">
  <div class="err" id="err">密码错误</div></div>
</div>
<nav><span class="logo">SkyWatch</span><span class="time">藁城 · {ts[:16] if ts else '—'}</span></nav>
<div id="map"></div>
<div class="content">
  <div class="stats-row fade-in">
    <div class="stat"><div class="stat-val">{len(planes)}</div><div class="stat-lbl">当前空域</div></div>
    <div class="stat"><div class="stat-val green">{total_today}</div><div class="stat-lbl">今日累计</div></div>
    <div class="stat"><div class="stat-val">{avg_alt:.0f}m</div><div class="stat-lbl">平均高度</div></div>
    <div class="stat"><div class="stat-val orange">{max_alt:.0f}m</div><div class="stat-lbl">最高飞行</div></div>
    <div class="stat"><div class="stat-val">{on_ground}</div><div class="stat-lbl">地面停靠</div></div>
  </div>
  <div class="panel fade-in"><h3>实时气象</h3>
    <div class="weather-grid">
      <div class="weather-item"><div class="w-val">{weather_desc}</div><div class="w-lbl">天气</div></div>
      <div class="weather-item"><div class="w-val">{temp}°C</div><div class="w-lbl">温度</div></div>
      <div class="weather-item"><div class="w-val">{humidity}%</div><div class="w-lbl">湿度</div></div>
      <div class="weather-item"><div class="w-val">{wind_speed} m/s</div><div class="w-lbl">风速</div></div>
      <div class="weather-item"><div class="w-val">{wind_dir}°</div><div class="w-lbl">风向</div></div>
      <div class="weather-item"><div class="w-val">{visibility} m</div><div class="w-lbl">能见度</div></div>
    </div>
  </div>
  <div class="panel fade-in"><h3>今日每小时观测量</h3>
    <div class="hbars">{bar_chart if bar_chart else '<p style="color:var(--sec);font-size:14px">数据采集中…</p>'}</div>
  </div>
  <div class="panel fade-in"><h3>近七日观测总量</h3>
    <div class="daily-row">{daily_items if daily_items else '<p style="color:var(--sec);font-size:14px">数据采集中…</p>'}</div>
  </div>
  <div class="panel fade-in"><h3>当前空域 ({len(planes)} 架)</h3>
    <div style="overflow-x:auto">
    <table>
    <tr><th>呼号</th><th>高度</th><th>速度</th><th>航向</th><th>状态</th><th>坐标</th></tr>
    {rows if rows else '<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--sec)">暂无数据</td></tr>'}
    </table></div>
  </div>
</div>
<footer>SkyWatch · 仅你可见 · 数据来源 OpenSky Network &amp; Open-Meteo</footer>
<script>
const HASH='{PASSWORD_HASH}';
async function unlock(){{const e=document.getElementById('pwd').value;const h=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(e));const x=Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,'0')).join('');if(x===HASH){{document.getElementById('auth').style.display='none';sessionStorage.setItem('skywatch_auth','1')}}else{{document.getElementById('err').style.display='block'}}}}
if(sessionStorage.getItem('skywatch_auth')==='1'){{document.getElementById('auth').style.display='none'}}
const map=L.map('map',{{attributionControl:false,zoomControl:false}}).setView([{CENTER_LAT},{CENTER_LNG}],11);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{attribution:'&copy; CartoDB',maxZoom:18}}).addTo(map);
L.control.zoom({{position:'bottomright'}}).addTo(map);
{markers_js}
const obs=new IntersectionObserver((e)=>{{e.forEach(en=>{{if(en.isIntersecting){{en.target.classList.add('visible');obs.unobserve(en.target)}}}})}},{{threshold:.15}});
document.querySelectorAll('.fade-in').forEach(el=>obs.observe(el));
</script>
</body>
</html>"""
    return html


def main():
    html = build()
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Generated docs/index.html ({len(html)} chars)")


if __name__ == "__main__":
    main()
