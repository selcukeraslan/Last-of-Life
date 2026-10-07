const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("static/app.js", "utf8");
const escDeclaration = source.match(/^const esc = .*;$/m)?.[0];
assert.ok(escDeclaration, "app.js must define its HTML escaping helper");
const context = vm.createContext({});
vm.runInContext(`${escDeclaration}\nglobalThis.htmlEscape = esc;`, context);

test("small recommendation IDs are escaped before entering data-id", () => {
  const id = `small-7" data-x='x'><img src=x onerror=alert(1)>&`;
  const attribute = `data-id="${context.htmlEscape(id)}"`;

  assert.equal(attribute,
    "data-id=\"small-7&quot; data-x=&#39;x&#39;&gt;&lt;img src=x onerror=alert(1)&gt;&amp;\"");
  assert.match(source, /data-id="\$\{esc\(p\.id\)\}"/);
});
