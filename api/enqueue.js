export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const REPO_OWNER = process.env.REPO_OWNER;
  const REPO_NAME = process.env.REPO_NAME;
  const ENQUEUE_SECRET = process.env.ENQUEUE_SECRET;

  if (!GITHUB_TOKEN || !REPO_OWNER || !REPO_NAME) {
    res.status(500).json({ error: 'Server not configured' });
    return;
  }

  const body = req.body;
  const url = body?.url;
  const chat_id = body?.chat_id;
  const secret = req.headers['x-enqueue-secret'];

  if (ENQUEUE_SECRET && ENQUEUE_SECRET !== secret) {
    res.status(403).json({ error: 'Forbidden' });
    return;
  }

  if (!url || !chat_id) {
    res.status(400).json({ error: 'Missing url or chat_id' });
    return;
  }

  const apiUrl = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/dispatches`;
  const payload = {
    event_type: 'clip_request',
    client_payload: { url, chat_id },
  };

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (response.status !== 204 && response.status !== 201) {
    const text = await response.text();
    res.status(500).json({ error: `GitHub dispatch failed: ${response.status} ${text}` });
    return;
  }

  res.status(200).json({ status: 'queued' });
}
