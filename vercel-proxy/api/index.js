module.exports = async (req, res) => {
  // 1. Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');

  // Handle preflight CORS request
  if (req.method === 'OPTIONS') {
    res.statusCode = 200;
    res.end();
    return;
  }

  try {
    // 2. Normalize path & query parameters to ensure trailing slash for /api/problems/all
    let path = req.url || '/';
    if (path === '/api/problems/all') {
      path = '/api/problems/all/';
    } else if (path.startsWith('/api/problems/all?')) {
      path = path.replace('/api/problems/all?', '/api/problems/all/?');
    }

    const targetUrl = `https://leetcode.com${path}`;

    // 3. Prepare headers for LeetCode
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

    // 4. Handle incoming request body for POST/PUT/PATCH/DELETE
    let body = null;
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
      if (req.body) {
        body = typeof req.body === 'object' ? JSON.stringify(req.body) : req.body;
      } else {
        const chunks = [];
        for await (const chunk of req) {
          chunks.push(chunk);
        }
        if (chunks.length > 0) {
          body = Buffer.concat(chunks);
        }
      }
    }

    // 5. Execute request with native fetch() and redirect: 'follow'
    const response = await fetch(targetUrl, {
      method: req.method,
      headers: headers,
      body: body,
      redirect: 'follow',
    });

    // 6. Forward response status & headers
    res.statusCode = response.status;

    const contentType = response.headers.get('content-type');
    if (contentType) {
      res.setHeader('Content-Type', contentType);
    }

    // 7. Send back response body
    const arrayBuffer = await response.arrayBuffer();
    res.end(Buffer.from(arrayBuffer));
  } catch (err) {
    res.statusCode = 500;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ error: 'Proxy request to LeetCode failed', message: err.message }));
  }
};
