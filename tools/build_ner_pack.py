#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "torch>=2.4",
#   "transformers>=4.44",
#   "onnx>=1.16",
#   "onnxruntime>=1.20",
#   "onnxconverter-common>=1.14",
#   "onnxscript",
#   "onnx-ir",
#   "huggingface_hub>=0.24",
#   "safetensors",
#   "numpy",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""
Monta o PACOTE NER do AnonLab (runtime + modelos BERTimbau em ONNX).

Roda UMA vez, numa máquina COM internet. O resultado é uma pasta que o
pesquisador copia (pendrive, rede interna…) para a máquina airgapped e abre
no anonimizador.html pelo botão "Carregar pacote NER". O anonimizador nunca
acessa a rede: tudo o que ele usa está nesta pasta.

    uv run tools/build_ner_pack.py                      # presets "lgpd" + "harem"
    uv run tools/build_ner_pack.py --model lgpd         # só um modelo
    uv run tools/build_ner_pack.py --model org/modelo-hf --dtypes q8
    uv run tools/build_ner_pack.py --list

Estrutura gerada (padrão: dist/anonlab-ner/):

    anonlab-ner.json            manifesto (versões, SHA-256 de cada arquivo)
    LEIA-ME.txt
    runtime/                    transformers.js + onnxruntime-web (WASM/WebGPU)
    models/<slug>/
        anonlab-model.json      rótulos, mapeamento p/ tipos do AnonLab, variantes
        config.json  tokenizer.json  tokenizer_config.json  ...
        onnx/model_<dtype>.onnx

Cada variante ONNX é comparada com o modelo PyTorch original (fp32) num corpus
de teste embutido; o relatório de concordância vai para o anonlab-model.json.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

# ============================================================ configuração

FORMAT_VERSION = 1

# Versão do transformers.js. O onnxruntime-web vem da dependência exata
# declarada por ele (os .wasm precisam bater com o JS embutido no bundle).
TRANSFORMERS_JS_VERSION = "4.3.0"

