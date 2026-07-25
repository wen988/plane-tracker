/**
 * B站 CORS 代理 - 腾讯云 SCF 版
 * 部署方式：腾讯云 SCF → Web 函数 → 上传此文件为 index.js
 */
'use strict';

exports.main_handler = async (event, context) => {
  const qs = event.queryString || {};
  const targetUrl = qs.url;

  if (!targetUrl) {
    return { statusCode: 400, body: 'Missing ?url=' };
  }

  // 安全：仅允许 B站
  if (!targetUrl.includes('api.bilibili.com') && !targetUrl.includes('www.bilibili.com')) {
    return { statusCode: 403, body: 'Forbidden host' };
  }

  try {
    const https = require('https');
    const http = require('http');
    const parsedUrl = new URL(targetUrl);
    const lib = parsedUrl.protocol === 'https:' ? https : http;

    const data = await new Promise((resolve, reject) => {
      const req = lib.request(targetUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'https://www.bilibili.com/',
          'Accept': 'application/json, text/plain, */*',
          'Accept-Language': 'zh-CN,zh;q=0.9',
        },
        timeout: 8000,
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(body));
      });
      req.on('error', reject);
      req.end();
    });

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json;charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=300',
      },
      body: data,
    };
  } catch (e) {
    return {
      statusCode: 502,
      headers: { 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: e.message }),
    };
  }
};
