const BASE = process.env.INSFORGE_BASE_URL;
const KEY = process.env.INSFORGE_API_KEY;

export async function insert(table, rows) {
  if (!BASE || !KEY) return { skipped: true, reason: 'INSFORGE not configured' };
  const body = Array.isArray(rows) ? rows : [rows];
  try {
    const r = await fetch(`${BASE}/api/tables/${table}/records`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      return { ok: false, status: r.status, error: text.slice(0, 500) };
    }
    return { ok: true, data: await r.json() };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

export async function upsertBySessionId(table, row) {
  if (!BASE || !KEY) return { skipped: true };
  // Insforge supports upsert via records endpoint when unique constraint exists
  try {
    const r = await fetch(`${BASE}/api/tables/${table}/records?on_conflict=session_id`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
      },
      body: JSON.stringify([row]),
    });
    if (!r.ok) {
      const text = await r.text();
      return { ok: false, status: r.status, error: text.slice(0, 500) };
    }
    return { ok: true, data: await r.json() };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}
