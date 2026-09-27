#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.24"]
# ///
"""
Publica no Hugging Face os modelos de um pacote NER (dist/anonlab-ner/), para o
anonimizador.html baixá-los direto no navegador ("🌐 Baixar modelos").

    hf auth login                                   # uma vez, token com permissão de escrita
    uv run tools/publish_hub.py --user SEU_USUARIO_HF
    uv run tools/publish_hub.py --user SEU_USUARIO_HF --dry-run

Cria um repositório por modelo (<usuário>/<slug>-onnx) com os ONNX, o
tokenizador, o manifesto do AnonLab e um model card que credita o modelo
original. No fim, acrescenta ao catálogo do anonimizador.html (NER_HUB) o commit
publicado, para o navegador baixar sempre exatamente esses arquivos.

Não é preciso para usar o AnonLab: o padrão já usa modelos que outras pessoas
publicaram em ONNX. Serve para acrescentar modelos que só existem em PyTorch
(como o legal-bert-lgpd).

Só publica derivados de modelos com licença declarada no Hugging Face (use
--allow-unlicensed por sua conta e risco).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
         "vocab.txt", "anonlab-model.json"]

CARD = """---
license: {license}
language: pt
library_name: transformers.js
pipeline_tag: token-classification
base_model: {hf_id}
tags:
- onnx
- transformers.js
- token-classification
- ner
- anonymization
- portuguese
- anonlab
---

# {slug} — ONNX para o navegador (AnonLab)

