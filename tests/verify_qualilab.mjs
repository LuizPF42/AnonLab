// Confere um .qualilab gerado pelo AnonLab com o PRÓPRIO código do QualiLab. O núcleo do
// servidor MCP do QualiLab-plugin (ql-core.gen.mjs, extraído byte a byte do index.html do app)
// abre o arquivo e responde às ferramentas como responderia a uma IA: documentos, trechos,
// memos, busca. Nenhum dado aceito pode aparecer em resposta nenhuma, a busca por ele não pode
// achar nada, e nenhuma âncora de censura pode estar quebrada (o QualiLab mascararia o
// documento inteiro, o que esconde o dado mas estraga a cópia).
//
//   node tests/verify_qualilab.mjs SAIDA.qualilab DADOS [--plugin PASTA]
//
// DADOS: o codebook do AnonLab (codebook_REIDENTIFICA.csv) ou um JSON com a lista de valores.
// PASTA: plugins/qualilab/server do QualiLab-plugin (padrão: ../QualiLab-plugin/..., ao lado deste repositório).
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : d; };
const plugin = path.resolve(opt("--plugin", path.join(ROOT, "..", "QualiLab-plugin", "plugins", "qualilab", "server")));
const [file, dataFile] = args;
if (!file || !dataFile) { console.error("uso: node tests/verify_qualilab.mjs SAIDA.qualilab DADOS [--plugin PASTA]"); process.exit(2); }

const { lerZip } = await import(pathToFileURL(path.join(plugin, "zip.mjs")));
const { makeQlToolRunner, brokenRedactionAnchor, unpackPdfIndex } = await import(pathToFileURL(path.join(plugin, "ql-core.gen.mjs")));

// carga igual à do main.mjs do plugin
const bruto = fs.readFileSync(file);
const pdfIdx = {};
let db;
if (bruto[0] === 0x50 && bruto[1] === 0x4b) {
  const ent = lerZip(bruto);
  db = JSON.parse(ent.get("project.json").toString("utf8"));
  for (const [n, d] of ent) if (n.startsWith("pdfindex/")) { const p = unpackPdfIndex(d.toString("utf8")); if (p) pdfIdx[n.slice(9, -5)] = p; }
} else db = JSON.parse(bruto.toString("utf8").replace(/^﻿/, ""));
for (const k of ["documents", "categories", "doc_values", "codes", "codings", "memos"]) if (!Array.isArray(db[k])) db[k] = [];

// os valores que não podem aparecer
let dados;
const txt = fs.readFileSync(dataFile, "utf8").replace(/^﻿/, "");
if (dataFile.endsWith(".json")) dados = JSON.parse(txt);
else dados = txt.split(/\r?\n/).slice(1).filter(Boolean).map(l => { const m = /^"[^"]*","((?:[^"]|"")*)"/.exec(l); return m ? m[1].replace(/""/g, '"') : null; }).filter(Boolean);
dados = [...new Set(dados.map(s => s.trim()).filter(s => s.length >= 3))];

const autores = [...new Set(db.codings.map(c => c.author_name).filter(Boolean))].sort();
const { run } = makeQlToolRunner({
  project: { id: db._meta?.id || "file-project", name: db._meta?.name }, projectMode: db._meta?.mode || "individual",
  docs: db.documents, codes: db.codes, cats: db.categories, allCodings: db.codings, allValues: db.doc_values, memos: db.memos,
  coders: autores.map(n => ({ name: n })), pdfIdx,
});

let fails = 0;
const red = new Set(db.codes.filter(c => c.is_redaction).map(c => c.id));
for (const d of db.documents) if (brokenRedactionAnchor(d.content, db.codings.filter(c => c.document_id === d.id), red)) { fails++; console.error("✗ âncora de censura quebrada em «" + d.name + "»"); }

// tudo o que a IA leria
const respostas = [];
const pede = async (nome, a) => { const r = await run(nome, a); respostas.push([nome, JSON.stringify(r)]); return r; };
const paginas = async (nome, a) => { for (let off = 0; off != null; ) off = (await pede(nome, { ...a, offset: off, limit: 500 }))?.next_offset ?? null; };
await pede("get_project", {});
await paginas("list_documents", {});
await paginas("list_codes", {});
await paginas("list_codings", { layer: "all" });
await paginas("list_memos", { scope: "all" });
for (const d of db.documents) for (let s = 0, r; s != null; s = r.next_start) r = await pede("get_document_content", { document_id: d.id, start: s, length: 400000 });

// palavra inteira e com as mesmas maiúsculas: "Rio" não é o "rio" de "escritório", e "Tal"
// (parte de "Tal, Qual & Associados") não é o "tal" da língua
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const achou = (hay, v) => new RegExp("(?<![\\p{L}\\p{N}])" + esc(JSON.stringify(v).slice(1, -1)) + "(?![\\p{L}\\p{N}])", "u").test(hay);
// quem codificou (autoria) não é dado da pessoa pesquisada: fica fora, com aviso
const autoria = new Set([...db.codings, ...db.memos, ...db.doc_values].map(x => x.author_name).concat(db._meta?.displayName).filter(Boolean));
for (const v of dados) {
  if (autoria.has(v)) { console.log(`· «${v}» também é nome de quem codificou (autoria não é pseudonimizada)`); continue; }
  const onde = respostas.filter(r => achou(r[1].normalize("NFC"), v.normalize("NFC"))).map(r => r[0]);
  if (onde.length) { fails++; console.error(`✗ «${v}» aparece em: ${[...new Set(onde)].join(", ")}`); }
  const busca = await run("search_corpus", { query: v, limit: 5, whole_word: true, case_sensitive: true });
  const n = busca?.total ?? busca?.items?.length ?? 0;
  if (n) { fails++; console.error(`✗ a busca por «${v}» acha ${n} ocorrência(s)`); }
}
const nCens = db.codings.filter(c => red.has(c.code_id)).length;
console.log(`${path.basename(file)}: ${db.documents.length} documento(s), ${nCens} trecho(s) de censura, ${dados.length} valor(es) conferido(s) em ${respostas.length} resposta(s) + busca`);
console.log(fails ? `\n${fails} problema(s)` : "\nOK — nada do que foi aceito chega à IA pelo QualiLab");
process.exit(fails ? 1 : 0);
