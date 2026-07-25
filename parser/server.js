/**
 * 短视频解析 Node.js 服务 v1
 * 支持：抖音、快手、B站
 * 部署目标：Render / Koyeb 等免费 Node.js 平台
 * 要求 Node.js >= 18（内置 global fetch）
 */

const http = require('http');

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1';
const FETCH_TIMEOUT = 7000;
const OVERALL_TIMEOUT = 12000;
const PROXY_BASE = 'https://vercel-bili-proxy-chi.vercel.app/api/bilibili';

// ==================== HTTP Server ====================

const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // 健康检查
  if (req.url === '/' || req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', platform: 'Node.js' }));
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);
  let videoUrl = url.searchParams.get('url');
  const isDownload = url.searchParams.get('download') === '1';

  videoUrl = extractUrl(videoUrl);

  if (!videoUrl) {
    json(res, 400, { success: false, error: '缺少 url 参数' });
    return;
  }

  if (isDownload) {
    await proxyDownload(res, videoUrl);
    return;
  }

  try {
    const result = await Promise.race([
      parseByPlatform(videoUrl),
      timeout(OVERALL_TIMEOUT, '请求超时，请稍后重试')
    ]);

    if (result === null) {
      json(res, 400, { success: false, error: '暂不支持该平台，目前支持抖音、快手和B站' });
      return;
    }

    if (!result || !result.video_url) {
      json(res, 200, { success: false, error: '解析失败，请检查链接是否有效' });
      return;
    }

    const platform = isDouyin(videoUrl) ? '抖音'
      : (isKuaishou(videoUrl) ? '快手'
      : (isBilibili(videoUrl) ? 'B站' : ''));

    json(res, 200, {
      success: true,
      title: result.title,
      videoUrl: result.video_url,
      musicUrl: result.music_url,
      cover: result.cover_url,
      images: result.images,
      platform,
      author: result.author?.name || '',
      avatar: result.author?.avatar || '',
      uid: result.author?.uid || ''
    });
  } catch (e) {
    const msg = e.name === 'AbortError' ? '请求超时，请稍后重试' : ('解析出错: ' + e.message);
    json(res, 200, { success: false, error: msg });
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Parser service running on port ${PORT}`);
});

// ==================== 路由分发 ====================

async function parseByPlatform(videoUrl) {
  if (isDouyin(videoUrl)) return parseDouyin(videoUrl);
  if (isKuaishou(videoUrl)) return parseKuaishou(videoUrl);
  if (isBilibili(videoUrl)) return parseBilibili(videoUrl);
  return null;
}

// ==================== 平台检测 ====================

function isDouyin(url) {
  return /douyin\.com|iesdouyin\.com/.test(url);
}

function isKuaishou(url) {
  return /kuaishou\.com|chenzhongtech\.com/.test(url);
}

function isBilibili(url) {
  return /bilibili\.com|b23\.tv|b22\.tv/.test(url);
}

// ==================== 抖音解析 ====================

async function parseDouyin(shareUrl) {
  let videoId;

  if (shareUrl.includes('v.douyin.com')) {
    const resp = await fetchWithTimeout(shareUrl, {
      redirect: 'manual',
      headers: { 'User-Agent': MOBILE_UA }
    });
    const location = resp.headers.get('Location') || '';
    videoId = extractDouyinVideoId(location);
  } else if (shareUrl.includes('/video/') || shareUrl.includes('/share/video/')) {
    videoId = extractDouyinVideoId(shareUrl);
  } else {
    videoId = shareUrl.replace(/[^0-9]/g, '');
  }

  if (!videoId) throw new Error('无法识别抖音视频ID，请确认链接正确');

  const pageResp = await fetchWithTimeout(
    `https://www.iesdouyin.com/share/video/${videoId}`,
    { headers: { 'User-Agent': MOBILE_UA, 'Referer': 'https://www.douyin.com/' } }
  );
  const html = await pageResp.text();

  const routerMatch = html.match(/window\._ROUTER_DATA\s*=\s*({.*?})<\/script>/s);
  if (!routerMatch) throw new Error('获取视频数据失败，可能需要登录或链接已失效');

  const routerData = JSON.parse(routerMatch[1]);
  let itemData = routerData?.loaderData?.['video_(id)/page']?.videoInfoRes?.item_list?.[0];
  if (!itemData) {
    const itemKey = `video_${videoId}`;
    itemData = routerData?.loaderData?.[itemKey]?.page?.videoInfoRes?.item_list?.[0];
  }
  if (!itemData) throw new Error('视频信息不存在，可能已被删除或设为私密');

  const title = itemData.desc || '';
  const authorName = itemData.author?.nickname || '';
  const authorAvatar = itemData.author?.avatar_thumb?.url_list?.[0] || '';
  const authorUid = itemData.author?.sec_uid || '';
  const coverUrl = itemData.video?.cover?.url_list?.[0] || '';

  let videoUrl = (itemData.video?.play_addr?.url_list?.[0] || '').replace('playwm', 'play');
  const images = (itemData.images || []).map(img => img.url_list?.[0] || '').filter(Boolean);
  if (images.length > 0) videoUrl = '';

  if (videoUrl) {
    try {
      const redirectResp = await fetchWithTimeout(videoUrl, {
        redirect: 'manual',
        headers: { 'User-Agent': MOBILE_UA, 'Referer': 'https://www.douyin.com/' }
      });
      const finalUrl = redirectResp.headers.get('Location');
      if (finalUrl) videoUrl = finalUrl;
    } catch (_) {}
  }

  return {
    title, video_url: videoUrl, music_url: '',
    cover_url: coverUrl, images,
    author: { uid: authorUid, name: authorName, avatar: authorAvatar }
  };
}