# arquivo no pacote -> (pacote npm, caminho dentro do tarball)
RUNTIME_FILES = {
    "transformers.min.js": ("@huggingface/transformers", "package/dist/transformers.min.js"),
    "ort-wasm-simd-threaded.asyncify.mjs": ("onnxruntime-web", "package/dist/ort-wasm-simd-threaded.asyncify.mjs"),
    "ort-wasm-simd-threaded.asyncify.wasm": ("onnxruntime-web", "package/dist/ort-wasm-simd-threaded.asyncify.wasm"),
}
RUNTIME_LICENSES = {
    "LICENSE-transformers.js.txt": ("@huggingface/transformers", "package/LICENSE"),
}
# o tarball do onnxruntime-web não traz o texto da licença (package.json: "MIT")
ORT_LICENSE = """MIT License

Copyright (c) Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

PRESETS = {
    "lgpd": {
        "hf": "celiudos/legal-bert-lgpd",
        "slug": "legal-bert-lgpd",
        "title": "Legal-BERT-LGPD — dados pessoais (LGPD), domínio jurídico",
        "notes": "BERTimbau Large ajustado para NOME, ENDERECO, DATA, CPF, TELEFONE, EMAIL, "
                 "DINHEIRO e CEP em textos jurídicos (Souza Filho, UnB/MPF, 2025).",
    },
    "lenerbr": {
        "hf": "pierreguillou/ner-bert-large-cased-pt-lenerbr",
        "slug": "ner-bert-large-lenerbr",
        "title": "BERTimbau Large LeNER-Br — pessoas, organizações, locais (jurídico)",
        "notes": "PESSOA, ORGANIZACAO, LOCAL, TEMPO, LEGISLACAO, JURISPRUDENCIA.",
    },
    "lenerbr-base": {
        "hf": "pierreguillou/ner-bert-base-cased-pt-lenerbr",
        "slug": "ner-bert-base-lenerbr",
        "title": "BERTimbau Base LeNER-Br — versão leve (3× mais rápida)",
        "notes": "PESSOA, ORGANIZACAO, LOCAL, TEMPO, LEGISLACAO, JURISPRUDENCIA.",
    },
    "harem": {
        "hf": "liaad/NER_harem_bert-base-portuguese-cased",
        "slug": "ner-harem-base",
        "title": "BERTimbau Base HAREM — domínio geral (notícias, web, entrevistas)",
        "notes": "PESSOA, ORGANIZACAO, LOCAL, TEMPO, VALOR, ACONTECIMENTO, OBRA… (HAREM).",
    },
    "harem-large": {
        "hf": "liaad/NER_harem_bert-large-portuguese-cased",
        "slug": "ner-harem-large",
        "title": "BERTimbau Large HAREM — domínio geral",
        "notes": "Modelo usado por Domingos (FCUL, 2025) para anonimização de PDFs.",
    },
}

# Rótulo do modelo (sem B-/I-) -> tipo do AnonLab (None = ignorar).
# O anonimizador.html tem uma cópia desta tabela como fallback.
LABEL_MAP = {
    # pessoas
    "NOME": "PESSOA", "PESSOA": "PESSOA", "PER": "PESSOA", "PERSON": "PESSOA", "NAME": "PESSOA",
    # organizações
    "ORGANIZACAO": "ORG", "ORGANIZAÇÃO": "ORG", "ORG": "ORG",
    # lugares
    "LOCAL": "LOCAL", "LOC": "LOCAL", "LOCATION": "LOCAL",
    "ENDERECO": "ENDERECO", "ENDEREÇO": "ENDERECO", "ADDRESS": "ENDERECO",
    # tempo
    "DATA": "DATA", "TEMPO": "DATA", "DATE": "DATA", "TIME": "DATA",
    # identificadores e contato
    "CPF": "CPF", "CNPJ": "CNPJ", "RG": "RG", "CEP": "CEP", "ZIPCODE": "CEP",
    "TELEFONE": "TEL", "PHONE": "TEL", "EMAIL": "EMAIL", "E-MAIL": "EMAIL",
    # valores e outros
    "DINHEIRO": "VALOR", "VALOR": "VALOR", "MONEY": "VALOR",
    "ACONTECIMENTO": "EVENTO", "EVENTO": "EVENTO", "EVENT": "EVENTO",
    "OBRA": "OBRA",
    # não são dados pessoais: ignorados
    "LEGISLACAO": None, "JURISPRUDENCIA": None, "ABSTRACCAO": None, "COISA": None,
    "OUTRO": None, "MISC": None,
}

# dtype (nome do transformers.js) -> sufixo do arquivo em onnx/
DTYPE_SUFFIX = {"fp32": "", "fp16": "_fp16", "q8": "_quantized", "q4": "_q4", "q4f16": "_q4f16"}

# F1 mínimo das entidades de cada variante contra o PyTorch fp32 (mesmo texto, mesmas
# janelas). Concordância por token engana: quase todo token é "O". Medido no
# legal-bert-lgpd (315 textos): fp16 1,000 · q4 assimétrico 0,977 · q8 0,90–0,92.
MIN_ENTITY_F1 = {"fp32": 0.999, "fp16": 0.99, "q8": 0.95, "q4": 0.95, "q4f16": 0.93}

# Frases reais (domínio jurídico) para a validação: LeNER-Br, partição de teste.
# Só usadas aqui, na máquina de build; não entram no pacote.
VALIDATION_URL = "https://raw.githubusercontent.com/peluz/lener-br/master/leNER-Br/test/test.conll"
VALIDATION_SENTENCES = 300

MAX_LENGTH = 512     # posição máxima do BERT
STRIDE = 128         # sobreposição entre janelas (em tokens)

# Corpus de teste (dados FICTÍCIOS). Cobre os rótulos da LGPD, entrevista,
# prontuário e texto jurídico. Usado na validação e nos vetores de teste JS.
TEST_TEXTS = [
    "Entrevista realizada em 12/03/2021 com João da Silva, 42 anos, morador de Recife, Pernambuco.",
    "Ele relatou que trabalhou com Maria Oliveira na empresa Tecidos Brasil Ltda. até 2019.",
    "Contato: joao.silva@email.com, telefone (81) 99876-5432. CPF informado: 529.982.247-25.",
    "O processo 0001234-56.2021.8.17.0001 corre na 2ª Vara Cível da Comarca de Salvador, Bahia.",
    "Mencionou o Dr. Carlos Andrade e uma viagem a Portugal em março de 2020.",
    "Trata-se de representação feita pelo senhor Francis Pantele da Cozzi, CPF: 412.612.341-32, "
    "telefone (31) 951358433, email fran@bol.com, atinente à sua contratação pela senhora "
    "Marinalva Bete Raz, CPF: 049.567.041-22, telefone (61) 9412 3333.",
    "Marinalva Bete Raz reclama indenização por danos morais no dia 14.05.2013 no valor de "
    "R$ 82.662,00 relacionado ao endereço constante no CEP 59123-222, Rua dos Pioneiros, nº 450, "
    "Jardim Esmeralda, Campo Grande, MS.",
    "Paciente Ana Beatriz Souza, nascida em 03/07/1985, deu entrada no Hospital São Lucas "
    "às 14h30 com quadro de asma. Acompanhante: Roberto Souza (irmão), fone 11 3456-7890.",
    "ENTREVISTADORA: E a senhora morava onde nessa época?\n"
    "D. LURDES: Morava lá na Vila Mariana, perto da casa do seu Antônio, sabe? Depois fui pra Osasco.",
    "A reunião com a diretora Fernanda Lima, da Secretaria Municipal de Educação de Belo Horizonte, "
    "ocorreu em 5 de maio de 2022, na Escola Estadual Pedro II.",
    "Em depoimento, a testemunha Josué Vittas afirmou residir na Avenida Brasil, 1500, apto 32, "
    "Bairro Centro, Juiz de Fora - MG, CEP 36010-000, e trabalhar na Petrobras desde 2015.",
    "O autor, JOSÉ CARLOS PEREIRA, brasileiro, casado, portador do RG 12.345.678-9 SSP/SP, "
    "residente na Rua Augusta, 200, São Paulo/SP, ajuizou ação contra o Banco Itaú S.A.",
    "Ontem a Luíza me mandou mensagem no WhatsApp dizendo que o Pedrinho tinha voltado de Manaus.",
    "Segundo a Lei nº 13.709/2018 (LGPD), o tratamento de dados pessoais sensíveis exige consentimento.",
    "Texto sem nenhum dado pessoal: o clima estava agradável e a conversa fluiu bem durante a tarde.",
]


# ============================================================ utilidades

def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "anonlab-build-ner-pack"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


# ============================================================ runtime (npm)

def npm_tarball(name: str, version: str) -> tuple[dict, tarfile.TarFile]:
    """Baixa o tarball de um pacote npm e confere o SRI (sha512) do registro."""
    meta = json.loads(http_get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/{version}"))
    data = http_get(meta["dist"]["tarball"])
    algo, _, expected = meta["dist"]["integrity"].partition("-")
    got = base64.b64encode(hashlib.new(algo, data).digest()).decode()
    if got != expected:
        raise SystemExit(f"Integridade do npm falhou para {name}@{version}")
    return meta, tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def build_runtime(out: Path) -> dict:
    rt = out / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    log(f"runtime: @huggingface/transformers@{TRANSFORMERS_JS_VERSION}")
    tjs_meta, tjs_tar = npm_tarball("@huggingface/transformers", TRANSFORMERS_JS_VERSION)
    ort_version = tjs_meta["dependencies"]["onnxruntime-web"]
    log(f"runtime: onnxruntime-web@{ort_version} (dependência exata do transformers.js)")
    _, ort_tar = npm_tarball("onnxruntime-web", ort_version)
    tars = {"@huggingface/transformers": tjs_tar, "onnxruntime-web": ort_tar}

    files = {}
    for fname, (pkg, member) in {**RUNTIME_FILES, **RUNTIME_LICENSES}.items():
        data = tars[pkg].extractfile(member).read()
        (rt / fname).write_bytes(data)
        if fname in RUNTIME_FILES:
            files[fname] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            log(f"  {fname:42s} {human(len(data)):>9s}  sha256 {files[fname]['sha256']}")
    (rt / "LICENSE-onnxruntime-web.txt").write_text(ORT_LICENSE, encoding="utf-8")
    return {"transformers_js": TRANSFORMERS_JS_VERSION, "onnxruntime_web": ort_version, "files": files}


# ============================================================ modelo

def resolve_models(names: list[str]) -> list[dict]:
    models = []
    for n in names:
        if n in PRESETS:
            models.append({"preset": n, **PRESETS[n]})
        elif "/" in n:
            slug = n.split("/")[-1].lower().replace("_", "-")
            models.append({"preset": None, "hf": n, "slug": slug, "title": n, "notes": ""})
        else:
            raise SystemExit(f"Modelo desconhecido: {n!r}. Use --list para ver os presets.")
    return models


def download_model(hf_id: str, revision: str | None, cache_dir: Path) -> tuple[Path, object]:
    from huggingface_hub import HfApi, snapshot_download

    info = HfApi().model_info(hf_id, revision=revision, files_metadata=True)
    names = {s.rfilename for s in info.siblings}
    weights = ["*.safetensors"] if any(n.endswith(".safetensors") for n in names) else ["pytorch_model.bin"]
    path = snapshot_download(
        hf_id,
        revision=info.sha,
        cache_dir=str(cache_dir),
        allow_patterns=["*.json", "vocab.txt", "README.md", "LICENSE*", *weights],
        ignore_patterns=["onnx/*", "*.onnx", "training_args*"],
    )
    return Path(path), info


def check_tokenizer_json(tok_json: dict) -> dict:
    """O tokenizador JS do AnonLab implementa BERT WordPiece (BasicTokenizer + WordPiece)."""
    norm = tok_json.get("normalizer") or {}
    pre = tok_json.get("pre_tokenizer") or {}
    model = tok_json.get("model") or {}
    problems = []
    if norm.get("type") != "BertNormalizer":
        problems.append(f"normalizer={norm.get('type')}")
    if pre.get("type") != "BertPreTokenizer":
        problems.append(f"pre_tokenizer={pre.get('type')}")
    if model.get("type") != "WordPiece":
        problems.append(f"model={model.get('type')}")
    if problems:
        raise SystemExit("Tokenizador não suportado (esperado BERT WordPiece): " + ", ".join(problems))
    return {
        "lowercase": bool(norm.get("lowercase", False)),
        "strip_accents": norm.get("strip_accents"),
        "clean_text": bool(norm.get("clean_text", True)),
        "handle_chinese_chars": bool(norm.get("handle_chinese_chars", True)),
        "unk_token": model.get("unk_token", "[UNK]"),
        "continuing_subword_prefix": model.get("continuing_subword_prefix", "##"),
        "max_input_chars_per_word": model.get("max_input_chars_per_word", 100),
    }


class LogitsOnly:
    """Envolve o modelo HF para o export devolver só os logits."""

    def __new__(cls, model):
        import torch

        class _W(torch.nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m

            def forward(self, input_ids, attention_mask, token_type_ids):
                return self.m(input_ids=input_ids, attention_mask=attention_mask,
                              token_type_ids=token_type_ids).logits

        return _W(model)


def export_fp32(model, tokenizer, path: Path) -> None:
    """Export via torch.export (dynamo). O exportador TorchScript antigo congela a
    construção de máscara do transformers 5 e diverge do PyTorch (visto: Δp 0,5)."""
    import torch
    from torch.export import Dim

    enc = tokenizer(["Exemplo de texto com João da Silva.", "Outro texto."], padding=True, return_tensors="pt")
    args = (enc["input_ids"], enc["attention_mask"], enc["token_type_ids"])
    names = ["input_ids", "attention_mask", "token_type_ids"]
    b, s = Dim("batch_size"), Dim("sequence_length", max=MAX_LENGTH)
    shapes = {n: {0: b, 1: s} for n in names}
    with torch.no_grad():
        prog = torch.onnx.export(LogitsOnly(model), args, dynamo=True, dynamic_shapes=shapes,
                                 input_names=names, output_names=["logits"], opset_version=18,
                                 optimize=True, verbose=False)
    prog.save(str(path))


def make_variant(dtype: str, fp32_path: Path, out_path: Path) -> None:
    import onnx

    if dtype == "fp32":
        shutil.copyfile(fp32_path, out_path)
    elif dtype == "fp16":
        from onnxconverter_common import float16

        m = float16.convert_float_to_float16(onnx.load(str(fp32_path)), keep_io_types=True)
        onnx.save(m, str(out_path))
    elif dtype == "q8":
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(str(fp32_path), str(out_path), weight_type=QuantType.QInt8,
                         per_channel=False, reduce_range=False,
                         extra_options={"MatMulConstBOnly": True})
    elif dtype in ("q4", "q4f16"):
        from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer

        m = onnx.load(str(fp32_path))
        if dtype == "q4f16":
            # converte antes de quantizar, para as escalas do MatMulNBits já saírem em fp16
            from onnxconverter_common import float16

            m = float16.convert_float_to_float16(m, keep_io_types=True)
        # a cabeça de classificação é pequena e sensível: fica em precisão cheia.
        # assimétrico/bloco 32 foi o melhor no teste (F1 0,977 vs 0,973 simétrico, 0,967 bloco 16)
        keep = [n.name for n in m.graph.node if n.op_type == "MatMul" and "classifier" in n.name]
        q = MatMulNBitsQuantizer(m, block_size=32, is_symmetric=False, nodes_to_exclude=keep)
        q.process()
        onnx.save(q.model.model, str(out_path))
    else:
        raise ValueError(dtype)


# ------------------------------------------------------------ referência (espelha o JS)

def windows_for(n_tokens: int, max_len: int = MAX_LENGTH, stride: int = STRIDE) -> list[tuple[int, int]]:
    """Janelas [ini, fim) sobre os tokens de conteúdo (sem [CLS]/[SEP])."""
    span = max_len - 2
    if n_tokens <= span:
        return [(0, n_tokens)]
    step = span - stride
    out, start = [], 0
    while True:
        end = min(start + span, n_tokens)
        out.append((start, end))
        if end == n_tokens:
            return out
        start += step


def best_window(i: int, wins: list[tuple[int, int]]) -> int:
    """Para cada token, usa a janela em que ele está mais ao centro (mais contexto)."""
    best, best_ctx = 0, -1
    for w, (s, e) in enumerate(wins):
        if s <= i < e:
            ctx = min(i - s, e - 1 - i)
            if ctx > best_ctx:
                best, best_ctx = w, ctx
    return best


def token_probs(run, tokenizer, text: str):
    """Probabilidades por token de conteúdo, com janelas sobrepostas. run(ids, mask, tt) -> logits."""
    import numpy as np

    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids, offsets, word_ids = enc["input_ids"], enc["offset_mapping"], enc.word_ids()
    wins = windows_for(len(ids))
    cls, sep = tokenizer.cls_token_id, tokenizer.sep_token_id
    per_win = []
    for s, e in wins:
        row = [cls] + ids[s:e] + [sep]
        a = np.array([row], dtype=np.int64)
        logits = run(a, np.ones_like(a), np.zeros_like(a))[0][1:-1]
        z = logits - logits.max(-1, keepdims=True)
        p = np.exp(z)
        per_win.append(p / p.sum(-1, keepdims=True))
    rows = []
    for i in range(len(ids)):
        w = best_window(i, wins)
        rows.append(per_win[w][i - wins[w][0]])
    probs = np.stack(rows) if rows else np.zeros((0, 1))
    return ids, offsets, word_ids, probs


def split_tag(label: str) -> tuple[str, str]:
    if len(label) > 2 and label[1] == "-" and label[0] in "BIES":
        return label[0], label[2:]
    return "I", label


def aggregate_first(offsets, word_ids, probs, id2label) -> list[dict]:
    """Estratégia "first" do HF: a palavra herda o rótulo do 1º sub-token; agrupa por BIO."""
    import numpy as np

    words = []  # (start, end, label, score)
    i = 0
    while i < len(word_ids):
        j = i
        while j + 1 < len(word_ids) and word_ids[j + 1] == word_ids[i]:
            j += 1
        k = int(np.argmax(probs[i]))
        words.append((offsets[i][0], offsets[j][1], id2label[k], float(probs[i][k])))
        i = j + 1
    ents, cur = [], None
    for s, e, label, score in words:
        bi, tag = split_tag(label)
        if cur is not None and tag == cur["tag"] and bi != "B":
            cur["end"] = e
            cur["scores"].append(score)
            continue
        if cur is not None:
            ents.append(cur)
        cur = {"tag": tag, "start": s, "end": e, "scores": [score]}
    if cur is not None:
        ents.append(cur)
    return [{"label": c["tag"], "start": c["start"], "end": c["end"],
             "score": round(sum(c["scores"]) / len(c["scores"]), 6)}
            for c in ents if c["tag"] != "O"]


def validation_texts(work: Path) -> list[str]:
    """Corpus embutido + frases do LeNER-Br (se der para baixar)."""
    path = work / "lener_test.conll"
    try:
        if not path.exists():
            path.write_bytes(http_get(VALIDATION_URL))
    except Exception as e:  # sem internet/GitHub: valida só com o corpus embutido
        log(f"  aviso: sem LeNER-Br para validação ({e}); usando só o corpus embutido")
        return list(TEST_TEXTS)
    sents, cur = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            if cur:
                sents.append(" ".join(cur))
                cur = []
            continue
        cur.append(line.split(" ")[0])
    return list(TEST_TEXTS) + [s for s in sents if len(s) > 40][:VALIDATION_SENTENCES]


def reference(ref_run, tokenizer, texts) -> list:
    """Probabilidades do PyTorch fp32, calculadas uma vez e reusadas nas comparações."""
    return [(t, token_probs(ref_run, tokenizer, t)) for t in texts]


def compare(ref: list, cand_run, tokenizer, id2label) -> dict:
    import numpy as np

    agree = total = 0
    max_dp = 0.0
    tp = fp = fn = 0
    for t, (_, off, wid, p_ref) in ref:
        _, _, _, p_can = token_probs(cand_run, tokenizer, t)
        if len(p_ref):
            agree += int((p_ref.argmax(-1) == p_can.argmax(-1)).sum())
            total += len(p_ref)
            max_dp = max(max_dp, float(np.abs(p_ref - p_can).max()))
        e_ref = {(e["label"], e["start"], e["end"]) for e in aggregate_first(off, wid, p_ref, id2label)}
        e_can = {(e["label"], e["start"], e["end"]) for e in aggregate_first(off, wid, p_can, id2label)}
        tp += len(e_ref & e_can)
        fp += len(e_can - e_ref)
        fn += len(e_ref - e_can)
    f1 = 2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else 1.0
    return {"token_agreement": round(agree / max(total, 1), 5), "entity_f1_vs_fp32": round(f1, 5),
            "max_prob_diff": round(max_dp, 5), "tokens": total}


def ort_runner(path: Path):
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])

    def run(ids, mask, tt):
        return sess.run(["logits"], {"input_ids": ids, "attention_mask": mask, "token_type_ids": tt})[0]

    return run


def torch_runner(model):
    import torch

    def run(ids, mask, tt):
        with torch.no_grad():
            return model(input_ids=torch.from_numpy(ids), attention_mask=torch.from_numpy(mask),
                         token_type_ids=torch.from_numpy(tt)).logits.numpy()

    return run


TOKENIZER_EDGE_CASES = [
    # casos só de tokenização (sem entidades de referência): acentos, pontuação,
    # controles, espaços unicode, CJK, emoji fora do BMP, palavra gigante, [SEP] literal
    "Ação, coração e pão! São Paulo—Rio? «aspas» “curvas” 'simples' (parênteses) [colchetes] {chaves}",
    "Tabs\taqui,\r\nquebra nbsp em-space​zero-width­soft-hyphen\u0007bell fim",
    "E-mail: fulano.de.tal+tag@exemplo.com.br; site https://www.exemplo.gov.br/a?b=1&c=2#x",
    "Números: 1.234,56 · R$ 7.890,00 · 12/03/2021 · 10h30 · nº 450 · 3º andar · 50%",
    "Chinês 北京 e japonês 東京 misturados com texto; emoji 🙂👍🏽 e símbolos ™ © ° ± ×",
    "Palavra" + "super" * 30 + "gigante e depois normal",
    "Texto com [SEP] literal e [CLS] também, e [MASK] no meio.",
    "Decomposto (NFD): João, José, coração",
    "   espaços   no   início e fim   ",
    "",
]


def test_vectors(tokenizer, run, id2label, texts) -> list[dict]:
    """Vetores p/ o teste JS: ids/offsets/word_ids do tokenizador HF, janelas,
    rótulo+score por token (após escolher a janela) e entidades de referência."""
    import numpy as np

    long_text = "\n\n".join(texts * 6)  # força várias janelas
    out = []
    for t in list(texts) + [long_text]:
        ids, off, wid, p = token_probs(run, tokenizer, t)
        arg = p.argmax(-1) if len(p) else np.zeros(0, dtype=int)
        wins = windows_for(len(ids))
        out.append({"text": t, "ids": ids, "offsets": [list(o) for o in off], "word_ids": wid,
                    "windows": [list(w) for w in wins],
                    "token_windows": [best_window(i, wins) for i in range(len(ids))],
                    "token_labels": [int(x) for x in arg],
                    "token_scores": [round(float(p[i][arg[i]]), 6) for i in range(len(arg))],
                    "entities": aggregate_first(off, wid, p, id2label)})
    for t in TOKENIZER_EDGE_CASES:
        enc = tokenizer(t, add_special_tokens=False, return_offsets_mapping=True)
        out.append({"text": t, "ids": enc["input_ids"], "offsets": [list(o) for o in enc["offset_mapping"]],
                    "word_ids": enc.word_ids(), "tokenizer_only": True})
    return out


def load_hf(spec: dict, work: Path, revision: str | None):
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    src, info = download_model(spec["hf"], revision, work / "hf-cache")
    log(f"  revisão {info.sha}")
    tokenizer = AutoTokenizer.from_pretrained(str(src), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(src), attn_implementation="eager")
    model.eval()
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    return src, info, tokenizer, model, id2label


def write_vectors(spec, info, tokenizer, model, id2label, vectors_dir: Path) -> None:
    vectors_dir.mkdir(parents=True, exist_ok=True)
    tok_json = json.loads(tokenizer.backend_tokenizer.to_str())
    vec = {"model": spec["hf"], "revision": info.sha, "id2label": {str(k): v for k, v in id2label.items()},
           "tokenizer": check_tokenizer_json(tok_json), "max_length": MAX_LENGTH, "stride": STRIDE,
           "cases": test_vectors(tokenizer, torch_runner(model), id2label, TEST_TEXTS)}
    path = vectors_dir / f"{spec['slug']}.json"
    path.write_text(json.dumps(vec, ensure_ascii=False), encoding="utf-8")
    log(f"  vetores de teste -> {path}")


def build_model(spec: dict, out: Path, work: Path, dtypes: list[str], revision: str | None,
                vectors_dir: Path | None) -> dict:
    hf_id, slug = spec["hf"], spec["slug"]
    log(f"modelo {hf_id} -> models/{slug}")
    src, info, tokenizer, model, id2label = load_hf(spec, work, revision)

    mdir = out / "models" / slug
    (mdir / "onnx").mkdir(parents=True, exist_ok=True)

    # arquivos de configuração/tokenizador (tokenizer.json é gerado se o repo não tiver)
    tokenizer.save_pretrained(str(work / f"tok-{slug}"))
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"):
        p = src / name if (src / name).exists() else work / f"tok-{slug}" / name
        if p.exists():
            shutil.copyfile(p, mdir / name)
    for name in ("README.md", "LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (src / name).exists():
            shutil.copyfile(src / name, mdir / ("MODEL_CARD.md" if name == "README.md" else name))
    tok_info = check_tokenizer_json(json.loads((mdir / "tokenizer.json").read_text(encoding="utf-8")))

    fp32_path = work / f"{slug}-fp32.onnx"
    if not fp32_path.exists():
        log("  exportando ONNX fp32…")
        export_fp32(model, tokenizer, fp32_path)
    texts = validation_texts(work)
    log(f"  referência PyTorch fp32 em {len(texts)} textos…")
    ref = reference(torch_runner(model), tokenizer, texts)
    report = {"fp32": compare(ref, ort_runner(fp32_path), tokenizer, id2label)}
    log(f"  fp32 ONNX vs PyTorch: {report['fp32']}")
    if report["fp32"]["entity_f1_vs_fp32"] < MIN_ENTITY_F1["fp32"]:
        raise SystemExit("Export fp32 divergiu do PyTorch — abortando.")

    variants = {}
    for dtype in dtypes:
        path = mdir / "onnx" / f"model{DTYPE_SUFFIX[dtype]}.onnx"
        log(f"  variante {dtype}…")
        make_variant(dtype, fp32_path, path)
        rep = report["fp32"] if dtype == "fp32" else compare(ref, ort_runner(path), tokenizer, id2label)
        report[dtype] = rep
        ok = rep["entity_f1_vs_fp32"] >= MIN_ENTITY_F1[dtype]
        log(f"    {human(path.stat().st_size)} · {rep} · {'OK' if ok else 'REPROVADA'}")
        if not ok:
            path.unlink()
            continue
        variants[dtype] = {"file": f"onnx/{path.name}", "size": path.stat().st_size, "sha256": sha256_file(path)}

    report["corpus"] = {"texts": len(texts), "tokens": report["fp32"]["tokens"]}
    if vectors_dir:
        write_vectors(spec, info, tokenizer, model, id2label, vectors_dir)

    tags = sorted({split_tag(l)[1] for l in id2label.values() if l != "O"})
    license_ = getattr(getattr(info, "card_data", None), "license", None)
    manifest = {
        "format": FORMAT_VERSION,
        "slug": slug,
        "title": spec["title"],
        "notes": spec["notes"],
        "source": {"hf_id": hf_id, "revision": info.sha, "license": license_},
        "architecture": model.config.architectures[0] if model.config.architectures else "BertForTokenClassification",
        "hidden_size": model.config.hidden_size,
        "num_hidden_layers": model.config.num_hidden_layers,
        "max_length": MAX_LENGTH,
        "stride": STRIDE,
        "tokenizer": tok_info,
        "id2label": {str(k): v for k, v in id2label.items()},
        "label_map": {t: LABEL_MAP.get(t.upper()) for t in tags},
        "variants": variants,
        "validation": report,
        "files": {n: {"sha256": sha256_file(mdir / n), "size": (mdir / n).stat().st_size}
                  for n in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json")
                  if (mdir / n).exists()},
    }
    unknown = [t for t in tags if t.upper() not in LABEL_MAP]
    if unknown:
        log(f"  aviso: rótulos sem mapeamento (serão ignorados): {unknown}")
    (mdir / "anonlab-model.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


LEIA_ME = """PACOTE NER DO ANONLAB
=====================

