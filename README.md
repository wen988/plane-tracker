# 藁城上空 · 飞机追踪面板

自动抓取藁城区上空实时飞机数据，通过 GitHub Pages 展示成仪表盘网页。

## 原理

- **GitHub Actions** 每小时自动运行一次
- **OpenSky Network API** 免费获取飞行数据
- **GitHub Pages** 免费托管网页
- 全程不需要服务器、不需要花钱

## 部署步骤

### 1. 创建 GitHub 仓库

在 GitHub 上新建仓库，名称随意（如 `plane-tracker`），**不要勾选**「Add a README file」。

### 2. 推送代码

```bash
cd plane-tracker
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

推送后 GitHub Actions 会自动开始运行。

### 3. 开启 GitHub Pages

仓库 → Settings → Pages →
- Source: **Deploy from a branch**
- Branch: **main**，目录选 **/docs**
- Save

稍等一分钟，访问 `https://你的用户名.github.io/仓库名/` 就能看到面板。

## 目录结构

```
plane-tracker/
├── .github/workflows/fetch.yml  # GitHub Actions 定时任务
├── scripts/
│   ├── fetch.py                  # 抓取飞机数据
│   └── generate.py               # 生成网页
├── data/                         # 数据快照（自动写入）
├── docs/
│   └── index.html                # 生成的网页
└── README.md
```
