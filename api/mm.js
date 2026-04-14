/**
 * POST /api/mm
 *
 * Submits the participant's project to MentorMates using their participant API
 * key. Joins the event (idempotent) then POSTs the project record.
 *
 * Contract sourced from https://github.com/edumame/mentormates-skill
 * (participant API surface: /api/agent/me/events/{event_ref}/...).
 *
 * Body:
 *   {
 *     "api_key": "mm_sk_...",           // participant API key
 *     "event_ref": "slug-or-uuid",
 *     "project_name": "string",
 *     "project_description": "string",
 *     "project_url": "url",             // optional
 *     "video_url": "url",               // optional
 *     "additional_materials_url": "url", // optional
 *     "cover_image_url": "url",         // optional
 *     "lead_name": "string",            // optional
 *     "lead_email": "string"            // optional
 *   }
 *
 * Returns:
 *   200 { ok, project_id, project_url, joined, mm_project_url }
 *   4xx/5xx { error, detail? }
 */

const MM_BASE = process.env.MM_BASE_URL || 'https://www.mentormates.ai';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const body = req.body || {};
  const {
    api_key,
    event_ref,
    project_name,
    project_description,
  } = body;

  if (!api_key || !event_ref || !project_name) {
    return res.status(400).json({
      error: 'api_key, event_ref, and project_name are required',
    });
  }

  const auth = { 'Authorization': `Bearer ${api_key}`, 'Content-Type': 'application/json' };

  // Step 1: idempotent join (200 OK or 409-ish "already joined" both treated as success)
  let joinStatus = null;
  try {
    const joinResp = await fetch(
      `${MM_BASE}/api/agent/me/events/${encodeURIComponent(event_ref)}/join`,
      { method: 'POST', headers: auth },
    );
    joinStatus = joinResp.status;
    if (joinResp.status >= 500) {
      const t = await joinResp.text().catch(() => '');
      return res.status(502).json({ error: 'MM join failed', status: joinResp.status, detail: t.slice(0, 500) });
    }
  } catch (err) {
    return res.status(502).json({ error: `MM join request failed: ${err.message}` });
  }

  // Step 2: create the project
  const projectBody = {
    project_name,
    project_description: project_description || '',
    project_url: body.project_url || undefined,
    video_url: body.video_url || undefined,
    additional_materials_url: body.additional_materials_url || undefined,
    cover_image_url: body.cover_image_url || undefined,
    lead_name: body.lead_name || undefined,
    lead_email: body.lead_email || undefined,
  };
  // Strip undefined so we don't send nulls
  Object.keys(projectBody).forEach(k => projectBody[k] === undefined && delete projectBody[k]);

  let created;
  try {
    const r = await fetch(
      `${MM_BASE}/api/agent/me/events/${encodeURIComponent(event_ref)}/projects`,
      { method: 'POST', headers: auth, body: JSON.stringify(projectBody) },
    );
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      return res.status(r.status).json({ error: data?.error || `MM returned ${r.status}`, detail: data });
    }
    created = data;
  } catch (err) {
    return res.status(502).json({ error: `MM create project failed: ${err.message}` });
  }

  const projectId = created?.project?.id || created?.id || created?.project_id;
  const mmUrl = projectId ? `${MM_BASE}/events/${event_ref}/projects/${projectId}` : null;

  return res.status(200).json({
    ok: true,
    joined: joinStatus,
    project_id: projectId,
    mm_project_url: mmUrl,
    raw: created,
  });
}
