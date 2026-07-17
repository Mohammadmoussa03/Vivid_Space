#!/usr/bin/env node
/**
 * Vivid Space load / stress harness. No dependencies — plain node:http.
 *
 * Closed-loop: --conc workers each fire a request, await it, and immediately
 * fire the next until the deadline. Reported RPS is therefore throughput at
 * that concurrency, not an offered rate.
 *
 * Usage:
 *   node loadtest.mjs --target http://127.0.0.1 --scenario read --conc 20 --duration 30
 *
 * Scenarios:
 *   static  nginx serving the built SPA (never touches Django)
 *   read    public DRF GET endpoints
 *   auth    csrf -> login -> me -> refresh -> logout
 *   tours   POST /api/tours/ (public write; inserts a row + console email)
 *   race    correctness probe: N concurrent identical bookings, expect exactly 1 win
 */
import http from 'node:http';
import https from 'node:https';
import { URL } from 'node:url';

// ---------- args ----------
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, arr) => {
    if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1]?.startsWith('--') ? true : arr[i + 1]]);
    return acc;
  }, []),
);
const TARGET = args.target || 'http://127.0.0.1';
const SCENARIO = args.scenario || 'read';
const CONC = Number(args.conc || 10);
const DURATION = Number(args.duration || 20);
const WARMUP = Number(args.warmup || 3);
const EMAIL = args.email || 'mohammad@loopstudio.co';
const PASSWORD = args.password || 'demo1234';
const LABEL = args.label || `${SCENARIO}@c${CONC}`;

const base = new URL(TARGET);
const client = base.protocol === 'https:' ? https : http;
const agent = new client.Agent({ keepAlive: true, maxSockets: CONC + 4 });

// ---------- tiny http ----------
function req(method, path, { body, jar, headers = {} } = {}) {
  // A bad index silently becomes GET /undefined, which nginx answers from the
  // SPA fallback with a 200 — the load test would then measure nginx, not Django.
  if (typeof path !== 'string' || !path.startsWith('/')) throw new Error(`bad path: ${path}`);
  return new Promise((resolve) => {
    const u = new URL(path, base);
    const h = { Accept: 'application/json', ...headers };
    let payload;
    if (body !== undefined) {
      payload = JSON.stringify(body);
      h['Content-Type'] = 'application/json';
      h['Content-Length'] = Buffer.byteLength(payload);
    }
    if (jar) {
      const cookies = Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ');
      if (cookies) h.Cookie = cookies;
      if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && jar.csrftoken) h['X-CSRFToken'] = jar.csrftoken;
    }
    const started = process.hrtime.bigint();
    const r = client.request(
      { hostname: u.hostname, port: u.port || (base.protocol === 'https:' ? 443 : 80), path: u.pathname + u.search, method, headers: h, agent },
      (res) => {
        let bytes = 0;
        let raw = '';
        res.on('data', (c) => { bytes += c.length; if (raw.length < 4096) raw += c; });
        res.on('end', () => {
          if (jar) {
            for (const line of res.headers['set-cookie'] || []) {
              const [kv] = line.split(';');
              const idx = kv.indexOf('=');
              if (idx > 0) jar[kv.slice(0, idx).trim()] = kv.slice(idx + 1).trim();
            }
          }
          resolve({
            status: res.statusCode,
            ms: Number(process.hrtime.bigint() - started) / 1e6,
            bytes,
            body: raw,
          });
        });
      },
    );
    r.on('error', (e) => resolve({ status: 0, ms: Number(process.hrtime.bigint() - started) / 1e6, bytes: 0, err: e.code || e.message }));
    r.setTimeout(30000, () => { r.destroy(); });
    if (payload) r.write(payload);
    r.end();
  });
}

// ---------- scenarios ----------
const READ_MIX = [
  ['/api/site/', 3],
  ['/api/spaces/', 3],
  ['/api/packages/', 2],
  ['/api/gallery/', 1],
  ['/api/faqs/', 1],
  ['/api/categories/', 1],
];
const weighted = READ_MIX.flatMap(([p, w]) => Array(w).fill(p));

let staticAssets = ['/'];
async function discoverAssets() {
  const res = await req('GET', '/');
  const found = [...res.body.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((m) => m[1]);
  staticAssets = ['/', ...new Set(found)];
}

async function login(jar) {
  await req('GET', '/api/auth/csrf/', { jar });
  return req('POST', '/api/auth/login/', { jar, body: { email: EMAIL, password: PASSWORD } });
}

function tourBody(i) {
  return {
    first_name: 'Loadtest',
    last_name: `Bot${i}`,
    email: `loadtest+${i}-${process.pid}@loadtest.invalid`,
    phone: '+96170000000',
    promo_code: '',
  };
}

// One unit of work per scenario. Returns {status, ms, bytes}.
async function step(worker, i) {
  switch (SCENARIO) {
    case 'static':
      return req('GET', staticAssets[i % staticAssets.length]);
    case 'read':
      return req('GET', weighted[(worker.id + i) % weighted.length]);
    case 'tours':
      return req('POST', '/api/tours/', { jar: worker.jar, body: tourBody(`${worker.id}-${i}`) });
    case 'auth': {
      const jar = {};
      const r = await login(jar);
      if (r.status !== 200) return r;
      const me = await req('GET', '/api/auth/me/', { jar });
      const rf = await req('POST', '/api/auth/token/refresh/', { jar, body: {} });
      await req('POST', '/api/auth/logout/', { jar, body: {} });
      return { status: me.status === 200 && rf.status === 200 ? 200 : 500, ms: r.ms + me.ms + rf.ms, bytes: r.bytes + me.bytes + rf.bytes };
    }
    default:
      throw new Error(`unknown scenario ${SCENARIO}`);
  }
}

// ---------- stats ----------
function pct(sorted, p) {
  if (!sorted.length) return 0;
  return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))];
}

