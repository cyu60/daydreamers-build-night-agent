/**
 * POST /api/tinyfish
 *
 * Executes a Tinyfish automation run for the participant using their own API key.
 * Streams the SSE events from tinyfish.ai, buffers until COMPLETE or ERROR, and
 * returns a single JSON response with the parsed result.
 *
 * Body:
 *   {
 *     "api_key": "<participant's Tinyfish key>",
 *     "url":     "<target URL or recording URL>",
 *     "goal":    "<natural-language task>",
 *     "browser_profile": "stealth" | "lite"  (optional, defaults to stealth)
 *   }
 *
 * Returns:
 *   200 { ok: true, result, run_id, streaming_url }
 *   4xx { error: "..." }            (bad input)
 *   5xx { error: "..." }            (tinyfish upstream failure)
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

  const decoder = new TextDecoder();
  const reader = upstream.body.getReader();
  let buffer = '';
  let runId = null;
  let streamingUrl = null;
  let result = null;
  let errorEvent = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const raw of lines) {
      const line = raw.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      let evt;
      try { evt = JSON.parse(payload); } catch { continue; }

      if (evt.runId) runId = evt.runId;
      if (evt.streamingUrl) streamingUrl = evt.streamingUrl;

      if (evt.type === 'COMPLETE') {
        const rj = evt.resultJson || {};
        if (rj.parsed) {
          try { result = JSON.parse(rj.parsed); } catch { result = rj.parsed; }
        } else if (rj.input) {
          try { result = JSON.parse(rj.input); } catch { result = rj.input; }
        } else if (evt.result) {
          result = evt.result;
        }
        break;
      }
      if (evt.type === 'ERROR') {
        errorEvent = evt;
        break;
      }
    }

    if (result !== null || errorEvent) break;
  }

  try { reader.cancel(); } catch {}

  if (errorEvent) {
    return res.status(502).json({
      error: errorEvent.message || 'Tinyfish reported an error',
      run_id: runId,
      streaming_url: streamingUrl,
    });
  }

  if (result === null) {
    return res.status(504).json({
      error: 'Tinyfish stream ended without a COMPLETE event',
      run_id: runId,
      streaming_url: streamingUrl,
    });
  }

  return res.status(200).json({
    ok: true,
    result,
    run_id: runId,
    streaming_url: streamingUrl,
  });
}