function extractDouyinVideoId(url) {
  const match = url.match(/\/(video|share\/video)\/(\d+)/);
  if (match) return match[2];
  const last = url.replace(/\/$/, '').split('/').pop();
  return /^\d+$/.test(last) ? last : '';
}

// ==================== 快手解析 ====================

async function parseKuaishou(shareUrl) {
  const resp = await fetchWithTimeout(shareUrl, { headers: { 'User-Agent': MOBILE_UA } });
  const html = await resp.text();

  const mp4Matches = [...html.matchAll(/(https?:\/\/[^"\s<>]+\.mp4[^"\s<>]*)/g)];
  const mp4Urls = mp4Matches.map(m => m[1]);
  const hdMp4 = mp4Urls.filter(u => u.includes('hd15'));
  const videoUrl = hdMp4[0] || mp4Urls[0] || '';

  let coverUrl = '';
  const ogImage = html.match(/<meta[^>]*property="og:image"[^>]*content="([^"]*)"/);
  if (ogImage) coverUrl = ogImage[1];
  if (!coverUrl) {
    const cm = html.match(/(https?:\/\/[^"\s<>]*upic[^"\s<>]*\.(?:jpg|jpeg|png|webp)[^"\s<>]*)/i);
    if (cm) coverUrl = cm[1];
  }

  let title = '';
  const ogTitle = html.match(/<meta[^>]*property="og:title"[^>]*content="([^"]*)"/);
  if (ogTitle && ogTitle[1] !== '快手') title = ogTitle[1];
  if (!title) {
    const dm = html.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/);
    if (dm) title = dm[1];
  }
  if (!videoUrl) throw new Error('未在页面中找到视频地址');

  let authorName = '', authorAvatar = '', authorUid = '';
  const stateMatch = html.match(/window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*<\/script>/s);
  if (stateMatch) {
    try {
      const state = JSON.parse(stateMatch[1]);
      const mi = state?.photo || state?.video || state?.feed || {};
      authorName = mi?.userName || mi?.authorName || mi?.author?.name || '';
      authorAvatar = mi?.headUrl || mi?.authorAvatar || mi?.author?.avatar || mi?.author?.headurl || '';
      authorUid = mi?.userId || mi?.authorId || mi?.author?.uid || mi?.author?.id || '';
    } catch (_) {}
  }

  return { title, video_url: videoUrl, music_url: '', cover_url: coverUrl,
    author: { uid: authorUid, name: authorName, avatar: authorAvatar } };
}

// ==================== B站解析 ====================

function extractBvId(url) {
  const bv = url.match(/BV[a-zA-Z0-9]{10}/);
  if (bv) return bv[0];
  const av = url.match(/av(\d+)/i);
  if (av) return av[0].toUpperCase();
  return '';
}

