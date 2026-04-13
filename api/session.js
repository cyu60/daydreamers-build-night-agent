import { upsertBySessionId } from '../lib-js/insforge.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { session_id, email } = req.body || {};
  if (!session_id || !email) {
    return res.status(400).json({ error: 'session_id and email required' });
  }

  const emailClean = String(email).trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailClean)) {
    return res.status(400).json({ error: 'invalid email' });
  }

  const result = await upsertBySessionId('build_night_sessions', {
    session_id,
    email: emailClean,
    updated_at: new Date().toISOString(),
  });

  if (result.skipped) {
    return res.status(200).json({ ok: true, stored: false, reason: 'insforge not configured' });
  }
  if (!result.ok) {
    return res.status(result.status || 500).json({ error: result.error });
  }
  return res.status(200).json({ ok: true, stored: true });
}
