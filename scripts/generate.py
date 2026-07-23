#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""藁城上空 - 飞机追踪 + 气象仪表盘"""
import json, os, glob, hashlib, datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
PW_HASH = hashlib.sha256("gaocheng".encode()).hexdigest()

WX_CN = {0:"晴",1:"少云",2:"多云",3:"阴",45:"雾",48:"雾凇",51:"小毛毛雨",53:"中毛毛雨",55:"大毛毛雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",80:"阵雨",81:"中阵雨",82:"大阵雨",95:"雷暴",96:"冰雹雷暴",99:"大冰雹雷暴"}

def fmt_time(ts):
    """Convert ISO timestamp to Chinese readable format"""
    try:
        dt = datetime.datetime.fromisoformat(ts.replace("Z","+00:00").split("+")[0])
        return dt.strftime("%m月%d日 %H:%M")
    except:
        return ts

def load_latest():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    if not files: return {}
    with open(files[0], encoding="utf-8") as f:
        d = json.load(f)
    records = d if isinstance(d, list) else [d]
    if not records: return {}
    r = records[-1]
    return {
        "planes": r.get("planes", []),
        "weather": r["weather"]["current"] if "weather" in r and "current" in r["weather"] else {},
        "forecast": r["forecast"]["hourly"] if "forecast" in r and "hourly" in r["forecast"] else [],
        "timestamp": r.get("timestamp", "")
    }

def load_history():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)[:168]
    recs = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            records = d if isinstance(d, list) else [d]
            for r in records:
                recs.append({
                    "planes": r.get("planes", []),
                    "weather": r.get("weather", {}),
                    "forecast": r.get("forecast", {}),
                    "timestamp": r.get("timestamp", "")
                })
        except:
            pass
    return recs