async function parseBilibili(shareUrl) {
  let videoId = extractBvId(shareUrl);

  if (!videoId && /b23\.tv|b22\.tv/.test(shareUrl)) {
    const r = await fetchWithTimeout(shareUrl, {
      redirect: 'manual',
      headers: { 'User-Agent': MOBILE_UA }
    });
    const loc = r.headers.get('Location') || '';
    videoId = extractBvId(loc) || extractBvId(decodeURIComponent(loc));
  }

  if (!videoId) throw new Error('无法识别B站视频ID，请确认链接正确');

  const bvid = videoId.startsWith('BV') ? videoId : videoId;

  const apiHeaders = {
    'User-Agent': MOBILE_UA,
    'Referer': 'https://www.bilibili.com/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9'
  };

  const viewResp = await fetchWithTimeout(
    `https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`,
    { headers: apiHeaders }
  );
  const viewData = await viewResp.json();
  if (viewData.code !== 0) throw new Error(viewData.message || '获取视频信息失败');

  const v = viewData.data;
  const title = v.title || '';
  const coverUrl = v.pic || '';
  const cid = v.cid;
  if (!cid) throw new Error('未找到视频 cid');

  const playResp = await fetchWithTimeout(
    `https://api.bilibili.com/x/player/playurl?bvid=${bvid}&cid=${cid}&qn=80&fnval=80&fourk=1`,
    { headers: apiHeaders }
  );
  const playData = await playResp.json();
  if (playData.code !== 0) throw new Error(playData.message || '获取播放地址失败');

  let videoUrl = '';
  if (playData.data?.durl?.length > 0) {
    videoUrl = playData.data.durl[0].url || playData.data.durl[0].backup_url?.[0] || '';
  }
  if (!videoUrl && playData.data?.dash?.video?.length > 0) {
    videoUrl = playData.data.dash.video[0].baseUrl || playData.data.dash.video[0].base_url || '';
  }
  if (!videoUrl) throw new Error('获取播放地址失败，视频可能需要登录或已失效');

  let musicUrl = '';
  const dashAudio = playData.data?.dash?.audio;
  if (dashAudio && dashAudio.length > 0) {
    musicUrl = dashAudio[0].baseUrl || dashAudio[0].base_url || '';
  }

  return {
    title, video_url: videoUrl, music_url: musicUrl, cover_url: coverUrl,
    bvid, cid: String(cid),
    author: {
      uid: String(v.owner?.mid || ''),
      name: v.owner?.name || '',
      avatar: v.owner?.face || ''
    }
  };
}

// ==================== 工具函数 ====================

function extractUrl(text) {
  if (!text) return '';
  const m = text.match(/https?:\/\/\S+/);
  return m ? m[0] : text;
}

function timeout(ms, msg) {
  return new Promise((_, reject) => setTimeout(() => reject(new Error(msg)), ms));
}

async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(t);
  }
}

async function proxyDownload(res, targetUrl) {
  // B站 CDN 走 Vercel 流式代理（绕过 Render IP 可能被封的情况）
  if (targetUrl.includes('bilivideo.com') || targetUrl.includes('hdslb.com')) {
    const streamUrl = `${PROXY_BASE}?action=stream&url=${encodeURIComponent(targetUrl)}`;
    const proxyResp = await fetchWithTimeout(streamUrl, {}, 30000);
    if (!proxyResp.ok) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: false, error: `下载代理失败 (${proxyResp.status})` }));
      return;
    }
    res.writeHead(200, {
      'Content-Type': proxyResp.headers.get('Content-Type') || 'video/mp4',
      'Content-Disposition': 'attachment; filename="bilibili_video.mp4"',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Expose-Headers': 'Content-Disposition',
      'Accept-Ranges': 'bytes'
    });
    if (proxyResp.body) {
      const reader = proxyResp.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(value);
      }
    }
    res.end();
    return;
  }

  let referer = '';
  if (/douyin\.com|snssdk\.com|douyinvod\.com/.test(targetUrl)) referer = 'https://www.douyin.com/';
  else if (/kuaishou\.com|yximgs\.com/.test(targetUrl)) referer = 'https://www.kuaishou.com/';
  else if (/bilibili\.com|bilivideo\.com/.test(targetUrl)) referer = 'https://www.bilibili.com/';

  const opts = { headers: { 'User-Agent': MOBILE_UA } };
  if (referer) opts.headers['Referer'] = referer;

  const dlResp = await fetchWithTimeout(targetUrl, opts);
  const ct = dlResp.headers.get('Content-Type') || 'application/octet-stream';

  res.writeHead(200, {
    'Content-Type': ct,
    'Content-Disposition': 'attachment; filename="video.mp4"',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Expose-Headers': 'Content-Disposition',
    'Cache-Control': 'public, max-age=3600'
  });

  if (dlResp.body) {
    const reader = dlResp.body.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(value);
    }
  }
  res.end();
}

function json(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-cache'
  });
  res.end(JSON.stringify(data));
}
