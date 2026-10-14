const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("static/app.js", "utf8");
const escDeclaration = source.match(/^const esc = .*;$/m)?.[0];
assert.ok(escDeclaration, "app.js must define its HTML escaping helper");
const context = vm.createContext({});
vm.runInContext(`${escDeclaration}\nglobalThis.htmlEscape = esc;`, context);

test("match IDs are escaped before entering data-match-id", () => {
  const id = `small-7" data-x='x'><img src=x onerror=alert(1)>&`;
  assert.equal(`data-match-id="${context.htmlEscape(id)}"`,
    "data-match-id=\"small-7&quot; data-x=&#39;x&#39;&gt;&lt;img src=x onerror=alert(1)&gt;&amp;\"");
  assert.match(source, /data-match-id="\$\{esc\(detailId\)\}"/);
  assert.match(source, /data-competition-id="\$\{esc\(m\.competition_id \?\? ""\)\}"/);
});

test("small-league picks say they rest on bulletin odds only", () => {
  const Simple = require("../../static/simple.js");
  const info = Simple.info({ small_league: true, pick: { market: "2", odds: 2.1 }, iddaa_odds: {} });
  assert.equal(info.headline, "MS 2");
  assert.equal(info.title, "Deplasman kazanır");
  assert.equal(info.level, 0);
  assert.match(info.reason, /iddaa oranlarındaki favoriye/);
});
