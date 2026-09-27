#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tokenizers>=0.20"]
# ///
"""
Gera vetores de referência do tokenizador (HF tokenizers) para um modelo do
Hugging Face, para tests/test_ner_core.mjs conferir o tokenizador JS do AnonLab.

    uv run tools/tokenizer_vectors.py augustaklug/legal-bert-ner-base-cased-ptbr-onnx fd285c1c…

Os textos são os do corpus de teste (tests/vectors/legal-bert-lgpd.json) e os
documentos de tests/golden/docs.json. Grava tests/vectors/tok-<nome>.json.
"""
import json
import sys
import urllib.request
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    repo, revision = sys.argv[1], sys.argv[2]
    url = f"https://huggingface.co/{repo}/resolve/{revision}/tokenizer.json"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "anonlab"}), timeout=60).read()
    tok = Tokenizer.from_str(raw.decode("utf-8"))
    tok.no_padding()
    tok.no_truncation()  # o AnonLab não trunca: textos longos viram janelas
    texts = [c["text"] for c in json.loads((ROOT / "tests/vectors/legal-bert-lgpd.json").read_text(encoding="utf-8"))["cases"]]
    texts += [d["text"] for d in json.loads((ROOT / "tests/golden/docs.json").read_text(encoding="utf-8"))["docs"]]
    cases = []
    for t in texts:
        e = tok.encode(t, add_special_tokens=False)
        cases.append({"text": t, "ids": e.ids, "offsets": [list(o) for o in e.offsets], "word_ids": e.word_ids,
                      "tokenizer_only": True})
    out = ROOT / "tests" / "vectors" / f"tok-{repo.split('/')[1]}.json"
    out.write_text(json.dumps({"model": repo, "revision": revision, "tokenizer_url": url, "cases": cases},
                              ensure_ascii=False), encoding="utf-8")
    print(f"{out} ({len(cases)} casos, {sum(len(c['ids']) for c in cases)} tokens)")


if __name__ == "__main__":
    main()
