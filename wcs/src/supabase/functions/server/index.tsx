import { Hono } from 'npm:hono';
import { cors } from 'npm:hono/cors';
import { logger } from 'npm:hono/logger';

const app = new Hono();

app.use('*', cors());
app.use('*', logger(console.log));

// Health check
app.get('/make-server-83221f8b/health', (c) => {
  return c.json({ status: 'ok', message: 'Server is running' });
});

Deno.serve(app.fetch);
