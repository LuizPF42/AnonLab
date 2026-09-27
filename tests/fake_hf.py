"""Servidor de TESTE: o repositório como site estático + um Hugging Face falso.

    python tests/fake_hf.py 8765

/fakehf/<dono>/<slug>-onnx/resolve/<rev>/<arquivo> é servido de
dist/anonlab-ner/models/<slug>/<arquivo>, imitando o que tools/publish_hub.py
publica. Com isso o modo "🌐 Baixar modelos" pode ser testado antes de publicar:

    AnonLab.NER_HUB.host = location.origin + "/fakehf/"   (no harness)
"""
import http.server
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "dist" / "anonlab-ner" / "models"
HUB = re.compile(r"^/fakehf/[^/]+/([^/?]+?)(?:-onnx)?/resolve/[^/]+/([^?]+)")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path):
        m = HUB.match(path)
        return str(MODELS / m.group(1) / m.group(2)) if m else super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # silencioso, menos os erros
        if len(args) > 1 and str(args[1])[:1] in "45":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"http://127.0.0.1:{port}/tests/harness.html  (fake HF em /fakehf/)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
