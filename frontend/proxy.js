// Thin proxy on port 3000 that forwards every request (including websockets)
// to the Odysseus FastAPI app on 127.0.0.1:8001. The Emergent ingress sends
// non-/api traffic here, but Odysseus serves its own UI from the same FastAPI
// process — so we just pass everything through.

const http = require('http');
const httpProxy = require('http-proxy');

const TARGET = process.env.BACKEND_TARGET || 'http://127.0.0.1:8001';
const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = process.env.HOST || '0.0.0.0';

const proxy = httpProxy.createProxyServer({
  target: TARGET,
  changeOrigin: true,
  ws: true,
  xfwd: true,
  // Long-running streams (chat SSE, research, etc.)
  proxyTimeout: 0,
  timeout: 0,
});

proxy.on('error', (err, req, res) => {
  console.error('[proxy error]', req && req.url, err.message);
  if (res && !res.headersSent) {
    try {
      res.writeHead(502, { 'Content-Type': 'text/plain' });
    } catch (_) {}
  }
  if (res && res.end) {
    try { res.end('Bad gateway: backend unreachable'); } catch (_) {}
  }
});

const server = http.createServer((req, res) => {
  proxy.web(req, res);
});

server.on('upgrade', (req, socket, head) => {
  proxy.ws(req, socket, head);
});

server.listen(PORT, HOST, () => {
  console.log(`[odysseus-proxy] listening on ${HOST}:${PORT} -> ${TARGET}`);
});
