/**
 * 短视频解析 Cloudflare Worker v2
 * 支持：抖音、快手
 * 修复：所有 fetch 调用增加超时控制，防止 Worker 挂起被 Cloudflare 杀死
 */

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1';
const FETCH_TIMEOUT = 7000; // 单次 fetch 超时 7 秒
const OVERALL_TIMEOUT = 12000; // 整体超时 12 秒（低于前端 15 秒 AbortController）

// 带超时的 fetch 封装
async function fetchWithTimeout(url, options = {}, timeout = FETCH_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function handleRequest(request) {
  const url = new URL(request.url);
  let videoUrl = url.searchParams.get('url');
  const isDownload = url.searchParams.get('download') === '1';

  if (request.method === 'OPTIONS') {
    return corsResponse('', 204);
  }

  // 从粘贴文本中提取纯 URL（兜底）
  videoUrl = extractUrl(videoUrl);

  if (!videoUrl) {
    return jsonResponse({ success: false, error: '缺少 url 参数' }, 400);
  }

  if (isDownload) {
    return proxyDownload(videoUrl);
  }

  try {
    let result;

    // 整体超时 Promise.race
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('请求超时，请稍后重试')), OVERALL_TIMEOUT)
    );

    const parsePromise = (async () => {
      if (isDouyin(videoUrl)) {
        return await parseDouyin(videoUrl);
      } else if (isKuaishou(videoUrl)) {
        return await parseKuaishou(videoUrl);
      } else {
        return null; // 不支持的平台
      }
    })();

    result = await Promise.race([parsePromise, timeoutPromise]);

    if (result === null) {
      return jsonResponse({ success: false, error: '暂不支持该平台，目前支持抖音和快手' }, 400);
    }

    if (!result || !result.video_url) {
      return jsonResponse({ success: false, error: '解析失败，请检查链接是否有效' }, 200);
    }

    // 转换为前端期望的驼峰格式
    const platform = isDouyin(videoUrl) ? '抖音' : (isKuaishou(videoUrl) ? '快手' : '');
    const output = {
      title: result.title,
      videoUrl: result.video_url,
      musicUrl: result.music_url,
      cover: result.cover_url,
      images: result.images,
      platform: platform,
      author: result.author?.name || '',
      avatar: result.author?.avatar || '',
      uid: result.author?.uid || ''
    };
    return jsonResponse({ success: true, ...output }, 200);
  } catch (e) {
    const msg = e.name === 'AbortError' ? '请求超时，请稍后重试' : ('解析出错: ' + e.message);
    return jsonResponse({ success: false, error: msg }, 200);
  }
}

// ==================== 平台检测 ====================

function isDouyin(url) {
  return /douyin\.com|iesdouyin\.com/.test(url);
}

function isKuaishou(url) {
  return /kuaishou\.com|chenzhongtech\.com/.test(url);
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

  if (!videoId) {
    throw new Error('无法识别抖音视频ID，请确认链接正确');
  }

  const pageUrl = `https://www.iesdouyin.com/share/video/${videoId}`;
  const pageResp = await fetchWithTimeout(pageUrl, {
    headers: {
      'User-Agent': MOBILE_UA,
      'Referer': 'https://www.douyin.com/'
    }
  });
  const html = await pageResp.text();

  const routerMatch = html.match(/window\._ROUTER_DATA\s*=\s*({.*?})<\/script>/s);
  if (!routerMatch) {
    throw new Error('获取视频数据失败，可能需要登录或链接已失效');
  }

  const routerData = JSON.parse(routerMatch[1]);
  const itemKey = `video_${videoId}`;
  const itemData = routerData?.loaderData?.[itemKey]?.page?.videoInfoRes?.item_list?.[0];

  if (!itemData) {
    throw new Error('视频信息不存在，可能已被删除或设为私密');
  }

  const title = itemData.desc || '';
  const authorName = itemData.author?.nickname || '';
  const authorAvatar = itemData.author?.avatar_thumb?.url_list?.[0] || '';
  const authorUid = itemData.author?.sec_uid || '';
  const coverUrl = itemData.video?.cover?.url_list?.[0] || '';

  let videoUrl = itemData.video?.play_addr?.url_list?.[0] || '';
  videoUrl = videoUrl.replace('playwm', 'play');

  const images = (itemData.images || []).map(img => img.url_list?.[0] || '').filter(Boolean);
  if (images.length > 0) {
    videoUrl = '';
  }

  if (videoUrl) {
    try {
      const redirectResp = await fetchWithTimeout(videoUrl, {
        redirect: 'manual',
        headers: { 'User-Agent': MOBILE_UA }
      });
      const finalUrl = redirectResp.headers.get('Location');
      if (finalUrl) videoUrl = finalUrl;
    } catch (e) {
      // 保持原地址
    }
  }

  return {
    title,
    video_url: videoUrl,
    music_url: '',
    cover_url: coverUrl,
    images,
    author: {
      uid: authorUid,
      name: authorName,
      avatar: authorAvatar
    }
  };
}

