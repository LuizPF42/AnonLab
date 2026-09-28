// Testa o bloco <script id="formats"> do anonimizador.html: CSV, zip, NFC, reancoramento de
// offsets e as duas saídas do .qualilab (censurar / destruir).
//
//   node tests/test_formats.mjs
//
// O projeto QualiLab de teste é montado aqui mesmo (offsets calculados com indexOf), com os
// casos que importam: trecho codificado que contém, corta ou encosta num dado pessoal,
// censura já existente, memo, categoria de opções, conversa de IA, histórico e espelho.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(ROOT, "anonimizador.html"), "utf8");
const src = html.match(/<script id="formats">([\s\S]*?)<\/script>/)?.[1];
if (!src) throw new Error('bloco <script id="formats"> não encontrado');
const ctx = vm.createContext({ TextDecoder, TextEncoder, Blob, Response, CompressionStream, DecompressionStream, crypto, structuredClone, console });
vm.runInContext(src + "\nthis.Formats = Formats;", ctx);
const F = ctx.Formats;

let fails = 0, checks = 0;
const ok = (cond, msg) => { checks++; if (!cond) { fails++; console.error("  ✗ " + msg); } };
const eq = (a, b, msg) => ok(JSON.stringify(a) === JSON.stringify(b), `${msg}: ${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`);
const section = s => console.log(s);
// objetos do contexto vm têm outro Object.prototype: normalizar antes de comparar
const plain = x => JSON.parse(JSON.stringify(x));

/* ---------- texto ---------- */
section("texto");
{
  const u = F.decodeText(new Uint8Array([0xEF, 0xBB, 0xBF, ...new TextEncoder().encode("João")]));
  eq([u.text, u.encoding, u.bom], ["João", "utf-8", true], "UTF-8 com BOM");
  const w = F.decodeText(new Uint8Array([0x4A, 0x6F, 0xE3, 0x6F]));      // "João" em Windows-1252
  eq([w.text, w.encoding], ["João", "windows-1252"], "Windows-1252");
  const nfd = "João é de São Paulo";                 // "João é de São Paulo" decomposto
  const v = F.nfcView(nfd);
  eq(v.text, nfd.normalize("NFC"), "nfcView normaliza");
  const i = v.text.indexOf("São Paulo");
  const o = [F.toOrig(v, i, false), F.toOrig(v, i + "São Paulo".length, true)];
  eq(nfd.slice(o[0], o[1]).normalize("NFC"), "São Paulo", "toOrig volta ao original");
  const same = F.nfcView("já NFC");
  ok(same.starts === null && F.toOrig(same, 3, true) === 3, "texto já em NFC: identidade");
}

/* ---------- reancoramento ---------- */
section("reancoramento");
{
  // propriedade: trecho codificado que não encosta em nada trocado mantém o texto; o que
  // encosta passa a conter o rótulo inteiro, e nunca sobra meio dado pessoal
  let seed = 7; const rnd = n => (seed = (seed * 1103515245 + 12345) % 2147483648) % n;
  for (let t = 0; t < 300; t++) {
    const text = [...Array(60 + rnd(60))].map(() => "abcdefgh  ."[rnd(11)]).join("");
    const reps = []; let p = rnd(5);
    while (p < text.length - 2) { const len = 1 + rnd(6), s = p, e = Math.min(text.length, p + len); reps.push({ start: s, end: e, label: "[X" + reps.length + "]" }); p = e + 1 + rnd(12); }
    const r = F.replaceSpans(text, reps);
    for (let k = 0; k < 20; k++) {
      const a = rnd(text.length), b = a + rnd(text.length - a + 1);
      const s = r.mapStart(a), e = Math.max(s, r.mapEnd(b)), q = r.text.slice(s, e);
      const touches = reps.filter(x => x.start < b && a < x.end);
      if (!touches.length) ok(q === text.slice(a, b) || a === b, `sem dado: "${text.slice(a, b)}" virou "${q}"`);
      for (const x of touches) ok(q.includes(x.label), `com dado: "${q}" sem o rótulo inteiro ${x.label}`);
    }
  }
  const r = F.replaceSpans("Maria Souza disse", [{ start: 0, end: 11, label: "[PESSOA_1]" }]);
  eq([r.text, r.mapStart(6), r.mapEnd(11), r.mapStart(11), r.mapEnd(17)], ["[PESSOA_1] disse", 0, 10, 10, 16], "casos de borda");
}

