// Builds public/static/css/app.css from the Tailwind classes used in templates/ and public/static/js/.
//   node tailwind/build.mjs                       (needs the "tailwindcss" npm package, version 4)
// The built file is committed, so the live site needs no Tailwind, Node or CDN.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const require = createRequire(import.meta.url);
const twDir = process.env.TAILWIND_DIR || path.dirname(require.resolve("tailwindcss/package.json", { paths: [root, "/opt/npm-tools"] }));
const { compile } = await import(path.join(twDir, "dist/lib.mjs"));

const files = [];
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).forEach(e => {
  const p = path.join(dir, e.name);
  if (e.isDirectory()) walk(p); else if (/\.(html|js|svg|py)$/.test(e.name)) files.push(p);
});
walk(path.join(root, "templates")); walk(path.join(root, "public/static/js"));
files.push(path.join(root, "icons.py"), path.join(root, "app.py"));
const candidates = new Set();
for (const f of files) for (const t of fs.readFileSync(f, "utf8").split(/[\s"'`<>=]+/)) if (t) candidates.add(t);

const input = path.join(root, "tailwind/input.css");
const compiler = await compile(fs.readFileSync(input, "utf8"), {
  base: path.dirname(input),
  loadStylesheet: async (id, base) => {
    const p = id === "tailwindcss" ? path.join(twDir, "index.css") : path.resolve(base, id);
    return { path: p, base: path.dirname(p), content: fs.readFileSync(p, "utf8") };
  },
  loadModule: async id => { throw new Error(`plugins are not used here: ${id}`); },
});
const css = compiler.build([...candidates]);
const out = path.join(root, "public/static/css/app.css");
fs.writeFileSync(out, css);
console.log(`app.css: ${(css.length / 1024).toFixed(1)} KB from ${files.length} files`);