/** Assert the API paths really hit Django. nginx's `try_files $uri /index.html`
 *  returns 200 + HTML for any unknown path, which would silently fake a pass. */
async function preflight() {
  const bad = [];
  for (const p of [...new Set(weighted)]) {
    const r = await req('GET', p);
    const looksHtml = r.body.trimStart().startsWith('<');
    if (r.status >= 400 || looksHtml) bad.push(`${p} -> ${r.status}${looksHtml ? ' (HTML/SPA fallback!)' : ''}`);
  }
  if (bad.length) {
    console.error(JSON.stringify({ fatal: 'preflight failed — not measuring Django', bad }));
    process.exit(2);
  }
}

async function run() {
  if (SCENARIO === 'static') await discoverAssets();
  if (SCENARIO === 'read') await preflight();

  // Pre-authenticate tour workers so the CSRF handshake isn't in the hot loop.
  const workers = Array.from({ length: CONC }, (_, id) => ({ id, jar: {} }));
  if (SCENARIO === 'tours') {
    await Promise.all(workers.map((w) => req('GET', '/api/auth/csrf/', { jar: w.jar })));
  }

  const lat = [];
  const statuses = new Map();
  let bytes = 0;
  let warm = false;
  const t0 = Date.now();
  const warmUntil = t0 + WARMUP * 1000;
  const endAt = warmUntil + DURATION * 1000;
  let measureStart = 0;

  await Promise.all(
    workers.map(async (w) => {
      for (let i = 0; Date.now() < endAt; i++) {
        const r = await step(w, i);
        const now = Date.now();
        if (now < warmUntil) continue; // discard warmup
        if (!warm) { warm = true; measureStart = now; }
        lat.push(r.ms);
        bytes += r.bytes;
        const key = r.err ? `ERR:${r.err}` : String(r.status);
        statuses.set(key, (statuses.get(key) || 0) + 1);
      }
    }),
  );

  const elapsed = (Date.now() - (measureStart || warmUntil)) / 1000;
  lat.sort((a, b) => a - b);
  const ok = [...statuses.entries()].filter(([k]) => k.startsWith('2')).reduce((a, [, v]) => a + v, 0);
  const out = {
    label: LABEL,
    target: TARGET,
    scenario: SCENARIO,
    concurrency: CONC,
    seconds: Number(elapsed.toFixed(1)),
    requests: lat.length,
    rps: Number((lat.length / elapsed).toFixed(1)),
    ok_pct: Number(((ok / (lat.length || 1)) * 100).toFixed(1)),
    latency_ms: {
      p50: Number(pct(lat, 50).toFixed(1)),
      p90: Number(pct(lat, 90).toFixed(1)),
      p95: Number(pct(lat, 95).toFixed(1)),
      p99: Number(pct(lat, 99).toFixed(1)),
      max: Number((lat.at(-1) || 0).toFixed(1)),
    },
    throughput_kbps: Number(((bytes / 1024) / elapsed).toFixed(1)),
    statuses: Object.fromEntries([...statuses.entries()].sort()),
  };
  console.log(JSON.stringify(out));
}

// ---------- race: correctness under concurrency ----------
async function race() {
  const n = CONC;
  const jars = [];
  for (let i = 0; i < n; i++) {
    const jar = {};
    const r = await login(jar);
    if (r.status !== 200) { console.log(JSON.stringify({ error: 'login failed', status: r.status, body: r.body.slice(0, 200) })); return; }
    jars.push(jar);
  }
  const spaces = JSON.parse((await req('GET', '/api/spaces/')).body);
  const space = args.space ? spaces.find((s) => s.key === args.space) : spaces.find((s) => s.booking_enabled);
  if (!space) { console.log(JSON.stringify({ error: 'no such space', want: args.space })); return; }

  // `units` is a COUNT (PositiveIntegerField), not a list. With `unit` omitted the
  // server takes the capacity branch: reject once conflicting bookings >= units.
  // So `units` concurrent bookings should succeed and every extra one must fail.
  const payload = {
    space: space.key,
    date: args.date || '2027-03-15',
    duration: 'hourly',
    start_time: '10:00',
    hours: 1,
    attendees: 2,
  };

  const results = await Promise.all(jars.map((jar) => req('POST', '/api/bookings/', { jar, body: payload })));
  const created = results.filter((r) => r.status === 201);
  const limit = space.units || 1;
  const oversold = created.length - limit;
  console.log(JSON.stringify({
    label: 'race:oversell',
    space: space.key,
    units_limit: limit,
    uses_free_hours: space.uses_free_hours,
    attempts: n,
    created_201: created.length,
    oversold_by: oversold,
    verdict: oversold <= 0
      ? `PASS — ${created.length} created, never exceeded units=${limit}`
      : `FAIL — OVERSOLD: ${created.length} bookings created but only ${limit} units exist`,
    statuses: Object.fromEntries(results.reduce((m, r) => m.set(String(r.status), (m.get(String(r.status)) || 0) + 1), new Map())),
    sample_rejection: results.find((r) => r.status !== 201)?.body?.slice(0, 160),
  }));
}

(SCENARIO === 'race' ? race() : run()).catch((e) => {
  console.error(JSON.stringify({ fatal: e.message }));
  process.exit(1);
});
