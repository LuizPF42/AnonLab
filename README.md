# AnonLab

Anonimizador de documentos **offline (airgapped)** para pesquisa. É um único
`anonimizador.html`: abre com duplo clique no navegador, não instala nada e não
acessa a rede. A ferramenta sugere o que anonimizar, mostrando o trecho ao
redor para revisão, e substitui por pseudônimos consistentes (`[PESSOA_1]`,
`[ENDERECO_2]`…). Quem decide o que sai é o pesquisador.

## Uso rápido

1. Abra `anonimizador.html` (Chrome ou Edge recomendados; Firefox e Safari também funcionam).
2. Cole o texto ou abra um `.txt`, ajuste as categorias e clique em **Detectar candidatos**.
3. Revise a lista (aceitar/rejeitar), confira o resultado e **copie** ou **baixe**.

Sem nada além do HTML, a detecção usa padrões com validação (CPF, CNPJ, e-mail,
telefone, processo CNJ…), listas (estados, capitais, países), uma heurística
de nomes e os seus termos livres.

## Modelo de linguagem (NER, opcional)

Com o **pacote NER**, a detecção passa a usar um modelo BERTimbau que entende o
contexto. Ele acha nomes no começo de frase ou em minúsculas, endereços
("Rua das Flores, nº 120", "Jardim Esmeralda"), datas por extenso e outros
dados que as regras não pegam. Tudo o que o modelo acha num lugar é procurado
também no resto do texto, para nenhuma ocorrência escapar.

O modelo roda **no próprio computador**, pelo [transformers.js](https://github.com/huggingface/transformers.js)
com onnxruntime-web: na **GPU via WebGPU** ou, se não houver, na **CPU via WebAssembly**.

O pacote padrão traz dois modelos, que rodam juntos na GPU:

| modelo | acha | GPU (WebGPU) | CPU (WASM) |
|---|---|---|---|
| [`celiudos/legal-bert-lgpd`](https://huggingface.co/celiudos/legal-bert-lgpd) (BERTimbau Large, MIT) | dados pessoais da LGPD: NOME, ENDERECO, DATA, CPF, TELEFONE, EMAIL, DINHEIRO, CEP | fp16, 638 MB | q4, 306 MB |
| [`liaad/NER_harem_bert-base-portuguese-cased`](https://huggingface.co/liaad/NER_harem_bert-base-portuguese-cased) (BERTimbau Base, MIT) | domínio geral: PESSOA, **ORGANIZACAO**, **LOCAL**, TEMPO… | fp16, 208 MB | — (as versões quantizadas foram reprovadas) |

**Resultados medidos** (RTX 3060, Ryzen 5 5500).

*Vazamento* em três documentos fictícios (entrevista, prontuário, petição), com
54 dados pessoais, aceitando só o que já vem marcado:

| configuração | dados que sobraram no texto |
|---|---|
| sem o modelo | 32 de 54 |
| só o LGPD | 1 de 54 (o nome de uma escola) |
| LGPD + HAREM | **0 de 54**, sem substituir nada indevido |

Os documentos (`tests/golden/docs.json`) foram escritos junto com os ajustes de
pós-processamento. Valem como teste de regressão, não como benchmark.

- **Fidelidade** ao PyTorch fp32 (F1 de entidades, 315 textos, ~22 mil
  tokens): fp16 1,000; q4 0,977. No navegador, a GPU reproduz a referência
  com F1 0,997 (LGPD) e 0,994 (HAREM).
- **Velocidade:** na GPU, ~80 ms por janela de 512 tokens, e uma página sai em
  menos de 1 s. Na CPU, ~12 s por janela por thread, com até 4 workers em
  paralelo; é lenta para documentos longos.

### Obter o pacote

O pacote é gerado **uma vez**, numa máquina com internet, e copiado (pendrive,
rede interna…) para a máquina airgapped:

```bash
uv run tools/build_ner_pack.py
```

Isso cria `dist/anonlab-ner/` (~1,2 GB). No anonimizador, clique em **Carregar
pacote NER** e selecione essa pasta, ou arraste a pasta para o cartão.

Outros modelos (é possível pôr vários no mesmo pacote e usá-los juntos):

```bash
uv run tools/build_ner_pack.py --list
uv run tools/build_ner_pack.py --model lgpd lenerbr
```

| preset | modelo | quando usar |
|---|---|---|
| `lgpd` (padrão) | `celiudos/legal-bert-lgpd` | dados pessoais; textos jurídicos e administrativos |
| `harem` (padrão) / `harem-large` | `liaad/NER_harem_bert-{base,large}-portuguese-cased` | domínio geral (entrevistas, notícias, web); organizações e locais |
| `lenerbr` / `lenerbr-base` | `pierreguillou/ner-bert-{large,base}-cased-pt-lenerbr` | pessoas, organizações e locais em textos jurídicos (sem licença declarada) |

Qualquer BERT de *token classification* do Hugging Face serve (`--model org/nome`).
Cada variante ONNX é comparada com o modelo original e **descartada** se
divergir além do limite (`MIN_ENTITY_F1` no script).

### Por que continua airgapped

- A página tem uma **Content-Security-Policy** que proíbe qualquer acesso à
  rede (`connect-src blob: data:`). O navegador bloqueia até o worker do modelo.
- O transformers.js recebe um `fetch` próprio que só entrega arquivos do pacote
  (qualquer outro endereço recebe 404 sem sair da máquina). Downloads remotos e
  cache do navegador ficam desligados.
- O runtime (JS e WASM) **só é executado se o SHA-256 bater** com os valores
  fixados no `anonimizador.html` (`NER_RUNTIME`). Os arquivos do modelo são
  conferidos contra o manifesto do pacote.

## Testes

```bash
node tests/test_ner_core.mjs          # tokenizador, janelas e agregação vs. Python/HF
```

`tests/vectors/*.json` é gerado pelo build (`--vectors tests/vectors`) com o
tokenizador e o modelo originais.

Os testes no navegador usam `tests/harness.html`, que carrega o anonimizador
num iframe e injeta o pacote (a CSP do anonimizador bloqueia até o localhost):

```bash
python -m http.server 8765
```

Abra `http://localhost:8765/tests/harness.html` e, no console:

```js
await harness.evalGolden()                                            // vazamento sem modelo
await harness.app().openNerPack(await harness.loadPack(undefined, ["fp16"]))
await harness.evalGolden()                                            // vazamento com modelos
```

## Desenho

A especificação completa (princípios, camadas, categorias, roadmap) está em
[`claude.md`](claude.md).
