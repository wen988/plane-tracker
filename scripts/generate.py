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
    """加载最新数据，兼容旧 list 格式和新 dict 格式"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    if not files:
        return {}
    with open(files[0], encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, list):
        return {"planes": d, "weather": {}, "forecast": {"hourly": []}, "timestamp": ""}
    return d

def load_history():
    """加载历史数据（近7天），兼容两种格式"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)[:168]
    records = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            if isinstance(d, list):
                records.append({"planes": d, "weather": {}, "forecast": {"hourly": []}, "timestamp": ""})
            else:
                records.append(d)
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
            alt = p.get("altitude_baro", p.get("altitude", 0)) or 0
            if isinstance(alt, str):
                try: alt = float(alt)
                except: alt = 0
            spd = p.get("velocity", p.get("ground_speed", 0)) or 0
            if isinstance(spd, str):
                try: spd = float(spd)
                except: spd = 0
            cs = p.get("callsign", "").strip()
            air = p.get("airline", "").strip() or cs[:3] if cs else "?"
            fl = p.get("flight", "").strip().replace(" ", "")
            icao = p.get("icao24", "").strip()
            ong = p.get("on_ground", False)
            cat = p.get("category", "")
            plane_js.append({
                "lat": lat, "lon": lon, "alt": alt, "spd": spd,
                "callsign": cs, "airline": air, "flight": fl,
                "icao": icao, "on_ground": ong, "category": cat
            })

    # 气象信息
    wx = weather.get("current", {})
    wx_temp = wx.get("temperature_2m", "N/A")
    wx_hum = wx.get("relative_humidity_2m", "N/A")
    wx_wind = wx.get("wind_speed_10m", "N/A")
    wx_dir = wx.get("wind_direction_10m", "N/A")
    wx_code = wx.get("weather_code", -1)
    wx_desc = WEATHER_CN.get(wx_code, f"代码{wx_code}")

    # 预报
    fc = data.get("forecast", {})
    fc_hourly = fc.get("hourly", [])

    # 风向箭头
    def wind_arrow(deg):
        try:
            d = float(deg)
            dirs = ["↓北", "↙", "←西", "↖", "↑南", "↗", "→东", "↘"]
            return dirs[round(d / 45) % 8]
        except:
            return "?"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="referrer" content="no-referrer">
