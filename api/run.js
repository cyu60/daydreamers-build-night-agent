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

  try {
    const response = await fetch(`${ARA_API}/${APP_ID}/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNTIME_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    return res.status(200).json(data);
  } catch (err) {
    return res.status(502).json({ error: 'Failed to reach Ara API', detail: err.message });
  }
}