function extractDouyinVideoId(url) {
  const match = url.match(/\/(video|share\/video)\/(\d+)/);
  if (match) return match[2];
  const parts = url.replace(/\/$/, '').split('/');
  const last = parts[parts.length - 1];
  if (/^\d+$/.test(last)) return last;
  return '';
}

// ==================== 快手解析 ====================

async function parseKuaishou(shareUrl) {
  const resp = await fetchWithTimeout(shareUrl, {
    headers: { 'User-Agent': MOBILE_UA }
  });
  const html = await resp.text();

  const mp4Matches = [...html.matchAll(/(https?:\/\/[^"\s<>]+\.mp4[^"\s<>]*)/g)];
  const mp4Urls = mp4Matches.map(m => m[1]);
  const hdMp4 = mp4Urls.filter(u => u.includes('hd15'));
  const videoUrl = hdMp4.length > 0 ? hdMp4[0] : (mp4Urls.length > 0 ? mp4Urls[0] : '');

  let coverUrl = '';
  const ogImage = html.match(/<meta[^>]*property="og:image"[^>]*content="([^"]*)"/);
  if (ogImage) coverUrl = ogImage[1];
  if (!coverUrl) {
    const coverMatch = html.match(/(https?:\/\/[^"\s<>]*upic[^"\s<>]*\.(?:jpg|jpeg|png|webp)[^"\s<>]*)/i);
    if (coverMatch) coverUrl = coverMatch[1];
  }

  let title = '';
  const ogTitle = html.match(/<meta[^>]*property="og:title"[^>]*content="([^"]*)"/);
  if (ogTitle && ogTitle[1] !== '快手') title = ogTitle[1];
  if (!title) {
    const descMatch = html.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/);
    if (descMatch) title = descMatch[1];
  }

  if (!videoUrl) {
    throw new Error('未在页面中找到视频地址');
  }

  // 提取作者信息
  let authorName = '';
  let authorAvatar = '';
  let authorUid = '';

  // 尝试从 __INITIAL_STATE__ 提取
  const stateMatch = html.match(/window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*<\/script>/s);
  if (stateMatch) {
    try {
      const state = JSON.parse(stateMatch[1]);
      const mediaInfo = state?.photo || state?.video || state?.feed || {};
      authorName = mediaInfo?.userName || mediaInfo?.authorName || mediaInfo?.author?.name || '';
      authorAvatar = mediaInfo?.headUrl || mediaInfo?.authorAvatar || mediaInfo?.author?.avatar || mediaInfo?.author?.headurl || '';
      authorUid = mediaInfo?.userId || mediaInfo?.authorId || mediaInfo?.author?.uid || mediaInfo?.author?.id || '';
    } catch(e) {}
  }

  // 尝试从 JSON-LD 提取
  if (!authorName) {
    const jsonLdMatch = html.match(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/);
    if (jsonLdMatch) {
      try {
        const ld = JSON.parse(jsonLdMatch[1]);
        authorName = ld?.author?.name || ld?.creator?.name || '';
      } catch(e) {}
    }
  }

  // 尝试从 __NEXT_DATA__ 提取
  if (!authorName) {
    const nextMatch = html.match(/<script[^>]*id="__NEXT_DATA__"[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/);
    if (nextMatch) {
      try {
        const nextData = JSON.parse(nextMatch[1]);
        const props = nextData?.props?.pageProps?.videoInfo || nextData?.props?.pageProps?.photoInfo || nextData?.props?.pageProps || {};
        authorName = props?.author?.name || props?.authorName || props?.userName || '';
        authorAvatar = props?.author?.avatar || props?.authorAvatar || props?.headUrl || '';
        authorUid = props?.author?.id || props?.authorId || props?.userId || '';
      } catch(e) {}
    }
  }

  return {
    title,
    video_url: videoUrl,
    music_url: '',
    cover_url: coverUrl,
    author: { uid: authorUid, name: authorName, avatar: authorAvatar }
  };
}

// ==================== 工具函数 ====================

function extractUrl(text) {
  if (!text) return '';
  const match = text.match(/https?:\/\/\S+/);
  return match ? match[0] : text;
}

async function proxyDownload(targetUrl) {
  const resp = await fetchWithTimeout(targetUrl, {
    headers: { 'User-Agent': MOBILE_UA }
  });
  const contentType = resp.headers.get('Content-Type') || 'application/octet-stream';
  const contentLength = resp.headers.get('Content-Length');

  const headers = {
    'Content-Type': contentType,
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Expose-Headers': 'Content-Disposition',
    'Cache-Control': 'public, max-age=3600'
  };
  if (contentLength) headers['Content-Length'] = contentLength;

  return new Response(resp.body, { status: 200, headers });
}

function jsonResponse(data, status = 200) {
  const body = JSON.stringify(data);
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Cache-Control': 'no-cache'
    }
  });
}

function corsResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Cache-Control': 'no-cache'
    }
  });
}