def make_index(data, records):
    planes = data.get("planes", [])
    ts = data.get("timestamp", "")
    weather = data.get("weather", {})
    if isinstance(weather, dict) and "current" in weather:
        wc = weather["current"]
    else:
        wc = weather if isinstance(weather, dict) else {}
    wx_temp = wc.get("temperature_2m", "--")
    wx_hum = wc.get("relative_humidity_2m", "--")
    wx_wind = wc.get("wind_speed_10m", "--")
    wx_code = wc.get("weather_code", -1)
    wx_text = WX_CN.get(wx_code, "--")

    total = len(planes)
    on_ground = sum(1 for p in planes if p.get("on_ground"))
    in_air = total - on_ground
    cs_count = sum(1 for p in planes if p.get("callsign","").strip())

    hourly = {}
    for r in records:
        t = r.get("timestamp","")
        if t: hourly[t[11:13]] = hourly.get(t[11:13],0) + len(r.get("planes",[]))
    hs = sorted(hourly.items())
    hmax = max([v for _,v in hs], default=1) or 1

    daily = {}
    for r in records:
        d = r.get("timestamp","")[:10]
        daily[d] = max(daily.get(d,0), len(r.get("planes",[])))
    ds = sorted(daily.items())[-7:]
    dmax = max([v for _,v in ds], default=1) or 1

    # plane markers JS
    pjs = []
    for p in planes:
        lat, lon = p.get("latitude"), p.get("longitude")
        if not lat or not lon: continue
        alt = p.get("altitude") or 0
        geo = p.get("geo_altitude") or 0
        vel = p.get("velocity") or 0
        trk = p.get("track") or 0
        vrate = p.get("vertical_rate") or 0
        sq = p.get("squawk") or None
        cs = p.get("callsign","").strip() or "N/A"
        icao = p.get("icao24","").strip()
        og = p.get("on_ground", False)
        country = p.get("origin_country","").strip() or "-"
        pjs.append({"lat":lat,"lon":lon,"alt":alt,"geo":geo,"vel":vel,"trk":trk,"vrate":vrate,"sq":sq,"cs":cs,"icao":icao,"og":og,"country":country})

    # table rows
    rows = ""
    for p in planes:
        cs = p.get("callsign","").strip() or "-"
        icao = p.get("icao24","").strip()
        alt = p.get("altitude") or 0
        geo = p.get("geo_altitude") or alt or 0
        vel = p.get("velocity") or 0
        trk = p.get("track") or 0
        vrate = p.get("vertical_rate")
        vrate_str = f"{vrate:.1f}" if vrate is not None else "-"
        sq = p.get("squawk") or "-"
        country = p.get("origin_country","").strip() or "-"
        og = "地面" if p.get("on_ground") else "空中"
        rows += f'<tr><td>{cs}</td><td>{icao}</td><td>{country}</td><td>{alt:.0f}</td><td>{geo:.0f}</td><td>{vel:.0f}</td><td>{trk:.0f}°</td><td>{vrate_str}</td><td>{sq}</td><td>{og}</td></tr>'

    # hourly bars
    hbars, hlabels = "", ""
    for h, v in hs:
        pct = v/hmax*100
        hbars += f'<div class="bar" style="height:{pct}%"><span class="tip">{h}时 {v}架</span></div>'
        hlabels += f"<span>{h}</span>"
    # daily bars
    dbars, dlabels = "", ""
    for d, v in ds:
        pct = v/dmax*100
        dbars += f'<div class="bar" style="height:{pct}%"><span class="tip">{d}: {v}架</span></div>'
        dlabels += f"<span>{d[5:]}</span>"

    html = f'''<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><meta name="robots" content="noindex">
<title>藁城上空 · 飞机追踪 | 单反的雷达站 v2</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f7;color:#1d1d1f}}
.lock{{position:fixed;inset:0;background:rgba(245,245,247,.97);z-index:999;display:flex;flex-direction:column;align-items:center;justify-content:center;backdrop-filter:blur(20px)}}
.lock input{{padding:12px 20px;border-radius:12px;border:1.5px solid #d2d2d7;background:#fff;font-size:16px;width:260px;text-align:center;outline:none}}
.lock input:focus{{border-color:#0071e3}}
.lock button{{margin-top:10px;padding:10px 36px;border-radius:20px;border:none;background:#0071e3;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
.lock .err{{color:#ff3b30;font-size:13px;margin-top:8px;display:none}}
nav{{display:flex;background:rgba(255,255,255,.8);backdrop-filter:blur(20px);padding:12px 24px;border-bottom:1px solid #d2d2d7;position:sticky;top:0;z-index:100}}
nav a{{padding:8px 20px;border-radius:8px;color:#86868b;text-decoration:none;font-size:14px;font-weight:500;margin-right:4px}}
nav a:hover{{background:rgba(0,0,0,.04);color:#1d1d1f}}
nav a.on{{background:#0071e3;color:#fff}}
.container{{max-width:1200px;margin:0 auto;padding:24px}}
.header{{margin-bottom:20px}}
.header h1{{font-size:28px;font-weight:700}}
.header .ts{{font-size:13px;color:#86868b;margin-top:4px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.card .num{{font-size:36px;font-weight:700;color:#0071e3}}
.card .lbl{{font-size:13px;color:#86868b;margin-top:4px}}
.wxbar{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px;padding:16px 20px;background:#fff;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.wxbar span{{font-size:14px;color:#1d1d1f}}
.wxbar b{{color:#0071e3}}
#map{{height:420px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,.06);margin-bottom:20px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.chart-box{{background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.chart-box h3{{font-size:15px;font-weight:600;margin-bottom:16px;color:#1d1d1f}}
.bars{{display:flex;align-items:flex-end;gap:2px;height:100px}}
.bars .bar{{flex:1;background:#0071e3;border-radius:3px 3px 0 0;min-height:2px;position:relative}}
.bars .bar:hover{{background:#2997ff}}
.bars .bar .tip{{display:none;position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:#1d1d1f;color:#fff;font-size:11px;padding:4px 8px;border-radius:4px;white-space:nowrap}}
.bars .bar:hover .tip{{display:block}}
.bar-labels{{display:flex;gap:2px;margin-top:6px}}
.bar-labels span{{flex:1;font-size:10px;color:#86868b;text-align:center;overflow:hidden}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:10px 12px;color:#86868b;font-weight:500;border-bottom:1px solid #e5e5ea}}
td{{padding:10px 12px;border-bottom:1px solid #f5f5f7}}
tr:hover td{{background:#f5f5f7}}
</style></head><body>
<div class="lock" id="lock"><div style="font-size:40px;margin-bottom:8px">🛰</div>
<div style="font-size:15px;color:#86868b;margin-bottom:16px">藁城上空飞机追踪</div>
<input type="password" id="pw" placeholder="输入密码" onkeydown="if(event.key==='Enter')unlock()">
<button onclick="unlock()">解锁</button><div class="err" id="err">密码错误</div></div>
<nav><a class="on" href="index.html">飞机追踪</a><a href="weather.html">气象仪表盘</a><a href="3d.html">3D地球</a><a href="replay.html">历史回放</a><a href="space.html">太空过境</a><a href="dashboard.html">数据大屏</a></nav>
<div class="container">
<div class="header"><h1>藁城上空飞机追踪</h1><div class="ts">更新于 {fmt_time(ts)}</div></div>
<div class="stats"><div class="card"><div class="num">{total}</div><div class="lbl">追踪飞机</div></div>
<div class="card"><div class="num">{in_air}</div><div class="lbl">空中飞行</div></div>
<div class="card"><div class="num">{on_ground}</div><div class="lbl">地面停放</div></div>
<div class="card"><div class="num">{cs_count}</div><div class="lbl">有呼号</div></div></div>
<div class="wxbar"><span>天气 <b>{wx_text}</b></span><span>温度 <b>{wx_temp}°C</b></span><span>湿度 <b>{wx_hum}%</b></span><span>风速 <b>{wx_wind} m/s</b></span></div>
<div id="map"></div>
<div class="charts">
<div class="chart-box"><h3>各时段飞机量</h3><div class="bars">{hbars}</div><div class="bar-labels">{hlabels}</div></div>
<div class="chart-box"><h3>近日峰值</h3><div class="bars">{dbars}</div><div class="bar-labels">{dlabels}</div></div>
</div>
<div class="chart-box"><h3>飞机列表</h3>
<table><thead><tr><th>呼号</th><th>ICAO24</th><th>来源国</th><th>气压高度(m)</th><th>几何高度(m)</th><th>速度(m/s)</th><th>航向</th><th>升降率(m/s)</th><th>Squawk</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
function unlock(){{crypto.subtle.digest("SHA-256",new TextEncoder().encode(document.getElementById("pw").value)).then(h=>{{let x=Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,"0")).join("");if(x=="{PW_HASH}")document.getElementById("lock").style.display="none";else document.getElementById("err").style.display="block"}})}}
var m=L.map("map").setView([37.94,114.84],11);
L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}",{{attribution:'&copy; Esri',maxZoom:18}}).addTo(m);
var planes={json.dumps(pjs,ensure_ascii=False)};
planes.forEach(function(p){{var vr=p.vrate?p.vrate.toFixed(1):"-";var sq=p.sq||"-";var ic=L.divIcon({{html:'<div style="font-size:18px;transform:rotate('+p.trk+'deg)">✈</div>',className:"",iconSize:[22,22],iconAnchor:[11,11]}});L.marker([p.lat,p.lon],{{icon:ic}}).addTo(m).bindPopup("<b>"+p.cs+"</b> ("+p.icao+")<br>来源国: "+p.country+"<br>气压高度: "+p.alt.toFixed(0)+"m | 几何高度: "+p.geo.toFixed(0)+"m<br>地速: "+p.vel.toFixed(0)+"m/s | 航向: "+p.trk.toFixed(0)+"°<br>升降率: "+vr+"m/s | Squawk: "+sq)}})
</script></body></html>'''

    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html: {len(html)} bytes")

