#!/usr/bin/env python3
"""生成藁城上空飞机追踪面板 + 气象仪表盘"""

import json, os, glob, hashlib, datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
PASSWORD_HASH = hashlib.sha256("gaocheng".encode()).hexdigest()

WEATHER_CN = {
    0: "☀️ 晴", 1: "🌤 少云", 2: "⛅ 多云", 3: "☁️ 阴",
    45: "🌫 雾", 48: "🌫 雾凇",
    51: "🌦 小毛毛雨", 53: "🌦 中毛毛雨", 55: "🌦 大毛毛雨",
    61: "🌧 小雨", 63: "🌧 中雨", 65: "🌧 大雨",
    71: "❄️ 小雪", 73: "❄️ 中雪", 75: "❄️ 大雪",
    80: "🌦 阵雨", 81: "🌦 中阵雨", 82: "🌦 大阵雨",
    95: "⛈ 雷暴", 96: "⛈ 冰雹雷暴", 99: "⛈ 大冰雹雷暴"
}

def load_latest():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    return json.load(open(files[0], encoding="utf-8")) if files else {}

def load_history():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)[:168]
    records = []
    for f in files:
        try:
            records.append(json.load(open(f, encoding="utf-8")))
        except:
            pass
    return records

def generate_index_html(data, records):
    """飞机追踪面板 - 高德地图 + 中文"""
    planes = data.get("planes", [])
    weather = data.get("weather", {})
    ts = data.get("timestamp", "")

    # 统计数据
    total = len(planes)
    on_ground = sum(1 for p in planes if p.get("on_ground"))
    in_air = total - on_ground
    callsigns = [p for p in planes if p.get("callsign", "").strip()]

    # 每小时统计
    hourly = {}
    for r in records:
        t = r.get("timestamp", "")
        if t:
            hour = t[11:13]
            hourly[hour] = hourly.get(hour, 0) + len(r.get("planes", []))
    hourly_sorted = sorted(hourly.items())

    # 近7日
    daily = {}
    for r in records:
        d = r.get("timestamp", "")[:10]
        daily[d] = max(daily.get(d, 0), len(r.get("planes", [])))
    daily_sorted = sorted(daily.items())[-7:]

    # 飞机标记 JS
    plane_js = []
    for p in planes:
        lat = p.get("latitude")
        lon = p.get("longitude")
        if lat and lon:
            callsign = p.get("callsign", "").strip() or "无呼号"
            alt = p.get("baro_altitude") or p.get("geo_altitude") or 0
            heading = p.get("true_track") or 0
            vel = p.get("velocity") or 0
            plane_js.append({
                "lat": lat, "lon": lon, "callsign": callsign,
                "alt": alt, "heading": heading, "vel": vel
            })

    planes_json = json.dumps(plane_js, ensure_ascii=False)
    hourly_json = json.dumps(hourly_sorted)
    daily_json = json.dumps(daily_sorted)
    temp = weather.get("temperature", "--")
    wind_speed = weather.get("wind_speed", "--")
    wind_dir = weather.get("wind_direction", "--")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>藁城上空 · 飞机追踪</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0}}
