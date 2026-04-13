import { getMessages, deleteMessages } from '../lib-js/insforge.js';

export default async function handler(req, res) {
  const session_id = (req.query && req.query.session_id) || null;
  if (!session_id) return res.status(400).json({ error: 'session_id required' });

  if (req.method === 'DELETE') {
    const r = await deleteMessages(session_id);
    if (r.skipped) return res.status(200).json({ ok: true, skipped: true });
    if (!r.ok) return res.status(500).json({ error: r.error });
    return res.status(200).json({ ok: true, deleted: true });
  }

  if (req.method === 'GET') {
    const r = await getMessages(session_id);
    if (r.skipped) return res.status(200).json([]);
    if (!r.ok) return res.status(500).json({ error: r.error });
    return res.status(200).json(r.data || []);
  }

  return res.status(405).json({ error: 'method not allowed' });
}
