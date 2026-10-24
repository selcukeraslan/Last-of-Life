const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function worker(authRequired = false) {
  const handlers = {}, stores = new Map();
  const key = (r) => typeof r === "string" ? r : r.url;
  const caches = {
    keys: async () => [...stores.keys()],
    delete: async (name) => stores.delete(name),
    open: async (name) => {
      if (!stores.has(name)) stores.set(name, new Map());
      const entries = stores.get(name);
      return {
        match: async (r) => entries.get(key(r))?.clone(),
        put: async (r, res) => { entries.set(key(r), res.clone()); },
        delete: async (r) => entries.delete(key(r)),
        keys: async () => [...entries.keys()].map((url) => new Request(url)),
      };
    },
  };
  const context = vm.createContext({
    URL, Request, Response, location: { origin: "https://example.test" }, caches,
    setTimeout: (fn, ms) => setTimeout(fn, ms).unref(),
    self: { addEventListener: (name, fn) => {handlers[name] = fn;}, clients: { matchAll: async () => [], claim: async () => {} } },
    fetch: async () => {throw new Error("offline");},
  });
  const code = fs.readFileSync("app/sw.js", "utf8")
    .replaceAll("__PRECACHE__", "[]").replaceAll("__AUTH_REQUIRED__", String(authRequired));
  vm.runInContext(code, context);
  return {
    stores, context,
    async request(path, options) {
      let response;
      const waits = [];
      const request = new Request("https://example.test" + path, options);
      handlers.fetch({request, waitUntil: (p) => waits.push(p), respondWith: (p) => {response = p;} });
      const result = await (response ?? context.fetch(request));
      await Promise.all(waits);
      return result;
    },
    async activate() {
      const waits = [];
      handlers.activate({waitUntil: (p) => waits.push(p)});
      await Promise.all(waits);
    },
  };
}

test("auth responses never enter cache, even with a legacy cached administrator", async () => {
  const w = worker();
  w.stores.set("api-v1", new Map([["https://example.test/api/auth/me", new Response('{"user":{"role":"admin"}}')]]));
  w.context.fetch = async () => new Response('{"user":null}', {headers: {"Cache-Control": "private, no-store"}});
  assert.equal((await (await w.request("/api/auth/me")).json()).user, null);
  assert.equal(w.stores.has("public-api-v2"), false);
  w.context.fetch = async () => {throw new Error("offline");};
  await assert.rejects(w.request("/api/auth/me"), /offline/);
  await w.activate();
  assert.equal(w.stores.has("api-v1"), false);
});

test("private data is not stored; explicitly public data remains available offline", async () => {
  const w = worker();
  w.context.fetch = async () => new Response("private", {headers: {"Cache-Control": "private, no-store"}});
  await w.request("/api/upcoming");
  assert.equal(w.stores.get("public-api-v2").size, 0);
  w.context.fetch = async () => new Response("public", {headers: {"Cache-Control": "public, s-maxage=60"}});
  await w.request("/api/upcoming");
  w.context.fetch = async () => {throw new Error("offline");};
  assert.equal(await (await w.request("/api/upcoming")).text(), "public");
});

test("logout and login clear API caches before completing", async () => {
  for (const route of ["logout", "login", "register", "reset"]) {
    const w = worker();
    w.stores.set("public-api-v2", new Map());
    w.stores.set("api-v1", new Map());
    w.context.fetch = async () => new Response("ok");
    await w.request(`/api/auth/${route}`, {method: "POST"});
    assert.equal(w.stores.size, 0);
  }
});

test("gated deployments cannot read a previous public API cache", async () => {
  const w = worker(true);
  w.stores.set("public-api-v2", new Map([["https://example.test/api/upcoming", new Response("old")]]));
  await assert.rejects(w.request("/api/upcoming"), /offline/);
  await w.activate();
  assert.equal(w.stores.has("public-api-v2"), false);
});

test("private response removes earlier public value", async () => {
  const w = worker();
  w.context.fetch = async () => new Response("old", {headers: {"Cache-Control": "public"}});
  await w.request("/api/upcoming");
  w.context.fetch = async () => new Response("new", {headers: {"Cache-Control": "private, no-store"}});
  await w.request("/api/upcoming");
  w.context.fetch = async () => {throw new Error("offline");};
  assert.equal((await w.request("/api/upcoming")).status, 503);
});

test('league freshness never falls back to a stale API cache', async () => {
  const w = worker();
  w.stores.set('public-api-v2', new Map([['https://example.test/api/leagues', new Response('{"last_update":"old"}')]]));
  w.context.fetch = async () => new Response('{"last_update":"new"}', {headers:{'Cache-Control':'no-store'}});
  assert.equal((await (await w.request('/api/leagues')).json()).last_update,'new');
  w.context.fetch = async () => {throw new Error('offline');};
  await assert.rejects(w.request('/api/leagues'), /offline/);
});
