// Testa o bloco <script id="ner-core"> do anonimizador.html contra vetores
// gerados em Python com o tokenizador/modelo originais do Hugging Face.
//
//   node tests/test_ner_core.mjs [--pack dist/anonlab-ner] [--core arquivo.js]
//
// Vetores: uv run tools/build_ner_pack.py --vectors tests/vectors [--vectors-only]
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const arg = (name, def) => {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : def;
};
const PACK = path.resolve(ROOT, arg("--pack", "dist/anonlab-ner"));
const CORE = arg("--core", null);

function loadCore() {
  let src;
  if (CORE) src = fs.readFileSync(CORE, "utf8");
  else {
    const html = fs.readFileSync(path.join(ROOT, "anonimizador.html"), "utf8");
    const m = html.match(/<script id="ner-core">([\s\S]*?)<\/script>/);
    if (!m) throw new Error('bloco <script id="ner-core"> não encontrado no anonimizador.html');
    src = m[1];
  }
  const ctx = vm.createContext({});
  vm.runInContext(src + "\nthis.NerCore = NerCore;", ctx);
  return ctx.NerCore;
}

// offsets do Python são em code points; os do JS, em unidades UTF-16
function cpToUtf16(text) {
  const map = [0];
  let u = 0;
  for (const ch of text) { u += ch.length; map.push(u); }
  return map;
}

const NerCore = loadCore();
const vecDir = path.join(ROOT, "tests", "vectors");
const files = fs.existsSync(vecDir) ? fs.readdirSync(vecDir).filter(f => f.endsWith(".json")) : [];
if (!files.length) { console.error("sem vetores em tests/vectors — gere com tools/build_ner_pack.py --vectors"); process.exit(2); }

let fails = 0, checks = 0;
const fail = (msg) => { fails++; if (fails <= 25) console.error("  ✗ " + msg); };

for (const f of files) {
  const vec = JSON.parse(fs.readFileSync(path.join(vecDir, f), "utf8"));
  const slug = f.replace(/\.json$/, "");
  const tokPath = path.join(PACK, "models", slug, "tokenizer.json");
  if (!fs.existsSync(tokPath)) { console.error(`sem ${tokPath} — gere o pacote antes`); process.exit(2); }
  const tok = NerCore.createTokenizer(JSON.parse(fs.readFileSync(tokPath, "utf8")));
  const id2label = vec.id2label;
  console.log(`${slug}: ${vec.cases.length} casos (${vec.model} @ ${vec.revision.slice(0, 8)})`);

  for (const [ci, c] of vec.cases.entries()) {
    const tag = `caso ${ci} ${JSON.stringify(c.text.slice(0, 40))}`;
    const enc = tok.encode(c.text);
    const map = cpToUtf16(c.text);
    checks++;
    if (enc.length !== c.ids.length) { fail(`${tag}: ${enc.length} tokens, esperado ${c.ids.length}`); }
    const n = Math.min(enc.length, c.ids.length);
    let bad = 0;
    for (let i = 0; i < n && bad < 3; i++) {
      const [ps, pe] = c.offsets[i];
      const wid = c.word_ids[i] ?? -1;
      if (enc.ids[i] !== c.ids[i] || enc.start[i] !== map[ps] || enc.end[i] !== map[pe]) {
        bad++;
        fail(`${tag} tok ${i}: JS id=${enc.ids[i]} [${enc.start[i]},${enc.end[i]}) · HF id=${c.ids[i]} [${map[ps]},${map[pe]})`);
      }
      // a numeração absoluta das palavras pode diferir; o que importa é a fronteira
      if (i > 0 && (enc.word[i] === enc.word[i - 1]) !== (wid === (c.word_ids[i - 1] ?? -1))) {
        bad++;
        fail(`${tag} tok ${i}: fronteira de palavra diverge`);
      }
    }
    if (c.tokenizer_only || enc.length !== c.ids.length) continue;

    checks++;
    const wins = NerCore.windowsFor(enc.length, vec.max_length, vec.stride);
    if (JSON.stringify(wins) !== JSON.stringify(c.windows)) fail(`${tag}: janelas ${JSON.stringify(wins)} ≠ ${JSON.stringify(c.windows)}`);
    if (c.token_windows) {
      checks++;
      const i = c.token_windows.findIndex((w, k) => NerCore.bestWindow(k, wins) !== w);
      if (i >= 0) fail(`${tag}: token ${i} usa janela ${NerCore.bestWindow(i, wins)}, esperado ${c.token_windows[i]}`);
      checks++;
      const all = NerCore.assignWindows(enc.length, wins);
      const j = c.token_windows.findIndex((w, k) => all[k] !== w);
      if (j >= 0) fail(`${tag}: assignWindows token ${j} = ${all[j]}, esperado ${c.token_windows[j]}`);
    }

    checks++;
    const ents = NerCore.aggregateFirst(enc, Int32Array.from(c.token_labels), Float32Array.from(c.token_scores), id2label);
    const exp = c.entities.map(e => ({ ...e, start: map[e.start], end: map[e.end] }));
    const key = e => `${e.label}@${e.start}-${e.end}`;
    const got = new Map(ents.map(e => [key(e), e]));
    for (const e of exp) {
      const g = got.get(key(e));
      if (!g) fail(`${tag}: faltou ${key(e)} ${JSON.stringify(c.text.slice(e.start, e.end))}`);
      else if (Math.abs(g.score - e.score) > 1e-4) fail(`${tag}: score ${key(e)} ${g.score} ≠ ${e.score}`);
    }
    if (ents.length !== exp.length) fail(`${tag}: ${ents.length} entidades, esperado ${exp.length}`);
  }
}

console.log(fails ? `\n${fails} falha(s) em ${checks} verificações` : `\nOK — ${checks} verificações`);
process.exit(fails ? 1 : 0);
