const https = require('https');

module.exports = async (req, res) => {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');

  if (req.method === 'OPTIONS') {
    res.statusCode = 200;
    res.end();
    return;
  }

  const targetUrl = `https://leetcode.com${req.url}`;

  // Headers passed to LeetCode
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://leetcode.com',
    'Referer': 'https://leetcode.com/problemset/all/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
  };

  if (req.headers['content-type']) {
    headers['Content-Type'] = req.headers['content-type'];
  }

  const proxyReq = https.request(targetUrl, {
    method: req.method,
    headers: headers,
  }, (proxyRes) => {
    res.statusCode = proxyRes.statusCode;
    if (proxyRes.headers['content-type']) {
      res.setHeader('Content-Type', proxyRes.headers['content-type']);
    }
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: 'Proxy request to LeetCode failed', message: err.message }));
  });

  if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
    req.pipe(proxyReq);
  } else {
    proxyReq.end();
  }
};
