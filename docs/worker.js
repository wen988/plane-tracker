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

  // CORS 预检
  if (request.method === 'OPTIONS') {
    return corsResponse('', 204);
  }

  if (!videoUrl) {
    return jsonResponse({ error: '缺少 url 参数' }, 400);
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
  // 快手分享链接重定向后提取 photoId
  const resp = await fetch(shareUrl, {
    redirect: 'manual',
    headers: { 'User-Agent': MOBILE_UA }
  });
  
  const location = resp.headers.get('Location') || '';
  let photoId = '';

  // 从重定向URL提取 photoId
  const photoMatch = location.match(/photoId=(\w+)/);
  if (photoMatch) {
    photoId = photoMatch[1];
  }
  // 也可以从短链接路径提取
  if (!photoId) {
    const pathMatch = location.match(/\/(\w{15,})\b/);
    if (pathMatch) photoId = pathMatch[1];
  }

  if (!photoId) {
    throw new Error('无法提取快手视频ID');
  }

  // 请求快手API
  const apiUrl = `https://v.m.chenzhongtech.com/rest/wd/photo/info?photoId=${photoId}`;
  const apiResp = await fetch(apiUrl, {
    headers: {
      'User-Agent': MOBILE_UA,
      'Referer': 'https://v.kuaishou.com/'
    }
  });
  const data = await apiResp.json();

  if (data.result !== 1 || !data.photo) {
    throw new Error('快手视频获取失败');
  }

  const photo = data.photo;
  const mainUrl = photo.mainMvUrls?.[0]?.url || 
                  photo.video?.url || 
                  photo.watermarkMvUrls?.[0]?.url?.replace('watermark', 'main') || 
                  '';

  return {
    title: photo.caption || '',
    video_url: mainUrl,
    music_url: photo.musicUrls?.[0]?.url || '',
    cover_url: photo.coverUrls?.[0]?.url || '',
    author: {
      uid: photo.userId?.toString() || '',
      name: photo.userName || '',
      avatar: photo.headUrl || ''
    }
  };
}

// ==================== 工具函数 ====================

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