> ⚠️ **Experimental, sem nenhuma garantia.** Conversão feita para o
> [AnonLab](https://github.com/LuizPF42/AnonLab), anonimizador que roda
> inteiramente no navegador. O modelo erra; ele **não garante anonimização**.
> Revise sempre o resultado.

Conversão para ONNX de **[{hf_id}](https://huggingface.co/{hf_id})** (revisão
`{revision}`), para rodar com [transformers.js](https://github.com/huggingface/transformers.js)
em WebGPU ou WebAssembly.

**Todo o crédito do modelo é dos autores originais**: veja
[{hf_id}](https://huggingface.co/{hf_id}) e o `ORIGINAL_MODEL_CARD.md` deste
repositório. Licença do original: **{license}**. Esta conversão só muda o
formato (ONNX) e a precisão numérica; os pesos são os do original.

## Variantes

| arquivo | dtype | tamanho | F1 de entidades vs. PyTorch fp32 |
|---|---|---|---|
{variants}

Medido em {texts} textos (~{tokens} tokens) com as mesmas janelas nos dois
lados. Variantes reprovadas na validação não são publicadas.

## Rótulos

{labels}

## Uso

```js
import {{ AutoModelForTokenClassification }} from "@huggingface/transformers";
const model = await AutoModelForTokenClassification.from_pretrained("{repo}", {{ device: "webgpu", dtype: "{first}" }});
```

O AnonLab não usa o pipeline de NER do transformers.js (ele não devolve as
posições no texto): tem tokenizador e agregação próprios, descritos em
`anonlab-model.json` e testados contra o tokenizador original.
"""


def model_card(meta: dict, repo: str) -> str:
    val = meta.get("validation", {})
    rows = []
    for dtype, v in meta["variants"].items():
        f1 = val.get(dtype, {}).get("entity_f1_vs_fp32")
        rows.append(f"| `{v['file']}` | {dtype} | {v['size'] / 2**20:.0f} MB | {f1 if f1 is not None else '—'} |")
    tags = sorted({l[2:] if l[1:2] == "-" else l for l in meta["id2label"].values() if l != "O"})
    corpus = val.get("corpus", {})
    return CARD.format(
        license=meta["source"].get("license") or "other", hf_id=meta["source"]["hf_id"],
        revision=meta["source"]["revision"], slug=meta["slug"], repo=repo,
        variants="\n".join(rows), texts=corpus.get("texts", "?"), tokens=corpus.get("tokens", "?"),
        labels=", ".join(f"`{t}`" for t in tags), first=next(iter(meta["variants"])))


def update_html(published: list[tuple[str, str]]) -> None:
    """Acrescenta (ou atualiza a revisão de) cada repositório no catálogo NER_HUB, sem
    tirar os que já estão lá (ex.: os modelos de terceiros do padrão)."""
    html = ROOT / "anonimizador.html"
    s = html.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in s else "\n"
    head = re.compile(r"const NER_HUB = \{\r?\n  host: \"[^\"]*\",\r?\n  models: \[\r?\n")
    if not head.search(s):
        print("  aviso: não achei o bloco NER_HUB no anonimizador.html; acrescente à mão:")
        for repo, rev in published:
            print(f'    {{repo:"{repo}", revision:"{rev}"}},')
        return
    for repo, rev in published:
        entry = re.compile(r'(repo:"' + re.escape(repo) + r'",\s*revision:")[^"]*(")')
        if entry.search(s):
            s = entry.sub(lambda m: m.group(1) + rev + m.group(2), s, count=1)
        else:
            m = head.search(s)
            s = s[:m.end()] + f'    {{repo:"{repo}", revision:"{rev}"}},{nl}' + s[m.end():]
    html.write_text(s, encoding="utf-8")
    print(f"  anonimizador.html: {len(published)} repositório(s) no catálogo NER_HUB, em commits fixos")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True, help="usuário ou organização no Hugging Face")
    ap.add_argument("--pack", type=Path, default=ROOT / "dist" / "anonlab-ner")
    ap.add_argument("--models", nargs="*", help="slugs a publicar (padrão: todos do pacote)")
    ap.add_argument("--suffix", default="-onnx", help="sufixo do nome do repositório")
    ap.add_argument("--private", action="store_true", help="cria repositórios privados")
    ap.add_argument("--allow-unlicensed", action="store_true", help="publica mesmo sem licença declarada no original")
    ap.add_argument("--no-update-html", action="store_true", help="não mexe no anonimizador.html")
    ap.add_argument("--dry-run", action="store_true", help="só mostra o que seria enviado")
    a = ap.parse_args()

    manifest = json.loads((a.pack / "anonlab-ner.json").read_text(encoding="utf-8"))
    slugs = a.models or list(manifest["models"])
    api = None
    if not a.dry_run:
        from huggingface_hub import HfApi

        api = HfApi()
        print(f"logado como: {api.whoami()['name']}")

    published = []
    for slug in slugs:
        mdir = a.pack / manifest["models"][slug]["path"]
        meta = json.loads((mdir / "anonlab-model.json").read_text(encoding="utf-8"))
        repo = f"{a.user}/{slug}{a.suffix}"
        license_ = meta["source"].get("license")
        if not license_ and not a.allow_unlicensed:
            print(f"- {slug}: PULADO — {meta['source']['hf_id']} não declara licença (use --allow-unlicensed)")
            continue
        files = [f for f in FILES if (mdir / f).exists()] + [v["file"] for v in meta["variants"].values()]
        size = sum((mdir / f).stat().st_size for f in files)
        print(f"- {slug} → {repo}  ({len(files)} arquivos, {size / 2**20:.0f} MB, licença {license_})")
        if a.dry_run:
            for f in files:
                print(f"    {f}")
            continue

        from huggingface_hub import CommitOperationAdd

        api.create_repo(repo, repo_type="model", private=a.private, exist_ok=True)
        ops = [CommitOperationAdd(path_in_repo=f, path_or_fileobj=str(mdir / f)) for f in files]
        ops.append(CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=model_card(meta, repo).encode()))
        if (mdir / "MODEL_CARD.md").exists():
            ops.append(CommitOperationAdd(path_in_repo="ORIGINAL_MODEL_CARD.md", path_or_fileobj=str(mdir / "MODEL_CARD.md")))
        info = api.create_commit(repo, operations=ops,
                                 commit_message=f"AnonLab: ONNX de {meta['source']['hf_id']}@{meta['source']['revision'][:8]}")
        print(f"    publicado: commit {info.oid}")
        published.append((repo, info.oid))

    if published and not a.no_update_html:
        update_html(published)


if __name__ == "__main__":
    main()