def make_weather(data, records):
    ts = data.get("timestamp", "")
    weather = data.get("weather", {})
    if isinstance(weather, dict) and "current" in weather:
        wc = weather["current"]
    else:
        wc = weather if isinstance(weather, dict) else {}
    fc = data.get("forecast", [])
    wx_temp = wc.get("temperature_2m", "--")
    wx_hum = wc.get("relative_humidity_2m", "--")
    wx_wind = wc.get("wind_speed_10m", "--")
    wx_wdir = wc.get("wind_direction_10m", "--")
    wx_code = wc.get("weather_code", -1)
    wx_text = WX_CN.get(wx_code, "--")

    times = [fmt_time(h.get("time",""))[-11:] for h in fc[:48]]
    temps = [h.get("temperature", h.get("temperature_2m",0)) for h in fc[:48]]
    humids = [h.get("humidity", h.get("relative_humidity_2m",0)) for h in fc[:48]]
    precip = [h.get("precip_prob", h.get("precipitation_probability",0)) or 0 for h in fc[:48]]
    winds = [h.get("wind_speed", h.get("wind_speed_10m",0)) for h in fc[:48]]
    wdirs = [h.get("wind_direction", h.get("wind_direction_10m",0)) for h in fc[:48]]
    vis = [h.get("visibility",0) or 0 for h in fc[:48]]

    cd = json.dumps({"labels":times,"temp":temps,"humid":humids,"precip":precip,"wind":winds,"wdir":wdirs,"vis":vis}, ensure_ascii=False)

    # wind table
    wrows = ""
    for i, t in enumerate(times):
        ws = winds[i] if i < len(winds) else "-"
        wd = wdirs[i] if i < len(wdirs) else "-"
        desc = "强风" if (ws or 0) > 10 else "和风" if (ws or 0) > 5 else "微风" if (ws or 0) > 1 else "静风"
        wrows += f"<tr><td>{t}</td><td>{wd}°</td><td>{ws}</td><td>{desc}</td></tr>"

    html = f'''<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><meta name="robots" content="noindex">
<title>藁城 · 气象仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f7;color:#1d1d1f}}
nav{{display:flex;background:rgba(255,255,255,.8);backdrop-filter:blur(20px);padding:12px 24px;border-bottom:1px solid #d2d2d7;position:sticky;top:0;z-index:100}}
nav a{{padding:8px 20px;border-radius:8px;color:#86868b;text-decoration:none;font-size:14px;font-weight:500;margin-right:4px}}
nav a:hover{{background:rgba(0,0,0,.04);color:#1d1d1f}}
nav a.on{{background:#0071e3;color:#fff}}
.container{{max-width:1200px;margin:0 auto;padding:24px}}
.header{{margin-bottom:20px}}
.header h1{{font-size:28px;font-weight:700}}
.header .ts{{font-size:13px;color:#86868b;margin-top:4px}}
.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.06);text-align:center}}
.card .num{{font-size:28px;font-weight:700;color:#0071e3}}
.card .lbl{{font-size:13px;color:#86868b;margin-top:4px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.chart-box{{background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.chart-box h3{{font-size:15px;font-weight:600;margin-bottom:12px}}
.chart-box canvas{{max-height:240px}}
.chart-wide{{grid-column:1/-1}}
.chart-wide canvas{{max-height:300px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:8px 12px;color:#86868b;font-weight:500;border-bottom:1px solid #e5e5ea}}
td{{padding:8px 12px;border-bottom:1px solid #f5f5f7}}
tr:hover td{{background:#f5f5f7}}
</style></head><body>
<nav><a href="index.html">飞机追踪</a><a class="on" href="weather.html">气象仪表盘</a><a href="3d.html">3D地球</a><a href="replay.html">历史回放</a><a href="space.html">太空过境</a><a href="dashboard.html">数据大屏</a></nav>
<div class="container">
<div class="header"><h1>藁城气象仪表盘</h1><div class="ts">更新于 {fmt_time(ts)}</div></div>
<div class="stats">
<div class="card"><div class="num">{wx_text}</div><div class="lbl">天气</div></div>
<div class="card"><div class="num">{wx_temp}°C</div><div class="lbl">温度</div></div>
<div class="card"><div class="num">{wx_hum}%</div><div class="lbl">湿度</div></div>
<div class="card"><div class="num">{wx_wind}m/s</div><div class="lbl">风速</div></div>
<div class="card"><div class="num">{wx_wdir}°</div><div class="lbl">风向</div></div>
</div>
<div class="charts">
<div class="chart-box"><h3>24小时温度趋势</h3><canvas id="c1"></canvas></div>
<div class="chart-box"><h3>24小时湿度趋势</h3><canvas id="c2"></canvas></div>
<div class="chart-box"><h3>24小时降水概率</h3><canvas id="c3"></canvas></div>
<div class="chart-box"><h3>24小时能见度</h3><canvas id="c4"></canvas></div>
<div class="chart-box"><h3>24小时风速</h3><canvas id="c5"></canvas></div>
<div class="chart-box"><h3>24小时风向风况详情</h3><table><thead><tr><th>时间</th><th>风向(°)</th><th>风速(m/s)</th><th>风况</th></tr></thead><tbody>{wrows}</tbody></table></div>
</div></div>
<script>
var d={cd};
var o={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:"#86868b",font:{{size:10}},maxTicksLimit:12}},grid:{{color:"#e5e5ea"}}}},y:{{ticks:{{color:"#86868b",font:{{size:10}}}},grid:{{color:"#e5e5ea"}}}}}}}};
function L(id,vals,color){{new Chart(document.getElementById(id),{{type:"line",data:{{labels:d.labels,datasets:[{{data:vals,borderColor:color,backgroundColor:color+"18",fill:true,tension:.4,pointRadius:2}}]}},options:o}})}}
function B(id,vals){{new Chart(document.getElementById(id),{{type:"bar",data:{{labels:d.labels,datasets:[{{data:vals,backgroundColor:vals.map(function(v){{return "rgba(0,113,227,"+(0.2+v/100*0.7)+")"}}),borderRadius:4}}]}},options:o}})}}
if(d.labels.length){{L("c1",d.temp,"rgba(0,113,227,0.9)");L("c2",d.humid,"#a78bfa");B("c3",d.precip);L("c4",d.vis,"#34d399");L("c5",d.wind,"#f97316")}}
</script></body></html>'''

    with open(os.path.join(DOCS_DIR, "weather.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"weather.html: {len(html)} bytes")

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    data = load_latest()
    records = load_history()
    make_index(data, records)
    make_weather(data, records)
    os.makedirs(os.path.join(DOCS_DIR, "data"), exist_ok=True)
    with open(os.path.join(DOCS_DIR, "data", "latest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("latest.json written")

if __name__ == "__main__":
    main()
