module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');

  if (req.method === 'OPTIONS') {
    res.statusCode = 200;
    return res.end();
  }

  const targetUrl = 'https://leetcode.com/graphql';

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

  const headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'referer': 'https://leetcode.com/problemset/all/',
    'origin': 'https://leetcode.com',
    'content-type': req.headers['content-type'] || 'application/json',
  };

  if (req.headers.cookie) {
    headers['cookie'] = req.headers.cookie;
  }

  try {
    const response = await fetch(targetUrl, {
      method: req.method,
      headers: headers,
      body: body,
      redirect: 'follow',
    });

    const responseText = await response.text();

    const headersObj = {};
    response.headers.forEach((val, key) => {
      headersObj[key] = val;
    });

    console.log('[PROXY DEBUG - /graphql]', {
      finalUrl: response.url,
      status: response.status,
      headers: headersObj,
      bodyPreview: responseText.substring(0, 500),
    });

    const setCookie = response.headers.get('set-cookie');
    if (setCookie) {
      res.setHeader('Set-Cookie', setCookie);
    }

    res.statusCode = response.status;
    const contentType = response.headers.get('content-type');
    if (contentType) {
      res.setHeader('Content-Type', contentType);
    }

    return res.end(responseText);
  } catch (err) {
    console.error('[PROXY ERROR]', err);
    res.statusCode = 500;
    res.setHeader('Content-Type', 'application/json');
    return res.end(JSON.stringify({ error: 'Proxy request to LeetCode GraphQL failed', message: err.message }));
  }
};