.lock-overlay{{position:fixed;inset:0;background:rgba(15,23,42,0.97);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column}}
.lock-overlay input{{padding:12px 20px;border-radius:12px;border:2px solid #334155;background:#1e293b;color:#e2e8f0;font-size:16px;width:260px;text-align:center;outline:none}}
.lock-overlay input:focus{{border-color:#38bdf8}}
.lock-overlay button{{margin-top:12px;padding:10px 32px;border-radius:12px;border:none;background:#38bdf8;color:#0f172a;font-size:15px;font-weight:600;cursor:pointer}}
.lock-error{{color:#f87171;font-size:13px;margin-top:8px;display:none}}
nav{{display:flex;gap:0;background:#1e293b;padding:0 20px;border-bottom:1px solid #334155}}
nav a{{padding:14px 24px;color:#94a3b8;text-decoration:none;font-size:14px;font-weight:500;border-bottom:2px solid transparent}}
nav a:hover{{color:#e2e8f0}}
nav a.active{{color:#38bdf8;border-bottom-color:#38bdf8}}
.container{{max-width:1400px;margin:0 auto;padding:20px}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.header h1{{font-size:24px;font-weight:700}}
.header span{{font-size:13px;color:#64748b}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.stat-card{{background:#1e293b;border-radius:14px;padding:18px;border:1px solid #334155}}
.stat-card .num{{font-size:32px;font-weight:700;color:#38bdf8}}
.stat-card .label{{font-size:13px;color:#64748b;margin-top:4px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.chart-card{{background:#1e293b;border-radius:14px;padding:16px;border:1px solid #334155}}
.chart-card h3{{font-size:14px;color:#94a3b8;margin-bottom:12px}}
.chart-bar{{display:flex;align-items:flex-end;gap:3px;height:100px}}
.chart-bar .bar{{flex:1;background:#38bdf8;border-radius:3px 3px 0 0;min-height:2px;position:relative}}
.chart-bar .bar:hover{{background:#7dd3fc}}
.chart-bar .bar .tip{{display:none;position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;font-size:11px;padding:3px 8px;border-radius:4px;white-space:nowrap}}
.chart-bar .bar:hover .tip{{display:block}}
.chart-labels{{display:flex;gap:3px;margin-top:6px}}
.chart-labels span{{flex:1;font-size:10px;color:#64748b;text-align:center;overflow:hidden}}
#map{{height:450px;border-radius:14px;border:1px solid #334155;margin-bottom:20px}}
.plane-table{{width:100%;border-collapse:collapse;font-size:13px}}
.plane-table th{{text-align:left;padding:10px 12px;color:#94a3b8;font-weight:500;border-bottom:1px solid #334155}}
.plane-table td{{padding:10px 12px;border-bottom:1px solid #1e293b}}
.plane-table tr:hover td{{background:#1e293b}}
.plane-table .callsign{{color:#38bdf8;font-weight:500}}
.plane-table .noid{{color:#64748b;font-style:italic}}
</style>
</head>
<body>
<div class="lock-overlay" id="lock">
  <div style="font-size:48px;margin-bottom:12px">✈️</div>
  <div style="font-size:16px;color:#94a3b8;margin-bottom:16px">藁城上空飞机追踪</div>
  <input type="password" id="pwd" placeholder="请输入密码" onkeydown="if(event.key==='Enter')unlock()">
  <button onclick="unlock()">解锁</button>
  <div class="lock-error" id="err">密码错误</div>
</div>
<nav>
  <a class="active" href="index.html">✈️ 飞机追踪</a>
  <a href="weather.html">🌤 气象仪表盘</a>
</nav>
<div class="container">
  <div class="header">
    <h1>🛰 藁城上空实时飞机追踪</h1>
    <span>更新于 {ts}</span>
  </div>
  <div class="stats">
    <div class="stat-card"><div class="num">{total}</div><div class="label">当前追踪飞机</div></div>
    <div class="stat-card"><div class="num">{in_air}</div><div class="label">空中飞行</div></div>
    <div class="stat-card"><div class="num">{on_ground}</div><div class="label">地面停放</div></div>
    <div class="stat-card"><div class="num">{len(callsigns)}</div><div class="label">有呼号飞机</div></div>
  </div>
  <div id="map"></div>
  <div class="charts">
    <div class="chart-card">
      <h3>📊 过去各小时飞机总量</h3>
      <div class="chart-bar" id="hourlyBars"></div>
      <div class="chart-labels" id="hourlyLabels"></div>
    </div>
    <div class="chart-card">
      <h3>📈 近7日每日峰值</h3>
      <div class="chart-bar" id="dailyBars"></div>
      <div class="chart-labels" id="dailyLabels"></div>
    </div>
  </div>
  <div class="chart-card" style="margin-bottom:20px">
    <h3>📋 飞机列表</h3>
    <table class="plane-table"><thead><tr><th>呼号</th><th>ICAO24</th><th>高度(m)</th><th>速度(m/s)</th><th>航向</th><th>状态</th></tr></thead>
    <tbody>'''
    for p in planes:
        cs = p.get("callsign", "").strip() or '<span class="noid">无呼号</span>'
        icao = p.get("icao24", "--")
        alt = (p.get("baro_altitude") or p.get("geo_altitude") or 0)
        vel = p.get("velocity") or 0
        hdg = p.get("true_track") or 0
        og = "地面" if p.get("on_ground") else "空中"
        html += f'<tr><td class="callsign">{cs}</td><td>{icao}</td><td>{alt:.0f}</td><td>{vel:.0f}</td><td>{hdg:.0f}°</td><td>{og}</td></tr>'
    html += '''</tbody></table></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
function unlock(){
  const raw=document.getElementById("pwd").value;
  const encoder=new TextEncoder();
  crypto.subtle.digest("SHA-256",encoder.encode(raw)).then(h=>{
    const hash=Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,"0")).join("");
    if(hash==="''' + PASSWORD_HASH + '''"){document.getElementById("lock").style.display="none"}
    else{document.getElementById("err").style.display="block"}
  });
}
const map=L.map("map").setView([37.94,114.84],11);
L.tileLayer("https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",{
  subdomains:"1234",attribution:"&copy; 高德地图",maxZoom:18
}).addTo(map);
const planes=''' + planes_json + ''';
planes.forEach(p=>{
  const icon=L.divIcon({html:'<div style="font-size:20px;transform:rotate('+p.heading+'deg)">✈️</div>',className:"",iconSize:[24,24],iconAnchor:[12,12]});
  L.marker([p.lat,p.lon],{icon}).addTo(map).bindPopup("<b>"+p.callsign+"</b><br>高度:"+p.alt.toFixed(0)+"m<br>速度:"+p.vel.toFixed(0)+"m/s");
});

// 每小时柱状图
const hourly=''' + hourly_json + ''';
const hBars=document.getElementById("hourlyBars");
const hLabels=document.getElementById("hourlyLabels");
const hMax=Math.max(...hourly.map(h=>h[1]),1);
hourly.forEach(h=>{
  const bar=document.createElement("div");bar.className="bar";
  bar.style.height=(h[1]/hMax*100)+"%";
  bar.innerHTML='<span class="tip">'+h[0]+"时: "+h[1]+"架</span>";
  hBars.appendChild(bar);
  const lbl=document.createElement("span");lbl.textContent=h[0];
  hLabels.appendChild(lbl);
});

// 每日柱状图
const daily=''' + daily_json + ''';
const dBars=document.getElementById("dailyBars");
const dLabels=document.getElementById("dailyLabels");
const dMax=Math.max(...daily.map(d=>d[1]),1);
daily.forEach(d=>{
  const bar=document.createElement("div");bar.className="bar";
  bar.style.height=(d[1]/dMax*100)+"%";
  bar.innerHTML='<span class="tip">'+d[0]+": "+d[1]+"架</span>";
  dBars.appendChild(bar);
  const lbl=document.createElement("span");lbl.textContent=d[0].slice(5);
  dLabels.appendChild(lbl);
});
</script>
</body></html>'''

    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated index.html")

def generate_weather_html(data):
    """气象仪表盘 - Chart.js"""
    forecast = data.get("forecast", {}).get("hourly", [])
    weather = data.get("weather", {})
    ts = data.get("timestamp", "")

    if not forecast:
        forecast_html = '<div style="text-align:center;color:#64748b;padding:40px">暂无预报数据</div>'
        chart_data = '{"labels":[],"temp":[],"humid":[],"precip":[],"wind":[],"wdir":[],"vis":[]}'
    else:
        times = [f["time"][-8:-3] for f in forecast]
        temp = [f["temperature"] for f in forecast]
        humid = [f["humidity"] for f in forecast]
        precip = [f["precip_prob"] for f in forecast]
        wind = [f["wind_speed"] for f in forecast]
        wdir = [f["wind_direction"] for f in forecast]
        vis = [f["visibility"] for f in forecast]

        # 当前天气
        w_code = weather.get("weather_code", 0)
        w_text = WEATHER_CN.get(w_code, "未知")
        temp_now = weather.get("temperature", "--")
        humid_now = weather.get("relative_humidity", "--")
        wind_now = weather.get("wind_speed", "--")
        wdir_now = weather.get("wind_direction", "--")
        vis_now = weather.get("visibility", "--")

        forecast_html = ""
        chart_data = json.dumps({
            "labels": times, "temp": temp, "humid": humid,
            "precip": precip, "wind": wind, "wdir": wdir, "vis": vis
        }, ensure_ascii=False)

    current_html = f'''
    <div class="stats" style="grid-template-columns:repeat(5,1fr)">
      <div class="stat-card"><div class="num">{w_text}</div><div class="label">当前天气</div></div>
      <div class="stat-card"><div class="num">{temp_now}°C</div><div class="label">温度</div></div>
      <div class="stat-card"><div class="num">{humid_now}%</div><div class="label">湿度</div></div>
      <div class="stat-card"><div class="num">{wind_now} m/s</div><div class="label">风速 · {wdir_now}°</div></div>
      <div class="stat-card"><div class="num">{vis_now} m</div><div class="label">能见度</div></div>
    </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>藁城 · 气象仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0}}
nav{{display:flex;gap:0;background:#1e293b;padding:0 20px;border-bottom:1px solid #334155}}
nav a{{padding:14px 24px;color:#94a3b8;text-decoration:none;font-size:14px;font-weight:500;border-bottom:2px solid transparent}}
nav a:hover{{color:#e2e8f0}}
nav a.active{{color:#38bdf8;border-bottom-color:#38bdf8}}
.container{{max-width:1400px;margin:0 auto;padding:20px}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.header h1{{font-size:24px;font-weight:700}}
.header span{{font-size:13px;color:#64748b}}
.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}}
.stat-card{{background:#1e293b;border-radius:14px;padding:18px;border:1px solid #334155}}
.stat-card .num{{font-size:28px;font-weight:700;color:#38bdf8}}
.stat-card .label{{font-size:13px;color:#64748b;margin-top:4px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.chart-card{{background:#1e293b;border-radius:14px;padding:16px;border:1px solid #334155}}
.chart-card h3{{font-size:14px;color:#94a3b8;margin-bottom:12px}}
.chart-card canvas{{max-height:250px}}
.chart-full{{grid-column:1/-1}}
.chart-full canvas{{max-height:280px}}
.wind-table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}}
.wind-table th{{text-align:left;padding:8px 12px;color:#94a3b8;font-weight:500;border-bottom:1px solid #334155}}
.wind-table td{{padding:8px 12px;border-bottom:1px solid #1e293b}}
.wind-table tr:hover td{{background:#1e293b}}
.wind-arrow{{display:inline-block;font-size:16px;transition:transform 0.3s}}
</style>
</head>
<body>
<nav>
  <a href="index.html">✈️ 飞机追踪</a>
  <a class="active" href="weather.html">🌤 气象仪表盘</a>
</nav>
<div class="container">
  <div class="header">
    <h1>🌤 藁城气象仪表盘</h1>
    <span>更新于 {ts}</span>
  </div>
  {current_html}
  <div class="charts">
    <div class="chart-card"><h3>🌡 24小时温度趋势</h3><canvas id="tempChart"></canvas></div>
    <div class="chart-card"><h3>💧 24小时湿度趋势</h3><canvas id="humidChart"></canvas></div>
    <div class="chart-card"><h3>🌧 24小时降水概率</h3><canvas id="precipChart"></canvas></div>
    <div class="chart-card"><h3>👁 24小时能见度</h3><canvas id="visChart"></canvas></div>
    <div class="chart-card"><h3>💨 24小时风速趋势</h3><canvas id="windChart"></canvas></div>
    <div class="chart-card">
      <h3>🧭 24小时风向风速详情</h3>
      <table class="wind-table"><thead><tr><th>时间</th><th>风向(°)</th><th>风速(m/s)</th><th>风况</th></tr></thead><tbody id="windBody"></tbody></table>
    </div>
  </div>
</div>
<script>
const data = {chart_data};

const commonOpts = {{
  responsive: true,
  maintainAspectRatio: false,
  plugins: {{ legend: {{ display: false }} }},
  scales: {{
    x: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, maxTicksLimit: 12 }}, grid: {{ color: "#1e293b" }} }},
    y: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }} }}, grid: {{ color: "#1e293b" }} }}
  }}
}};

function makeLine(id, values, color, label, unit) {{
  new Chart(document.getElementById(id), {{
    type: "line",
    data: {{ labels: data.labels, datasets: [{{ data: values, borderColor: color, backgroundColor: color+"22", fill: true, tension: 0.4, pointRadius: 2 }}] }},
    options: commonOpts
  }});
}}

function makeBar(id, values, color) {{
  new Chart(document.getElementById(id), {{
    type: "bar",
    data: {{ labels: data.labels, datasets: [{{ data: values, backgroundColor: values.map(v => v>50 ? "#ef4444" : v>20 ? "#f59e0b" : "#38bdf8"), borderRadius: 4 }}] }},
    options: commonOpts
  }});
}}

if(data.labels.length) {{
  makeLine("tempChart", data.temp, "#38bdf8", "温度", "°C");
  makeLine("humidChart", data.humid, "#a78bfa", "湿度", "%");
  makeBar("precipChart", data.precip, "#ef4444");
  makeLine("visChart", data.vis, "#34d399", "能见度", "m");
  makeLine("windChart", data.wind, "#f97316", "风速", "m/s");

  const wbody = document.getElementById("windBody");
  data.labels.forEach((t,i) => {{
    const ws = data.wind[i] ?? "-";
    const wd = data.wdir[i] ?? "-";
    const desc = ws > 10 ? "强风" : ws > 5 ? "和风" : ws > 1 ? "微风" : "静风";
    wbody.innerHTML += `<tr><td>${{t}}</td><td>${{wd}}°</td><td>${{ws}}</td><td>${{desc}}</td></tr>`;
  }});
}}
</script>
</body></html>'''

    with open(os.path.join(DOCS_DIR, "weather.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated weather.html")

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    data = load_latest()
    records = load_history()
    generate_index_html(data, records)
    generate_weather_html(data)
    print("Done.")

if __name__ == "__main__":
    main()
