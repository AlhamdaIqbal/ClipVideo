export default function handler(req, res) {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.status(200).send(`<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ClipVideo Webhook</title>
  </head>
  <body>
    <h1>ClipVideo Webhook</h1>
    <p>This deployment only exposes a webhook API at <code>/enqueue</code>.</p>
    <p>Send a POST request to <code>/enqueue</code> with JSON:</p>
    <pre>{"url":"https://youtube.com/watch?v=...","chat_id":"123456789"}</pre>
  </body>
</html>`);
}
