const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("static/app.js", "utf8");
const escDeclaration = source.match(/^const esc = .*;$/m)?.[0];
assert.ok(escDeclaration, "app.js must define its HTML escaping helper");
const context = vm.createContext({});
vm.runInContext(`${escDeclaration}\nglobalThis.htmlEscape = esc;`, context);

test("small recommendation IDs are escaped before entering data-match-id", () => {
  const id = `small-7" data-x='x'><img src=x onerror=alert(1)>&`;
  const attribute = `data-match-id="${context.htmlEscape(id)}"`;

  assert.equal(attribute,
    "data-match-id=\"small-7&quot; data-x=&#39;x&#39;&gt;&lt;img src=x onerror=alert(1)&gt;&amp;\"");
  assert.match(source, /data-match-id="\$\{esc\(p\.id\)\}"/);
  assert.match(source, /data-competition-id="\$\{esc\(p\.competition_id \?\? ""\)\}"/);
});

test("small recommendations disclose that the probability is market-only", () => {
  assert.match(source, /recommendation_source === "iddaa_market"/);
  assert.match(source, /piyasa olasılığı gösterilir/);
  assert.match(source, /Model verisi yok/);
});