Esta pasta contém o modelo de linguagem (NER/BERTimbau) usado pelo
anonimizador.html para sugerir nomes, endereços e outros dados pessoais.

COMO USAR
1. Abra o anonimizador.html no navegador (Chrome ou Edge recomendados).
2. No cartão "Modelo de linguagem (NER)", clique em "Carregar pacote NER"
   e selecione ESTA pasta (anonlab-ner).
3. Espere o modelo carregar (a barra mostra o progresso) e detecte normalmente.

PRIVACIDADE
- Nada é baixado nem enviado: o navegador lê os arquivos desta pasta e roda
  o modelo localmente (GPU via WebGPU, ou CPU via WebAssembly).
- O anonimizador confere o SHA-256 dos arquivos de runtime antes de executá-los.

CONTEÚDO
- runtime/  transformers.js {tjs} e onnxruntime-web {ort} (licenças em runtime/)
- models/   {models}

Gerado em {date} por tools/build_ner_pack.py.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # lgpd + harem: um cobre o que o outro não tem (o LGPD não tem ORGANIZACAO/LOCAL);
    # juntos zeraram o vazamento nos documentos de tests/golden
    ap.add_argument("--model", nargs="+", default=["lgpd", "harem"], help="presets ou IDs do Hugging Face")
    ap.add_argument("--revision", default=None, help="revisão/commit do modelo (padrão: main)")
    ap.add_argument("--dtypes", default="fp16,q8,q4",
                    help="variantes ONNX: fp32,fp16,q8,q4,q4f16 (as reprovadas na validação são descartadas)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "dist" / "anonlab-ner")
    ap.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "anonlab-build")
    ap.add_argument("--vectors", type=Path, default=None, help="pasta para vetores de teste do tokenizador JS")
    ap.add_argument("--skip-runtime", action="store_true", help="não baixa o runtime (usa o que já está em --out)")
    ap.add_argument("--vectors-only", action="store_true", help="só gera os vetores de teste (requer --vectors)")
    ap.add_argument("--list", action="store_true", help="lista os presets e sai")
    a = ap.parse_args()

    if a.list:
        for k, v in PRESETS.items():
            print(f"{k:13s} {v['hf']:48s} {v['title']}")
        return
    if a.vectors_only:
        if not a.vectors:
            raise SystemExit("--vectors-only requer --vectors PASTA")
        for spec in resolve_models(a.model):
            log(f"vetores: {spec['hf']}")
            _, info, tokenizer, model, id2label = load_hf(spec, a.work, a.revision)
            write_vectors(spec, info, tokenizer, model, id2label, a.vectors)
        return

    dtypes = [d.strip() for d in a.dtypes.split(",") if d.strip()]
    bad = [d for d in dtypes if d not in DTYPE_SUFFIX]
    if bad:
        raise SystemExit(f"dtype inválido: {bad}")
    a.out.mkdir(parents=True, exist_ok=True)
    a.work.mkdir(parents=True, exist_ok=True)

    manifest_path = a.out / "anonlab-ner.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    runtime = old.get("runtime") if a.skip_runtime else build_runtime(a.out)
    if not runtime:
        raise SystemExit("--skip-runtime, mas não há runtime em --out")

    models = dict(old.get("models", {}))
    for spec in resolve_models(a.model):
        m = build_model(spec, a.out, a.work, dtypes, a.revision, a.vectors)
        models[m["slug"]] = {"title": m["title"], "path": f"models/{m['slug']}",
                             "variants": sorted(m["variants"])}

    manifest = {"format": FORMAT_VERSION, "kind": "anonlab-ner-pack",
                "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "runtime": runtime, "models": models}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.out / "LEIA-ME.txt").write_text(LEIA_ME.format(
        tjs=runtime["transformers_js"], ort=runtime["onnxruntime_web"],
        models=", ".join(models), date=manifest["created"]), encoding="utf-8")

    total = sum(p.stat().st_size for p in a.out.rglob("*") if p.is_file())
    log(f"pronto: {a.out} ({human(total)})")
    log(f"arquivos intermediários em {a.work} (pode apagar)")


if __name__ == "__main__":
    main()
