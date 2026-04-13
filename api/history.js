const BASE = process.env.INSFORGE_BASE_URL;
const KEY = process.env.INSFORGE_API_KEY;

export default async function handler(req, res) {
  const session_id = (req.query && req.query.session_id) || null;
  if (!session_id) return res.status(400).json({ error: 'session_id required' });
  if (!BASE || !KEY) return res.status(500).json({ error: 'insforge not configured' });

  if (req.method === 'DELETE') {
    const r = await fetch(
      `${BASE}/api/tables/build_night_messages/records?session_id=eq.${encodeURIComponent(session_id)}`,
      { method: 'DELETE', headers: { Authorization: `Bearer ${KEY}` } }
    );
    if (!r.ok) return res.status(r.status).json({ error: await r.text() });
    return res.status(200).json({ ok: true, deleted: true });
  }

  if (req.method === 'GET') {
    const r = await fetch(
      `${BASE}/api/tables/build_night_messages/records?session_id=eq.${encodeURIComponent(session_id)}&order=created_at.asc`,
      { headers: { Authorization: `Bearer ${KEY}` } }
    );
    if (!r.ok) return res.status(r.status).json({ error: await r.text() });
    return res.status(200).json(await r.json());
  }

  return res.status(405).json({ error: 'method not allowed' });
}