/* ---------- CSV ---------- */
section("CSV");
{
  const cases = [
    ["nome;resposta\r\nMaria;\"gostei, muito\"\r\nJoão;\"disse \"\"não\"\"\r\nsegunda linha\"\r\n", ";"],
    ["a,b,c\n1,2,3\n\n4,,6", ","],
    ["x\ty\n\"a\tb\"\tc\n", "\t"],
    ["só uma coluna\nlinha 2\n", ","],
    ["a;b;\n;;\n", ";"],
  ];
  for (const [text, d] of cases) {
    eq(F.sniffDelimiter(text), d, "separador de " + JSON.stringify(text.slice(0, 20)));
    const csv = F.parseCSV(text, d);
    eq(F.writeCSV(csv, d), text, "ida e volta de " + JSON.stringify(text.slice(0, 20)));
  }
  const csv = F.parseCSV(cases[0][0], ";");
  eq(plain(csv.rows.map(r => r.map(c => c.v))), [["nome", "resposta"], ["Maria", "gostei, muito"], ["João", "disse \"não\"\r\nsegunda linha"]], "células");
  eq(csv.eol, "\r\n", "fim de linha CRLF");
  // resposta aberta com vírgulas num CSV de ";": a vírgula dentro de aspas não confunde
  eq(F.sniffDelimiter('id;texto\n1;"a, b, c"\n2;"d, e"\n3;f\n'), ";", "vírgula entre aspas não conta");
}

/* ---------- zip ---------- */
section("zip");
{
  const big = new TextEncoder().encode(JSON.stringify({ a: "x".repeat(5000), b: [1, 2, 3] }));
  const bin = new Uint8Array(3000).map((_, i) => (i * 37) & 255);
  const z = await F.writeZip([{ name: "project.json", data: big }, { name: "pdfs/d1.pdf", data: bin, store: true }, { name: "vazio.txt", data: new Uint8Array(0) }]);
  const back = await F.readZip(z);
  eq([...back.keys()], ["project.json", "pdfs/d1.pdf", "vazio.txt"], "entradas");
  ok(Buffer.from(back.get("project.json")).equals(Buffer.from(big)), "json (deflate) volta igual");
  ok(Buffer.from(back.get("pdfs/d1.pdf")).equals(Buffer.from(bin)), "pdf (store) volta igual");
  ok(z.length < big.length, "json foi comprimido");
  eq(F.crc32(new TextEncoder().encode("123456789")), 0xCBF43926, "crc32");
  const bad = z.slice(); bad[30 + "project.json".length + 5] ^= 0xFF;   // mexe nos dados do primeiro arquivo
  let threw = false; try { await F.readZip(bad); } catch (_) { threw = true; }
  ok(threw, "zip corrompido é recusado");
}

/* ---------- QualiLab ---------- */
section("QualiLab");
const T1 = "Entrevista com Maria Souza, CPF 529.982.247-25, moradora da Rua das Flores, nº 120, em Recife.\n" +
           "Ela trabalha na Tecidos Brasil Ltda. Maria Souza disse que o chefe, João Pereira, a apoiou.";
const T2 = "João Pereira confirmou. O e-mail dele é joao.pereira@email.com, e Maria Souza não.";
const at = (t, s, k = 0) => { let i = -1; for (let n = 0; n <= k; n++) i = t.indexOf(s, i + 1); if (i < 0) throw new Error(s); return i; };
const coding = (id, doc, t, code, a, b) => ({ id, document_id: doc, code_id: code, span_start: a, span_end: b, quote: t.slice(a, b), layer: "individual",
  created_by: null, author_name: "Ana", created_at: "2026-01-01T00:00:00Z", pdf_region: null, source: "manual" });