<title>藁城上空 - 飞机追踪</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#0f1923; color:#e0e0e0; }}
.header {{ background:linear-gradient(135deg, #1a3a4a, #0d2137); padding:16px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #2a5a7a; }}
.header h1 {{ font-size:20px; color:#7ec8f8; }}
.header .time {{ font-size:12px; color:#8899aa; }}
.stats {{ display:flex; gap:12px; padding:12px 24px; background:#132433; flex-wrap:wrap; }}
.stat-card {{ background:#1a3040; border-radius:8px; padding:10px 16px; min-width:100px; text-align:center; border:1px solid #2a4a60; }}
.stat-card .num {{ font-size:22px; font-weight:bold; color:#4fc3f7; }}
.stat-card .label {{ font-size:11px; color:#8899aa; margin-top:2px; }}
.map-container {{ height:420px; margin:8px; border-radius:8px; overflow:hidden; border:1px solid #2a4a60; }}
.charts {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:0 8px 8px; }}
.chart-box {{ background:#132433; border-radius:8px; padding:12px; border:1px solid #2a4a60; }}
.chart-box h3 {{ font-size:13px; color:#7ec8f8; margin-bottom:8px; }}
.chart-box canvas {{ width:100% !important; height:200px !important; }}
.plane-table {{ padding:8px; }}
.plane-table table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.plane-table th {{ background:#1a3040; color:#7ec8f8; padding:8px 6px; text-align:left; border-bottom:2px solid #2a5a7a; position:sticky; top:0; }}
.plane-table td {{ padding:6px; border-bottom:1px solid #1a3040; }}
.plane-table tr:hover {{ background:#1a3040; }}
.weather-bar {{ display:flex; align-items:center; gap:16px; padding:8px 24px; background:#132433; border-bottom:1px solid #2a4a60; flex-wrap:wrap; }}
.weather-item {{ font-size:13px; }}
.weather-item .val {{ color:#4fc3f7; font-weight:bold; }}
.forecast {{ padding:8px 24px; overflow-x:auto; }}
.forecast h3 {{ font-size:13px; color:#7ec8f8; margin-bottom:8px; }}
.forecast-table {{ width:100%; border-collapse:collapse; font-size:11px; }}
.forecast-table th {{ background:#1a3040; color:#7ec8f8; padding:6px; border-bottom:1px solid #2a4a60; }}
.forecast-table td {{ padding:4px 6px; border-bottom:1px solid #1a3040; text-align:center; }}
.badge {{ display:inline-block; padding:2px 6px; border-radius:4px; font-size:11px; }}
.badge-air {{ background:#1b5e20; color:#a5d6a7; }}
.badge-ground {{ background:#4a2800; color:#ffcc80; }}
.pw-overlay {{ display:flex; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:9999; justify-content:center; align-items:center; flex-direction:column; }}
.pw-box {{ background:#132433; padding:30px; border-radius:12px; border:1px solid #2a4a60; text-align:center; }}
.pw-box input {{ padding:10px 16px; border-radius:6px; border:1px solid #2a4a60; background:#0d2137; color:#fff; font-size:16px; margin:10px 0; width:200px; }}
.pw-box button {{ padding:10px 24px; border-radius:6px; border:none; background:#2a5a7a; color:#fff; cursor:pointer; font-size:14px; }}
.pw-box button:hover {{ background:#3a7aaa; }}
.pw-error {{ color:#ef5350; font-size:12px; margin-top:4px; }}
.hidden {{ display:none !important; }}
.wind-arrow {{ display:inline-block; margin-left:4px; }}
</style>
</head>
<body>
<div id="pw-overlay" class="pw-overlay">
<div class="pw-box">
<h2 style="color:#7ec8f8; margin-bottom:12px;">藁城上空</h2>
<p style="color:#8899aa; font-size:13px;">请输入访问密码</p>
<input type="password" id="pw-input" placeholder="密码" autofocus>
<button onclick="checkPw()">确认</button>
<p id="pw-error" class="pw-error"></p>
</div>
</div>

<div id="main-content" class="hidden">
<div class="header">
<h1>藁城上空 · 飞机追踪</h1>
<span class="time">数据时间: {ts}</span>
</div>

<div class="stats">
<div class="stat-card"><div class="num">{total}</div><div class="label">总飞机数</div></div>
<div class="stat-card"><div class="num">{in_air}</div><div class="label">空中</div></div>
<div class="stat-card"><div class="num">{on_ground}</div><div class="label">地面</div></div>
<div class="stat-card"><div class="num">{len(callsigns)}</div><div class="label">有呼号</div></div>
</div>

<div class="weather-bar">
<div class="weather-item">天气: <span class="val">{wx_desc}</span></div>
<div class="weather-item">温度: <span class="val">{wx_temp}°C</span></div>
<div class="weather-item">湿度: <span class="val">{wx_hum}%</span></div>
<div class="weather-item">风速: <span class="val">{wx_wind} m/s</span></div>
<div class="weather-item">风向: <span class="val">{wind_arrow(wx_dir)} {wx_dir}°</span></div>
</div>

<div class="map-container" id="map"></div>

<div class="charts">
<div class="chart-box">
<h3>每小时飞机数量趋势</h3>
<canvas id="chart-hourly"></canvas>
</div>
<div class="chart-box">
<h3>近7日每日飞机峰值</h3>
<canvas id="chart-daily"></canvas>
</div>
</div>

<div class="plane-table">
<table>
<thead><tr>
<th>呼号</th><th>航班</th><th>航司</th><th>ICAO24</th><th>纬度</th><th>经度</th><th>高度(m)</th><th>速度(m/s)</th><th>状态</th><th>类型</th>
</tr></thead>
<tbody>
"""

    for p in plane_js:
        status = "地面" if p["on_ground"] else "空中"
        badge_class = "badge-ground" if p["on_ground"] else "badge-air"
        html += f"""<tr>
<td>{p['callsign'] or '-'}</td>
<td>{p['flight'] or '-'}</td>
<td>{p['airline']}</td>
<td>{p['icao']}</td>
<td>{p['lat']:.4f}</td>
<td>{p['lon']:.4f}</td>
<td>{p['alt']:.0f}</td>
<td>{p['spd']:.0f}</td>
<td><span class="badge {badge_class}">{status}</span></td>
<td>{p['category'] or '-'}</td>
</tr>
"""

    html += """</tbody></table></div>
</div>

<script>
const PASSWORD_HASH = '""" + PASSWORD_HASH + """';

function sha256(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash |= 0;
    }
    return Math.abs(hash).toString(16).padStart(8, '0');
}

function checkPw() {
    const input = document.getElementById('pw-input').value;
    if (input === 'gaocheng') {
        document.getElementById('pw-overlay').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
        initMap();
        initCharts();
    } else {
        document.getElementById('pw-error').textContent = '密码错误，请重试';
    }
}

document.getElementById('pw-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') checkPw();
});

const planeData = """ + json.dumps(plane_js, ensure_ascii=False) + """;
const hourlyData = """ + json.dumps(hourly_sorted, ensure_ascii=False) + """;
const dailyData = """ + json.dumps(daily_sorted, ensure_ascii=False) + """;

function initMap() {
    const map = new AMap.Map('map', {
        center: [114.85, 38.04],
        zoom: 9,
        mapStyle: 'amap://styles/dark',
    });

    planeData.forEach(p => {
        const color = p.on_ground ? '#ff9800' : '#00e5ff';
        const marker = new AMap.Marker({
            position: [p.lon, p.lat],
            title: p.callsign || p.flight || 'N/A',
            icon: new AMap.Icon({
                size: new AMap.Size(20, 20),
                image: 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="6" fill="${color}" opacity="0.8"/><circle cx="10" cy="10" r="2" fill="white"/></svg>`),
            })
        });
        marker.setMap(map);

        if (!p.on_ground) {
            marker.on('click', function() {
                const content = `<div style="font-size:12px;padding:6px;background:#132433;color:#e0e0e0;border-radius:4px;border:1px solid #2a4a60;">
                    <b>${p.callsign || p.flight || 'N/A'}</b><br>
                    高度: ${p.alt.toFixed(0)}m / 速度: ${p.spd.toFixed(0)}m/s<br>
                    航司: ${p.airline} | ${p.flight || ''}
                </div>`;
                new AMap.InfoWindow({ content: content, offset: new AMap.Pixel(0, -20) }).open(map, marker.getPosition());
            });
        }
    });

    // 藁城标记
    new AMap.Marker({
        position: [114.85, 38.04],
        icon: new AMap.Icon({
            size: new AMap.Size(24, 24),
            image: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><circle cx="12" cy="12" r="8" fill="#ef5350" opacity="0.9"/><circle cx="12" cy="12" r="3" fill="white"/></svg>'),
        }),
        title: '藁城'
    }).setMap(map);
}

function initCharts() {
    // 每小时
    const hLabels = hourlyData.map(d => d[0] + ':00');
    const hValues = hourlyData.map(d => d[1]);
    new Chart(document.getElementById('chart-hourly'), {
        type: 'line',
        data: {
            labels: hLabels,
            datasets: [{
                label: '飞机数量',
                data: hValues,
                borderColor: '#4fc3f7',
                backgroundColor: 'rgba(79,195,247,0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#8899aa', font: { size: 11 } } } },
            scales: {
                x: { ticks: { color: '#8899aa', font: { size: 10 }, maxRotation: 45 }, grid: { color: '#1a3040' } },
                y: { ticks: { color: '#8899aa', font: { size: 10 } }, grid: { color: '#1a3040' } }
            }
        }
    });

    // 每日
    const dLabels = dailyData.map(d => d[0]);
    const dValues = dailyData.map(d => d[1]);
    new Chart(document.getElementById('chart-daily'), {
        type: 'bar',
        data: {
            labels: dLabels,
            datasets: [{
                label: '峰值',
                data: dValues,
                backgroundColor: 'rgba(79,195,247,0.4)',
                borderColor: '#4fc3f7',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#8899aa', font: { size: 11 } } } },
            scales: {
                x: { ticks: { color: '#8899aa', font: { size: 10 }, maxRotation: 45 }, grid: { color: '#1a3040' } },
                y: { ticks: { color: '#8899aa', font: { size: 10 } }, grid: { color: '#1a3040' } }
            }
        }
    });
}
</script>
<script src="https://webapi.amap.com/maps?v=2.0&key=你的高德Key"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</body>
</html>"""

    return html


def generate_weather_html(data, records):
    """气象仪表盘 - Chart.js"""
    ts = data.get("timestamp", "")
    weather = data.get("weather", {})
    hourly_data = data.get("forecast", {}).get("hourly", [])

    current = weather.get("current", {})
    temp = current.get("temperature_2m", "N/A")
    hum = current.get("relative_humidity_2m", "N/A")
    wind = current.get("wind_speed_10m", "N/A")
    wdir = current.get("wind_direction_10m", "N/A")
    wx_code = current.get("weather_code", -1)
    wx_desc = WEATHER_CN.get(wx_code, f"代码{wx_code}")

    # 48小时温度
    temp_labels = [h.get("time", "")[-5:] for h in hourly_data[:48]]
    temp_vals = [h.get("temperature_2m", 0) for h in hourly_data[:48]]

    # 湿度
    hum_vals = [h.get("relative_humidity_2m", 0) for h in hourly_data[:48]]

    # 风速
    wind_vals = [h.get("wind_speed_10m", 0) for h in hourly_data[:48]]

    # 降水概率
    precip_vals = [h.get("precipitation_probability", 0) or 0 for h in hourly_data[:48]]

    # 云量
    cloud_vals = [h.get("cloud_cover", 0) or 0 for h in hourly_data[:48]]

    # 近7日温度范围
    daily_temps = {}
    for r in records:
        d = r.get("timestamp", "")[:10]
        wx_daily = r.get("weather", {}).get("current", {})
        t = wx_daily.get("temperature_2m")
        if d and t is not None:
            daily_temps.setdefault(d, []).append(t)
    daily_labels = sorted(daily_temps.keys())[-7:]
    daily_max = [max(daily_temps.get(d, [0])) for d in daily_labels]
    daily_min = [min(daily_temps.get(d, [0])) for d in daily_labels]

    def wind_arrow(deg):
        try:
            d = float(deg)
            dirs = ["↓北", "↙", "←西", "↖", "↑南", "↗", "→东", "↘"]
            return dirs[round(d / 45) % 8]
        except:
            return "?"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="referrer" content="no-referrer">
<title>藁城气象仪表盘</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#0f1923; color:#e0e0e0; }}
.header {{ background:linear-gradient(135deg, #1a3a4a, #0d2137); padding:16px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #2a5a7a; }}
.header h1 {{ font-size:20px; color:#7ec8f8; }}
.header .time {{ font-size:12px; color:#8899aa; }}
.current {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; padding:16px 24px; }}
.cur-card {{ background:#132433; border-radius:8px; padding:12px; text-align:center; border:1px solid #2a4a60; }}
.cur-card .val {{ font-size:24px; font-weight:bold; color:#4fc3f7; }}
.cur-card .label {{ font-size:11px; color:#8899aa; margin-top:4px; }}
.charts {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:0 24px 24px; }}
.chart-box {{ background:#132433; border-radius:8px; padding:12px; border:1px solid #2a4a60; }}
.chart-box h3 {{ font-size:13px; color:#7ec8f8; margin-bottom:8px; }}
.chart-box canvas {{ width:100% !important; height:220px !important; }}
@media (max-width:768px) {{ .current {{ grid-template-columns:repeat(3,1fr); }} .charts {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="header">
<h1>藁城 · 气象仪表盘</h1>
<span class="time">数据时间: {ts}</span>
</div>

<div class="current">
<div class="cur-card"><div class="val">{wx_desc}</div><div class="label">天气状况</div></div>
<div class="cur-card"><div class="val">{temp}°C</div><div class="label">气温</div></div>
<div class="cur-card"><div class="val">{hum}%</div><div class="label">相对湿度</div></div>
<div class="cur-card"><div class="val">{wind} m/s {wind_arrow(wdir)}</div><div class="label">风速/风向</div></div>
<div class="cur-card"><div class="val">{len(hourly_data)}条</div><div class="label">预报数据</div></div>
</div>

<div class="charts">
<div class="chart-box">
<h3>48小时温度变化</h3>
<canvas id="chart-temp"></canvas>
</div>
<div class="chart-box">
<h3>48小时湿度变化</h3>
<canvas id="chart-hum"></canvas>
</div>
<div class="chart-box">
<h3>48小时风速</h3>
<canvas id="chart-wind"></canvas>
</div>
<div class="chart-box">
<h3>48小时降水概率</h3>
<canvas id="chart-precip"></canvas>
</div>
<div class="chart-box">
<h3>48小时云量</h3>
<canvas id="chart-cloud"></canvas>
</div>
<div class="chart-box">
<h3>近7日温度范围</h3>
<canvas id="chart-range"></canvas>
</div>
</div>

<script>
const tempLabels = """ + json.dumps(temp_labels, ensure_ascii=False) + """;
const tempVals = """ + json.dumps(temp_vals, ensure_ascii=False) + """;
const humVals = """ + json.dumps(hum_vals, ensure_ascii=False) + """;
const windVals = """ + json.dumps(wind_vals, ensure_ascii=False) + """;
const precipVals = """ + json.dumps(precip_vals, ensure_ascii=False) + """;
const cloudVals = """ + json.dumps(cloud_vals, ensure_ascii=False) + """;
const dailyLabels = """ + json.dumps(daily_labels, ensure_ascii=False) + """;
const dailyMax = """ + json.dumps(daily_max, ensure_ascii=False) + """;
const dailyMin = """ + json.dumps(daily_min, ensure_ascii=False) + """;

const chartOpts = {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#8899aa', font: {{ size: 10 }} }} }} }},
    scales: {{
        x: {{ ticks: {{ color: '#8899aa', font: {{ size: 9 }}, maxRotation: 45, maxTicksLimit: 12 }}, grid: {{ color: '#1a3040' }} }},
        y: {{ ticks: {{ color: '#8899aa', font: {{ size: 9 }} }}, grid: {{ color: '#1a3040' }} }}
    }}
}};

new Chart(document.getElementById('chart-temp'), {{
    type: 'line', data: {{ labels: tempLabels, datasets: [{{ label: '温度(°C)', data: tempVals, borderColor: '#ef5350', backgroundColor: 'rgba(239,83,80,0.1)', fill: true, tension: 0.3 }}] }}, options: chartOpts
}});
new Chart(document.getElementById('chart-hum'), {{
    type: 'line', data: {{ labels: tempLabels, datasets: [{{ label: '湿度(%)', data: humVals, borderColor: '#42a5f5', backgroundColor: 'rgba(66,165,245,0.1)', fill: true, tension: 0.3 }}] }}, options: chartOpts
}});
new Chart(document.getElementById('chart-wind'), {{
    type: 'bar', data: {{ labels: tempLabels, datasets: [{{ label: '风速(m/s)', data: windVals, backgroundColor: 'rgba(129,212,250,0.4)', borderColor: '#81d4fa', borderWidth: 1 }}] }}, options: chartOpts
}});
new Chart(document.getElementById('chart-precip'), {{
    type: 'bar', data: {{ labels: tempLabels, datasets: [{{ label: '降水概率(%)', data: precipVals, backgroundColor: 'rgba(79,195,247,0.3)', borderColor: '#4fc3f7', borderWidth: 1 }}] }}, options: chartOpts
}});
new Chart(document.getElementById('chart-cloud'), {{
    type: 'line', data: {{ labels: tempLabels, datasets: [{{ label: '云量(%)', data: cloudVals, borderColor: '#b0bec5', backgroundColor: 'rgba(176,190,197,0.1)', fill: true, tension: 0.3 }}] }}, options: chartOpts
}});
new Chart(document.getElementById('chart-range'), {{
    type: 'bar', data: {{
        labels: dailyLabels,
        datasets: [
            {{ label: '最高(°C)', data: dailyMax, backgroundColor: 'rgba(239,83,80,0.5)', borderColor: '#ef5350', borderWidth: 1 }},
            {{ label: '最低(°C)', data: dailyMin, backgroundColor: 'rgba(66,165,245,0.5)', borderColor: '#42a5f5', borderWidth: 1 }}
        ]
    }}, options: chartOpts
}});
</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</body>
</html>"""

    return html


def main():
    data = load_latest()
    records = load_history()

    os.makedirs(DOCS_DIR, exist_ok=True)

    index_html = generate_index_html(data, records)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    weather_html = generate_weather_html(data, records)
    with open(os.path.join(DOCS_DIR, "weather.html"), "w", encoding="utf-8") as f:
        f.write(weather_html)

    print(f"Generated {len(index_html)} bytes -> docs/index.html")
    print(f"Generated {len(weather_html)} bytes -> docs/weather.html")

if __name__ == "__main__":
    main()
