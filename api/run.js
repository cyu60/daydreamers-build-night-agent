import { insertMessage } from '../lib-js/insforge.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const ARA_API = process.env.ARA_API_URL || 'https://ara-api-prd.up.railway.app/v1/apps';
  const APP_ID = process.env.ARA_APP_ID;
  const RUNTIME_KEY = process.env.ARA_RUNTIME_KEY;

  if (!APP_ID || !RUNTIME_KEY) {
    return res.status(500).json({ error: 'ARA_APP_ID or ARA_RUNTIME_KEY not configured' });
  }

  const body = req.body || {};
  const input = body.input || {};
  const sessionId = input.session_id || null;
  const turnId = input.run_id || input.idempotency_key || null;
  const userMessage = input.message || null;
  const transcript = input.transcript || '';

  try {
    if (sessionId && userMessage) {
      await insertMessage({ session_id: sessionId, turn_id: turnId, role: 'user', text: userMessage });
    }

    // Ara only exposes `message` to the subagent LLM. Inline the prior transcript
    // so the LLM actually sees what's been said. Without this the agent is
    // effectively stateless each turn.
    if (transcript && transcript.trim().length > 0) {
      body.input = {
        ...input,
        message:
          `PRIOR CONVERSATION (oldest → newest):\n${transcript}\n\n` +
          `────────────────────────────────────\n` +
          `LATEST PARTICIPANT MESSAGE (reply to this, informed by the full prior context above):\n${userMessage}`,
      };
    }

    const response = await fetch(`${ARA_API}/${APP_ID}/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNTIME_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    const reply = (data?.result?.output_text) || data?.output_text;
    if (sessionId && reply) {
      await insertMessage({ session_id: sessionId, turn_id: turnId, role: 'agent', text: reply });
    }

    return res.status(200).json(data);
  } catch (err) {
    return res.status(502).json({ error: 'Failed to reach Ara API', detail: err.message });
  }
}
