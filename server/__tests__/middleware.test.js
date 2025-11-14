const request = require('supertest');

describe('Middleware /avalie', () => {
  let engineServer;
  let app;
  let engineUrl;

  beforeAll(async () => {
    // Start fake engine on ephemeral port
    const { app: engineApp } = require('../engine');
    await new Promise((resolve) => {
      engineServer = engineApp.listen(0, resolve);
    });
    const address = engineServer.address();
    engineUrl = `http://127.0.0.1:${address.port}/analyze`;

    // Configure middleware env before requiring it
    process.env.ENGINE_URL = engineUrl;
    process.env.CORS_ORIGIN = 'http://localhost:5173';

    ({ app } = require('../index'));
  });

  afterAll(async () => {
    if (engineServer) {
      await new Promise((resolve) => engineServer.close(resolve));
    }
  });

  test('returns normalized JSON with files', async () => {
    const res = await request(app)
      .post('/avalie')
      .set('Origin', 'http://localhost:5173')
      .send({ url: 'https://example.com' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('success');
    expect(res.body).toHaveProperty('content');
    expect(Array.isArray(res.body.files)).toBe(true);
    const names = res.body.files.map((f) => f.filename);
    expect(names).toEqual(expect.arrayContaining(['summary.json', 'headings.json', 'meta.json', 'links.json']));
  });

  test('streams a zip when zip=1', async () => {
    const res = await request(app)
      .post('/avalie?zip=1')
      .set('Origin', 'http://localhost:5173')
      .send({ url: 'https://example.com' });
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/application\/zip/);
  });

  test('health returns ok', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' });
  });

  test('CORS header present for allowed origin and absent for blocked', async () => {
    const allowed = await request(app)
      .post('/avalie')
      .set('Origin', 'http://localhost:5173')
      .send({ url: 'https://example.com' });
    expect(allowed.headers['access-control-allow-origin']).toBe('http://localhost:5173');

    const blocked = await request(app)
      .post('/avalie')
      .set('Origin', 'http://malicious.local')
      .send({ url: 'https://example.com' });
    expect(blocked.headers['access-control-allow-origin']).toBeUndefined();
  });
});

