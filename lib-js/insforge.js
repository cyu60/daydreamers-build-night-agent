import { createClient } from '@insforge/sdk';

const BASE = process.env.INSFORGE_BASE_URL;
const KEY = process.env.INSFORGE_API_KEY;

let _client = null;

export function client() {
  if (!_client) {
    if (!BASE || !KEY) return null;
    _client = createClient({ baseUrl: BASE, anonKey: KEY });
  }
  return _client;
}

export async function insertMessage({ session_id, turn_id, role, text }) {
  const c = client();
  if (!c) return { skipped: true };
  try {
    const { data, error } = await c.database
      .from('build_night_messages')
      .insert({ session_id, turn_id, role, text })
      .select();
    if (error) return { ok: false, error: error.message || String(error) };
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

export async function upsertSession({ session_id, email }) {
  const c = client();
  if (!c) return { skipped: true };
  try {
    const { data: existing } = await c.database
      .from('build_night_sessions')
      .select('id')
      .eq('session_id', session_id)
      .limit(1);
    if (existing && existing.length > 0) {
      const { data, error } = await c.database
        .from('build_night_sessions')
        .update({ email, updated_at: new Date().toISOString() })
        .eq('session_id', session_id)
        .select();
      if (error) return { ok: false, error: error.message || String(error) };
      return { ok: true, data };
    }
    const { data, error } = await c.database
      .from('build_night_sessions')
      .insert({ session_id, email })
      .select();
    if (error) return { ok: false, error: error.message || String(error) };
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

export async function getMessages(session_id) {
  const c = client();
  if (!c) return { skipped: true, data: [] };
  try {
    const { data, error } = await c.database
      .from('build_night_messages')
      .select('*')
      .eq('session_id', session_id)
      .order('created_at', { ascending: true });
    if (error) return { ok: false, error: error.message || String(error) };
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

export async function deleteMessages(session_id) {
  const c = client();
  if (!c) return { skipped: true };
  try {
    const { error } = await c.database
      .from('build_night_messages')
      .delete()
      .eq('session_id', session_id);
    if (error) return { ok: false, error: error.message || String(error) };
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}
