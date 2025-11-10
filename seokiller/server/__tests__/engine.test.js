const request = require('supertest');

describe('Fake Engine /analyze', () => {
  let engineServer;
  let engineApp;

  beforeAll(async () => {
    ({ app: engineApp } = require('../engine'));
    await new Promise((resolve) => {
      engineServer = engineApp.listen(0, resolve);
    });
  });

  afterAll(async () => {
    if (engineServer) {
      await new Promise((resolve) => engineServer.close(resolve));
    }
  });

  test('returns summary and files', async () => {
    const res = await request(engineApp)
      .post('/analyze')
      .send({ url: 'https://example.com' });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('summary');
    expect(Array.isArray(res.body.files)).toBe(true);
  });
});