const PII = ["Maria Souza", "529.982.247-25", "Rua das Flores, nº 120", "Recife", "Tecidos Brasil Ltda", "João Pereira", "joao.pereira@email.com"];
const PREFIX = { "Maria Souza": "PESSOA", "529.982.247-25": "CPF", "Rua das Flores, nº 120": "ENDERECO", "Recife": "CIDADE", "Tecidos Brasil Ltda": "ORG", "João Pereira": "PESSOA", "joao.pereira@email.com": "EMAIL" };
const LABEL = { "Maria Souza": "[PESSOA_1]", "529.982.247-25": "[CPF_1]", "Rua das Flores, nº 120": "[ENDERECO_1]", "Recife": "[CIDADE_1]", "Tecidos Brasil Ltda": "[ORG_1]", "João Pereira": "[PESSOA_2]", "joao.pereira@email.com": "[EMAIL_1]" };
function miniProject() {
  const mOff = at(T1, "Maria Souza"), cutA = at(T1, "Souza disse"), cutB = at(T1, "chefe") + 5;
  return {
    _meta: { id: "file-project", name: "Mini — Maria Souza", code: "FILE", mode: "collective", displayName: "Ana", restrict_ai: "none", ai_ever_enabled: false },
    documents: [
      { id: "d1", name: "ENT-01 — Maria Souza (Recife)", content: T1, created_at: "2026-01-01T00:00:00Z", has_pdf: false },
      { id: "d2", name: "ENT-02", content: T2, created_at: "2026-01-01T00:00:00Z", has_pdf: true },
    ],
    categories: [
      { id: "c1", position: 0, name: "Empresa", kind: "select", options: ["Tecidos Brasil Ltda", "Outra"], description: "", color: 0 },
      { id: "c2", position: 1, name: "Resumo", kind: "text", options: [], description: "", color: 0 },
      { id: "c3", position: 2, name: "Áreas", kind: "checkbox", options: ["Tecidos Brasil Ltda", "Vendas"], description: "", color: 0 },
      { id: "c4", position: 3, name: "Idade", kind: "number", options: [], description: "", color: 0 },
    ],
    doc_values: [
      { id: "v1", document_id: "d1", category_id: "c1", value: "Tecidos Brasil Ltda", set_by: null, author_name: "Ana", layer: "final" },
      { id: "v2", document_id: "d1", category_id: "c2", value: "Maria Souza fala do trabalho em Recife.", set_by: null, author_name: "Ana", layer: "final" },
      { id: "v3", document_id: "d1", category_id: "c3", value: "Tecidos Brasil Ltda | Vendas", set_by: null, author_name: "Ana", layer: "final" },
      { id: "v4", document_id: "d1", category_id: "c4", value: "42", set_by: null, author_name: "Ana", layer: "final" },
    ],
    codes: [
      { id: "k1", position: 0, parent_id: null, name: "Trabalho", hue: 0, depth: 0, hue_deg: null, sat: null, is_redaction: false, pos_x: null, pos_y: null },
      { id: "k2", position: 1, parent_id: null, name: "Censura", hue: 1, depth: 0, hue_deg: -2, sat: null, is_redaction: true, pos_x: null, pos_y: null },
      { id: "k3", position: 2, parent_id: "k2", name: "Nomes", hue: 1, depth: 1, hue_deg: -2, sat: null, is_redaction: true, pos_x: null, pos_y: null },
      { id: "k4", position: 3, parent_id: null, name: "Fala de João Pereira", hue: 2, depth: 0, hue_deg: null, sat: null, is_redaction: false, pos_x: null, pos_y: null },
    ],
    codings: [
      coding("g1", "d1", T1, "k1", at(T1, "Ela trabalha"), at(T1, "Ltda.") + 5),                 // contém o dado pessoal
      coding("g2", "d1", T1, "k3", mOff, mOff + "Maria Souza".length),                           // censura já existente
      coding("g3", "d1", T1, "k1", cutA, cutB),                                                  // começa no meio de um nome
      coding("g4", "d1", T1, "k1", at(T1, "a apoiou"), at(T1, "a apoiou") + 8),                  // sem dado pessoal
      coding("g5", "d2", T2, "k1", at(T2, "confirmou"), at(T2, "confirmou") + 9),
      coding("g6", "d1", T1, "k1", at(T1, "Recife"), at(T1, "Recife") + 6),                      // exatamente o dado
    ],
    memos: [{ id: "m1", project_id: "file-project", scope: "document", target_id: "d1", content: "A Maria Souza pediu sigilo sobre a Tecidos Brasil Ltda.", label: "", author_name: "Ana", updated_at: "2026-01-01T00:00:00Z" }],
    ia_results: [{ id: "r1", project_id: "file-project", scope: "project", mode_label: "Analisar", result: JSON.stringify({ texto: "Maria Souza e João Pereira discordam." }), author_name: "Ana", created_at: "2026-01-01T00:00:00Z" }],
    ia_memory: [{ id: "y1", project_id: "file-project", content: "João Pereira é o chefe.", reason: "", source: "ai", active: true, ai_model: "x", mode_label: "", author_name: "Ana", created_at: "2026-01-01T00:00:00Z" }],
    activity: [
      { project_id: "file-project", created_at: "2026-01-01T00:00:00Z", id: "a1", op: "trail_started", target_kind: null, target_id: null, target_name: null, layer: null, detail: {}, actor: null, actor_name: "Ana", at: "2026-01-01T00:00:00Z" },
      { project_id: "file-project", created_at: "2026-01-01T00:00:00Z", id: "a2", op: "text_edited", target_kind: "document", target_id: "d1", target_name: "ENT-01 — Maria Souza (Recife)", layer: null, detail: { remapped: 0, affected: 0 }, actor: null, actor_name: "Ana", at: "2026-01-01T00:00:00Z" },
    ],
    link_relations: [{ id: "lr1", name: "apoia", direction: "forward" }],
    links: [{ id: "l1", relation_id: "lr1", origin_kind: "code", origin_id: "k1", target_kind: "code", target_id: "k4", comment: "Como a Maria Souza descreve", color: null, evidence_coding_id: "g1", created_by: null, author_name: "Ana", created_at: "2026-01-01T00:00:00Z" }],
    disagreements: [{ id: "x1", document_id: "d1", code_id: "k1", span_start: at(T1, "João Pereira, a"), span_end: at(T1, "a apoiou") + 8, quote: T1.slice(at(T1, "João Pereira, a"), at(T1, "a apoiou") + 8), created_by: null, author_name: "Ana", created_at: "2026-01-01T00:00:00Z" }],
    snapshots: [{ meta: { id: "s1" }, json: JSON.stringify({ documents: [{ content: T1 }] }) }],
  };
}
// o que a detecção entregaria: toda ocorrência de cada dado, em cada segmento
function planFor(db, mode, meta = true) {
  const reps = new Map();
  for (const s of F.qualilabSegments(db)) {
    const list = [];
    for (const v of PII) for (let i = s.text.indexOf(v); i >= 0; i = s.text.indexOf(v, i + 1)) list.push({ start: i, end: i + v.length, label: LABEL[v], prefix: PREFIX[v] });
    list.sort((a, b) => a.start - b.start);
    if (list.length) reps.set(s.key, list);
  }
  const subst = x => { let t = String(x); for (const v of [...PII].sort((a, b) => b.length - a.length)) t = t.split(v).join(LABEL[v]); return t; };
  return { mode, meta, reps, subst, code: "new", typeName: p => ({ PESSOA: "Pessoas", CPF: "CPF", ENDERECO: "Endereços", CIDADE: "Cidades", ORG: "Organizações", EMAIL: "E-mails" }[p] || p), author: "AnonLab", now: "2026-09-28T12:00:00Z" };
}
const quotesOk = db => db.codings.concat(db.disagreements || []).every(c => {
  const d = db.documents.find(x => x.id === c.document_id);
  return c.quote === d.content.slice(c.span_start, c.span_end) && c.span_start <= c.span_end && c.span_end <= d.content.length;
});
{
  const db0 = miniProject();
  const pdf = new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52, 10, 1, 2, 3]);   // "%PDF-1.4\n…"
  const zipped = await F.writeZip([{ name: "project.json", data: new TextEncoder().encode(JSON.stringify(db0)) },
    { name: "pdfs/d2.pdf", data: pdf, store: true }, { name: "pdfindex/d2.json", data: new TextEncoder().encode('{"v":1}') }]);
  const src = await F.readQualilab(zipped);
  ok(src.zipped && src.pdfs.has("d2") && src.pdfIndex.has("d2"), "lê o .qualilab em zip (PDF e índice)");
  const plainSrc = await F.readQualilab(new TextEncoder().encode(JSON.stringify(db0)));
  ok(!plainSrc.zipped && plainSrc.db.documents.length === 2, "lê o .qualilab em JSON");
  const segs = F.qualilabSegments(src.db);
  eq(segs.map(s => s.key), ["doc:d1", "doc:d2", "name:d1", "name:d2", "memo:0", "opt:c1:0", "opt:c1:1", "opt:c3:0", "opt:c3:1", "val:1", "link:0", "project"], "segmentos");

  // --- censurar ---
  const cen = F.buildQualilab(src, planFor(src.db, "censor"));
  const c = cen.db;
  ok(quotesOk(c), "censura: todo quote é a fatia do texto");
  eq(c.documents.map(d => d.content), [T1, T2], "censura: o texto fica intacto");
  eq(plain(c.codings.slice(0, 6)), plain(db0.codings), "censura: trechos antigos intactos");
  const fam = c.codes.find(x => x.name === F.RED_FAMILY);
  ok(fam && fam.is_redaction && fam.hue_deg === -2 && !fam.parent_id, "censura: família nova, is_redaction, preta");
  const kids = c.codes.filter(x => x.parent_id === fam?.id);
  ok(kids.length >= 5 && kids.every(k => k.is_redaction && k.depth === 1 && k.hue_deg === -2), "censura: um subcódigo por tipo");
  ok(!c.codings.some(x => x.code_id === fam?.id), "censura: a família não recebe trechos");
  const novos = c.codings.slice(6);
  const body = [...planFor(src.db, "censor").reps].filter(([k]) => k.startsWith("doc:")).reduce((a, [, l]) => a + l.length, 0);
  eq(novos.length + cen.stats.already, body, "censura: um trecho por ocorrência");
  eq(cen.stats.already, 1, "censura: não repete o que já estava censurado");
  ok(novos.every(x => x.layer === "final" && x.author_name === "AnonLab" && x.source === "manual"), "censura: camada final, autor AnonLab");
  ok(!("snapshots" in c), "censura: espelhos fora");
  eq(c.documents.map(d => d.name), ["ENT-01 — [PESSOA_1] ([CIDADE_1])", "ENT-02"], "censura: títulos pseudonimizados");
  eq(c.categories[0].options, ["[ORG_1]", "Outra"], "censura: opções pseudonimizadas");
  eq(c.doc_values.map(v => v.value), ["[ORG_1]", "[PESSOA_1] fala do trabalho em [CIDADE_1].", "[ORG_1] | Vendas", "42"], "censura: valores coerentes com as opções");
  eq(c.codes.find(x => x.id === "k4").name, "Fala de [PESSOA_2]", "censura: nome de código");
  ok(!JSON.stringify([c.ia_results, c.ia_memory, c.activity, c.memos, c.links]).match(/Maria Souza|João Pereira|Tecidos Brasil/), "censura: IA, histórico, memos e conexões sem dado");
  eq(c.activity.at(-1).op, "bulk_coding", "censura: registrado no histórico");
  const out = await F.writeQualilab(c, src, "censor");
  const re = await F.readQualilab(out);
  ok(re.zipped && re.pdfs.has("d2") && Buffer.from(re.pdfs.get("d2")).equals(Buffer.from(pdf)), "censura: o PDF original vai junto");
  const noMeta = F.buildQualilab(src, planFor(src.db, "censor", false)).db;
  eq(noMeta.documents[0].name, db0.documents[0].name, "censura sem 'meta': título fica");
  // código existente escolhido
  const plan2 = { ...planFor(src.db, "censor"), code: "k3" };
  const c2 = F.buildQualilab(src, plan2).db;
  ok(c2.codings.slice(6).every(x => x.code_id === "k3") && !c2.codes.some(x => x.name === F.RED_FAMILY), "censura: usa o código escolhido");
  // rodar de novo sobre o censurado não duplica
  const again = F.buildQualilab({ ...src, db: c }, planFor(c, "censor"));
  eq(again.stats.coded, 0, "censura de novo: nada a acrescentar");

  // --- destruir ---
  const des = F.buildQualilab(src, planFor(src.db, "destroy"));
  const d = des.db;
  ok(quotesOk(d), "destruição: todo quote é a fatia do texto novo");
  eq(d.codings.length, db0.codings.length, "destruição: nenhum trecho some");
  const json = JSON.stringify(d);
  for (const v of PII) ok(!json.includes(v), "destruição: sobrou " + v);
  eq(d.codings.find(x => x.id === "g4").quote, "a apoiou", "destruição: trecho sem dado mantém o texto");
  eq(d.codings.find(x => x.id === "g6").quote, "[CIDADE_1]", "destruição: trecho igual ao dado vira o rótulo");
  eq(d.codings.find(x => x.id === "g3").quote, "[PESSOA_1] disse que o chefe", "destruição: trecho que cortava o nome cobre o rótulo inteiro");
  ok(d.codings.find(x => x.id === "g1").quote.includes("[ORG_1]"), "destruição: trecho que contém o dado");
  eq(d.disagreements[0].quote, "[PESSOA_2], a apoiou", "destruição: discordâncias reancoradas");
  ok(d.documents.every(x => !x.has_pdf) && d.codings.every(x => x.pdf_region === null), "destruição: sem PDF");
  const outD = await F.writeQualilab(d, src, "destroy");
  ok(outD[0] === 0x7B, "destruição: sai em JSON puro (sem o PDF)");
  eq(d.activity.filter(a => a.op === "text_edited" && a.actor_name === "AnonLab").length, 2, "destruição: histórico por documento");
  ok(/pseudonimizado \(AnonLab\)$/.test(d._meta.name) && !d._meta.name.includes("Maria"), "destruição: nome do projeto");

  // --out PASTA: grava as duas saídas e a lista de dados, para o tests/verify_qualilab.mjs
  // conferir com o código do próprio QualiLab
  const i = process.argv.indexOf("--out");
  if (i > 0) {
    const dir = path.resolve(process.argv[i + 1]); fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "mini_censurado.qualilab"), out);
    fs.writeFileSync(path.join(dir, "mini_pseudonimizado.qualilab"), outD);
    fs.writeFileSync(path.join(dir, "mini_dados.json"), JSON.stringify(PII));
    // controles: o verificador tem que acusar o original e a censura sem os títulos/memos
    fs.writeFileSync(path.join(dir, "controle_original.qualilab"), JSON.stringify(db0));
    fs.writeFileSync(path.join(dir, "controle_censura_sem_meta.qualilab"), JSON.stringify(noMeta));
    console.log("gravado em " + dir);
  }
}

console.log(fails ? `\n${fails} falha(s) em ${checks} verificações` : `\nOK — ${checks} verificações`);
process.exit(fails ? 1 : 0);
