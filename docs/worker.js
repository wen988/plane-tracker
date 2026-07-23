/**
 * 短视频解析 Cloudflare Worker
 * 支持：抖音、快手、B站（后续扩展）
 * 部署到 Cloudflare Workers 后，前端 video-parser.html 的 API_BASE 指向这里即可
 */

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1';

async function handleRequest(request) {
  const url = new URL(request.url);
  const videoUrl = url.searchParams.get('url');
  const isDownload = url.searchParams.get('download') === '1';

  // CORS 预检
  if (request.method === 'OPTIONS') {
    return corsResponse('', 204);
  }

  if (!videoUrl) {
    return jsonResponse({ error: '缺少 url 参数' }, 400);
  }

  // 下载代理模式：直接转发二进制内容
  if (isDownload) {
    return proxyDownload(videoUrl);
  }

  try {
    let result;

    if (isDouyin(videoUrl)) {
      result = await parseDouyin(videoUrl);
    } else if (isKuaishou(videoUrl)) {
      result = await parseKuaishou(videoUrl);
    } else {
      return jsonResponse({ error: '暂不支持该平台，目前支持抖音和快手' }, 400);
    }

    if (!result || !result.video_url) {
      return jsonResponse({ error: '解析失败，请检查链接是否有效' }, 500);
    }

    return jsonResponse(result, 200);
  } catch (e) {
    return jsonResponse({ error: '解析出错: ' + e.message }, 500);
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
  // 第一步：请求分享链接，获取重定向后的真实URL，提取video_id
  let videoId;
  
  if (shareUrl.includes('v.douyin.com')) {
    // App分享链接，需要跟随重定向获取video_id
    const resp = await fetch(shareUrl, {
      redirect: 'manual',
      headers: { 'User-Agent': MOBILE_UA }
    });
    const location = resp.headers.get('Location') || '';
    videoId = extractDouyinVideoId(location);
  } else if (shareUrl.includes('/video/') || shareUrl.includes('/share/video/')) {
    // PC网页链接，直接从URL提取
    videoId = extractDouyinVideoId(shareUrl);
  } else {
    // 可能已经是纯video_id
    videoId = shareUrl.replace(/[^0-9]/g, '');
  }

  if (!videoId) {
    throw new Error('无法从链接中提取视频ID');
  }

  // 第二步：请求抖音页面，提取 ROUTER_DATA
  const pageUrl = `https://www.iesdouyin.com/share/video/${videoId}`;
  const pageResp = await fetch(pageUrl, {
    headers: {
      'User-Agent': MOBILE_UA,
      'Referer': 'https://www.douyin.com/'
    }
  });
  const html = await pageResp.text();

  // 提取 window._ROUTER_DATA
  const routerMatch = html.match(/window\._ROUTER_DATA\s*=\s*({.*?})<\/script>/s);
  if (!routerMatch) {
    throw new Error('获取视频数据失败，可能需要登录或链接已失效');
  }

  const routerData = JSON.parse(routerMatch[1]);
  const itemKey = `video_${videoId}`;
  const itemData = routerData?.loaderData?.[itemKey]?.page?.videoInfoRes?.item_list?.[0];

  if (!itemData) {
    throw new Error('视频信息不存在');
  }

  // 提取信息
  const title = itemData.desc || '';
  const authorName = itemData.author?.nickname || '';
  const authorAvatar = itemData.author?.avatar_thumb?.url_list?.[0] || '';
  const authorUid = itemData.author?.sec_uid || '';
  const coverUrl = itemData.video?.cover?.url_list?.[0] || '';
  
  // 视频地址（playwm 替换为 play 去水印）
  let videoUrl = itemData.video?.play_addr?.url_list?.[0] || '';
  videoUrl = videoUrl.replace('playwm', 'play');

  // 如果是图集，视频地址为空
  const images = (itemData.images || []).map(img => img.url_list?.[0] || '').filter(Boolean);
  if (images.length > 0) {
    videoUrl = '';
  }

  // 获取302重定向后的真实视频URL
  if (videoUrl) {
    try {
      const redirectResp = await fetch(videoUrl, {
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
  // 从路径中提取视频ID
  const match = url.match(/\/(video|share\/video)\/(\d+)/);
  if (match) return match[2];
  // 从路径末尾提取纯数字
  const parts = url.replace(/\/$/, '').split('/');
  const last = parts[parts.length - 1];
  if (/^\d+$/.test(last)) return last;
  return '';
}

// ==================== 快手解析 ====================

async function parseKuaishou(shareUrl) {
  // 直接访问分享页获取HTML（跟随重定向拿到完整页面）
  const resp = await fetch(shareUrl, {
    headers: {
      'User-Agent': MOBILE_UA
    }
  });
  
  const html = await resp.text();

  // 从HTML中提取视频地址（优先选高清 hd15）
  const mp4Matches = [...html.matchAll(/(https?:\/\/[^"\s<>]+\.mp4[^"\s<>]*)/g)];
  const mp4Urls = mp4Matches.map(m => m[1]);
  const hdMp4 = mp4Urls.filter(u => u.includes('hd15'));
  const videoUrl = hdMp4.length > 0 ? hdMp4[0] : (mp4Urls.length > 0 ? mp4Urls[0] : '');

  // 从HTML提取封面图
  let coverUrl = '';
  const ogImage = html.match(/<meta[^>]*property="og:image"[^>]*content="([^"]*)"/);
  if (ogImage) coverUrl = ogImage[1];
  if (!coverUrl) {
    const coverMatch = html.match(/(https?:\/\/[^"\s<>]*upic[^"\s<>]*\.(?:jpg|jpeg|png|webp)[^"\s<>]*)/i);
    if (coverMatch) coverUrl = coverMatch[1];
  }

  // 提取标题
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

  return {
    title,
    video_url: videoUrl,
    music_url: '',
    cover_url: coverUrl,
    author: {
      uid: '',
      name: '',
      avatar: ''
    }
  };
}

// ==================== 工具函数 ====================

// 下载代理：直接转发远程文件二进制内容，解决跨域下载问题
async function proxyDownload(targetUrl) {
  const resp = await fetch(targetUrl, {
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
