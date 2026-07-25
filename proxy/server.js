const http = require('http');

const PORT = process.env.PORT || 3000;

const server = http.createServer(async (req, res) => {
  // CORS 预检
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    return res.end();
  }

  const url = new URL(req.url, `http://${req.headers.host}`);
  const targetUrl = url.searchParams.get('url');

  if (!targetUrl) {
    res.writeHead(400);
    return res.end('Missing ?url=');
  }

  if (!targetUrl.includes('api.bilibili.com') && !targetUrl.includes('www.bilibili.com')) {
    res.writeHead(403);
    return res.end('Forbidden host');
  }

  try {
    const resp = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
      },
      signal: AbortSignal.timeout(8000),
    });

    const data = await resp.text();
    res.writeHead(200, {
      'Content-Type': resp.headers.get('Content-Type') || 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=300',
    });
    res.end(data);
  } catch (e) {
    res.writeHead(502, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({ error: e.message }));
  }
});

server.listen(PORT, () => {
  console.log(`B站 CORS 代理已启动 :${PORT}`);
});
