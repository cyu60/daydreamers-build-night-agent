/**
 * POST /api/tinyfish
 *
 * Streams a Tinyfish automation run to the client as Server-Sent Events.
 * Each upstream SSE event is forwarded verbatim so the frontend can render
 * the live browser view (streamingUrl) and per-step purpose text as the
 * run progresses — not only the final result.
 *
 * Body: { api_key, url, goal, browser_profile? }
 */

export const config = { maxDuration: 300 };

const TINYFISH_ENDPOINT = 'https://agent.tinyfish.ai/v1/automation/run-sse';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { api_key, url, goal, browser_profile } = req.body || {};
  if (!api_key || !url || !goal) {
    return res.status(400).json({ error: 'api_key, url, and goal are required' });
  }

  let upstream;
  try {
    upstream = await fetch(TINYFISH_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'X-API-Key': api_key,
      },
      body: JSON.stringify({
        url,
        goal,
        browser_profile: browser_profile || 'stealth',
      }),
    });
  } catch (err) {
    return res.status(502).json({ error: `Failed to reach Tinyfish: ${err.message}` });
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => '');
    return res.status(upstream.status || 502).json({
      error: `Tinyfish upstream returned ${upstream.status}`,
      detail: text.slice(0, 500),
    });
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  const decoder = new TextDecoder();
  const reader = upstream.body.getReader();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;
      // Forward complete SSE frames immediately. Keep the partial tail.
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, idx + 2);
        buffer = buffer.slice(idx + 2);
        res.write(frame);
      }
    }
    if (buffer.length) res.write(buffer);
  } catch (err) {
    res.write(`data: ${JSON.stringify({ type: 'ERROR', message: err.message })}\n\n`);
  } finally {
    try { reader.cancel(); } catch {}
    res.end();
  }
}
