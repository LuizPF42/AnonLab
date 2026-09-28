# AnonLab ⚠️ EXPERIMENTAL

> [!CAUTION]
> ## ⚠️ SOFTWARE EXPERIMENTAL — SEM NENHUMA GARANTIA ⚠️
>
> **ESTE PROJETO É UM PROTÓTIPO DE PESQUISA, EM DESENVOLVIMENTO, FORNECIDO "COMO ESTÁ", SEM GARANTIA DE QUALQUER TIPO, EXPRESSA OU IMPLÍCITA.**
>
> - **ELE NÃO GARANTE ANONIMIZAÇÃO.** A ferramenta *sugere* o que remover e **ERRA**: pode deixar passar nomes, números, endereços e outros dados pessoais, e pode marcar o que não devia.
> - **REVISE O RESULTADO INTEIRO, À MÃO, ANTES DE COMPARTILHAR, PUBLICAR OU ANALISAR QUALQUER DOCUMENTO.**
> - Mesmo com os nomes trocados, combinações de detalhes (profissão rara + cidade pequena + data) podem **reidentificar** pessoas.
> - Os modelos de linguagem são de terceiros, foram treinados em outros tipos de texto e erram de forma imprevisível no seu material.
> - **Não é aconselhamento jurídico** e não substitui a avaliação do encarregado de dados (DPO) nem do comitê de ética da sua instituição.
> - Os autores e colaboradores **não se responsabilizam** por vazamentos, danos ou qualquer consequência do uso. Veja a [licença (MIT)](LICENSE).

Anonimizador de documentos para pesquisa que **roda inteiramente no
navegador**: o texto que você cola **nunca sai do seu computador**. Ele não é
enviado a nenhum servidor nem a nenhum modelo remoto; é o modelo que vem até o
navegador. A ferramenta sugere o que anonimizar, mostrando o trecho ao redor
para revisão, e substitui por pseudônimos consistentes (`[PESSOA_1]`,
`[ENDERECO_2]`…). Quem decide o que sai é o pesquisador. Aceita texto,
planilhas (CSV) e projetos do [QualiLab](https://github.com/LuizPF42/QualiLab)
(`.qualilab`), que saem pseudonimizados ou com a censura do QualiLab aplicada.

**Testar online:** <https://luizpf42.github.io/AnonLab/anonimizador.html>
(GitHub Pages). Também dá para baixar o `anonimizador.html` e abrir com duplo
clique. As duas formas fazem a mesma coisa, mas a cópia local permite auditar e
fixar exatamente o código que roda.

## Uso rápido

1. Abra o `anonimizador.html` (Chrome ou Edge recomendados; Firefox e Safari também funcionam).
2. Cole o texto ou abra um arquivo (`.txt`, `.csv` ou `.qualilab`), ajuste as categorias e clique em **Detectar candidatos**.
3. Revise a lista (aceitar/rejeitar), confira o resultado e **copie** ou **baixe**.

Sem nada além do HTML, a detecção usa padrões com validação (CPF, CNPJ, e-mail,
telefone, processo CNJ…), listas (estados, capitais, países), uma heurística
de nomes e os seus termos livres.

## Planilhas (CSV) e projetos do QualiLab

O arquivo inteiro passa pela mesma detecção e pela mesma revisão, de uma vez.
Por isso o mesmo nome recebe o mesmo rótulo em todas as linhas e documentos:
a "Maria Souza" da coluna Nome e a que aparece numa resposta aberta viram o
mesmo `[PESSOA_1]`. A revisão mostra onde está cada achado (linha e coluna, ou
documento, título, memo).

**CSV.** A planilha sai com a mesma estrutura: separador (`;`, `,`, tabulação,
detectado sozinho), aspas, quebras de linha dentro das células, cabeçalho. O
arquivo sai sempre em UTF-8; se o original era Windows-1252 (o "ANSI" do
Excel), sai com BOM para o Excel reconhecer. Para cada coluna você escolhe:

- **detectar no texto** (padrão): respostas abertas, observações;
- **inteira é pessoa / e-mail / CPF / telefone…**: a célula toda vira um
  rótulo, e o mesmo valor é trocado onde mais aparecer no arquivo;
- **manter como está**: a coluna não é tocada (idade, nota, carimbo de data/hora).

O cabeçalho sugere o tipo ("Nome", "E-mail", "CPF", "Telefone"…); confira antes
de detectar.

**QualiLab (`.qualilab`).** O projeto sai em duas versões possíveis:

| | Censurar | Destruir |
|---|---|---|
| texto dos documentos | intacto | com os pseudônimos (`[PESSOA_1]`) no lugar dos dados |
| o que muda | cada achado recebe o **código de censura** do QualiLab (⦸): a família nova `Censura (AnonLab)`, com um subcódigo por tipo, ou um código de censura que o projeto já tenha | todos os trechos codificados (e as discordâncias) são reancorados no texto novo; quem cobria um dado passa a cobrir o rótulo inteiro |
| no QualiLab | o texto aparece na sua tela e sai mascarado nos relatórios (ATI, W3C), no que vai para a IA e no servidor MCP | o dado não existe mais no arquivo |
| PDFs originais | vão junto | **não vão** (têm o texto cru) |
| tem volta? | sim: basta tirar a censura | não |

A censura do QualiLab não alcança título de documento, valor de categoria nem
memo, e é justamente ali que o nome costuma escapar ("ENT-01 — Dra. Fulana de
Tal"). Por isso, nas duas versões, o AnonLab pseudonimiza também títulos,
memos, valores e opções de categoria, comentários de conexão, conversas e
memória de IA, histórico e nomes de código (na censura dá para desligar).
Os espelhos (pontos de restauração) não vão para a cópia, como na exportação
do próprio QualiLab. A autoria (quem codificou) não é alterada.

A cópia tem o sufixo "censurado (AnonLab)" ou "pseudonimizado (AnonLab)" no
nome do projeto, e o histórico registra a operação. Ela serve de **cópia de
publicação** no fluxo que o manual do QualiLab recomenda (seção 12.4): o
original continua sendo o seu laboratório.

## Modelo de linguagem (NER, opcional)

Com um modelo de linguagem (BERT treinado para reconhecer entidades), a
detecção passa a entender o contexto. Ele acha nomes
no começo de frase ou em minúsculas, endereços ("Rua das Flores, nº 120",
"Jardim Esmeralda"), datas por extenso e outros dados que as regras não pegam.
Tudo o que o modelo acha num lugar é procurado também no resto do texto, para
nenhuma ocorrência escapar.

**O modelo vem até o navegador; o texto não vai a lugar nenhum.** No cartão
"Modelo de linguagem", clique em **🌐 Baixar modelos**. O navegador baixa os
modelos do Hugging Face uma vez (~490 MB na GPU, ~970 MB na CPU) e guarda para
as próximas visitas. A opção "carregar sozinho ao abrir" já vem marcada. Não é
preciso conta em lugar nenhum: são modelos que outras pessoas já publicaram em
ONNX (o mesmo esquema do QualiLab com o modelo do Xenova). O modelo roda **no
próprio computador**, pelo
[transformers.js](https://github.com/huggingface/transformers.js) com
onnxruntime-web: na **GPU via WebGPU** ou, se não houver, na **CPU via
WebAssembly**.

Por padrão rodam dois modelos juntos:

| modelo | acha | licença | GPU (WebGPU) | CPU (WASM) |
|---|---|---|---|---|
| [`dominguesm/legal-bert-ner-base-cased-ptbr`](https://huggingface.co/dominguesm/legal-bert-ner-base-cased-ptbr), em ONNX por [`augustaklug`](https://huggingface.co/augustaklug/legal-bert-ner-base-cased-ptbr-onnx) | pessoas, organizações, locais, datas (BERT jurídico em português) | CC-BY-4.0 | fp16, 207 MB | fp32, 414 MB |
| [`OpenMed/OpenMed-PII-Portuguese-mLiteClinical-Base-135M-v1`](https://huggingface.co/OpenMed/OpenMed-PII-Portuguese-mLiteClinical-Base-135M-v1), em ONNX pela própria [OpenMed](https://huggingface.co/OpenMed/OpenMed-PII-Portuguese-mLiteClinical-Base-135M-v1-onnx-android) | dados pessoais: nomes, endereços, documentos, contas, contatos (54 tipos) | Apache-2.0 | fp16, 257 MB | fp32, 514 MB |

**Como foram escolhidos** (RTX 3060, Ryzen 5 5500). Cinco documentos fictícios
(entrevista, prontuário, petição, diário de campo, ofício de RH), com 90 dados
pessoais, aceitando só o que já vem marcado. "Vazou" conta também o vazamento
parcial (sobrou um sobrenome ou um número):

| configuração | vazou (rodada 1) | vazou (rodada 2) | substituições indevidas (rodada 2) |
|---|---|---|---|
| sem modelo | 59 | 50 | 0 |
| legal-bert-lgpd + HAREM (convertidos por nós; exigem publicar) | 5 | 0 | 1 |
| legal-bert-ner (dominguesm) | 10 | 1 | 0 |
| BERTimbau NER HAREM (NeuralMind), ONNX de rchuluc | 9 | 1 | 1 |
| mBERT NER multilíngue (Davlan), ONNX do Xenova | 12 | 3 | 1 |
| OpenMed PII | 25 | 19 | 0 |
| **legal-bert-ner + OpenMed (padrão)** | **4** | **0** | **0** |

A rodada 2 veio depois de corrigir falhas que independem do modelo e que os
dois documentos novos revelaram: SIAPE e conta bancária sem detector; `@` de
rede social desligado; trecho do modelo com confiança baixa passando por cima
de regras certas; endereço marcado como LOCAL sem o número. Como esses
documentos ajudaram a achar as falhas, a rodada 2 vale como regressão, não
como benchmark. Na rodada 1, os dois documentos novos ainda eram inéditos, e
neles o padrão já ficou à frente: 4 vazamentos, contra 5 do LGPD + HAREM.

- **Fidelidade** das nossas conversões ao PyTorch fp32 (F1 de entidades, 315
  textos, ~22 mil tokens): fp16 1,000; q4 0,977. No navegador, a GPU
  reproduz a referência com F1 0,997 (LGPD) e 0,994 (HAREM). O tokenizador do
  AnonLab bate 100% com o do Hugging Face nos seis modelos testados.
- **Velocidade:** na GPU, ~80 ms por janela de 512 tokens (modelo Large), e uma
  página sai em menos de 1 s. Na CPU, com até 4 workers em paralelo, é bem
  mais lenta para documentos longos.

### Outros modelos (convertidos por você)

Modelos que só existem em PyTorch, como o
[`celiudos/legal-bert-lgpd`](https://huggingface.co/celiudos/legal-bert-lgpd),
podem ser convertidos e usados pela pasta local ou publicados:

```bash
uv run tools/build_ner_pack.py                           # converte e valida → dist/anonlab-ner/ (~1,2 GB)
hf auth login                                            # uma vez, token com escrita
uv run tools/publish_hub.py --user SEU_USUARIO_HF        # publica <usuário>/<modelo>-onnx
```

O `publish_hub.py` cria um repositório por modelo, com um model card que
credita o original, e acrescenta ao catálogo do `anonimizador.html`
(`NER_HUB`) o commit publicado. Ele se recusa a publicar derivados de modelos
sem licença declarada. Atenção: o `legal-bert-lgpd` se declara MIT, mas foi
treinado a partir de um modelo sem licença (`pierreguillou/ner-bert-large-cased-pt-lenerbr`).

### Modo offline (pasta local)

Para trabalhar sem internet, a mesma pasta `dist/anonlab-ner/` pode ser
copiada (pendrive, rede interna…) e aberta pelo botão **📦 pasta local**, ou
arrastada para o cartão. Nesse modo nada é baixado.

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

### Privacidade: o texto não sai do navegador

- Todo o processamento (regras, listas e modelo) acontece **na sua máquina**.
  Nenhum servidor recebe o documento. A rede só é usada para *baixar* o modelo.
- A página tem uma **Content-Security-Policy** que só permite conexões com o
  jsDelivr (runtime) e o Hugging Face (modelos), inclusive no worker do
  modelo. Não há analytics, fontes ou imagens externas.
- O runtime (transformers.js + onnxruntime-web, 27 MB) **só é executado se o
  SHA-256 bater** com os valores fixados no `anonimizador.html`
  (`NER_RUNTIME`). Os modelos vêm de uma revisão fixa do repositório no Hugging
  Face.
- O transformers.js recebe um `fetch` próprio, que só busca no host dos
  modelos (ou só na pasta, no modo offline). Qualquer outro endereço recebe 404
  sem sair da máquina.
- A versão no GitHub Pages carrega o código do GitHub a cada visita. Quem quiser
  fixar e auditar exatamente o que roda pode baixar o `anonimizador.html` e
  abrir localmente.

## Testes

```bash
node tests/test_ner_core.mjs          # tokenizador, janelas e agregação vs. Python/HF
node tests/test_formats.mjs           # CSV, zip, NFC, reancoramento, .qualilab (censurar e destruir)
```

O `test_formats.mjs --out PASTA` grava as saídas de um projeto de teste, e o
`verify_qualilab.mjs` confere uma saída com o **código do próprio QualiLab**:
o núcleo do servidor MCP do [QualiLab-plugin](https://github.com/LuizPF42/QualiLab-plugin)
(extraído do app) abre o arquivo e responde como responderia a uma IA. Nenhum
dado aceito pode aparecer, a busca por ele não pode achar nada e nenhuma âncora
de censura pode estar quebrada:

```bash
node tests/verify_qualilab.mjs saida.qualilab codebook_REIDENTIFICA.csv --plugin ../QualiLab-plugin/plugins/qualilab/server
```

Os vetores de `tests/vectors/` vêm do Python, com o tokenizador e o modelo
originais:

- `tok-*.json`: tokenização dos modelos padrão
  (`uv run tools/tokenizer_vectors.py REPO REVISAO`). O teste baixa o
  `tokenizer.json` da revisão fixa para `tests/.cache/`.
- os demais: tokenização, janelas e agregação dos modelos do pacote
  (`build_ner_pack.py --vectors tests/vectors`), pulados se
  `dist/anonlab-ner/` não existir.

Os testes no navegador usam `tests/harness.html`, que carrega o anonimizador
num iframe. O `tests/fake_hf.py` serve o repositório e imita o Hugging Face em
`/fakehf/`, a partir de `dist/anonlab-ner/`, para testar o download antes de
publicar:

```bash
python tests/fake_hf.py 8765
```

Abra `http://localhost:8765/tests/harness.html` e, no console:

```js
await harness.evalGolden()                     // vazamento sem modelo
await harness.openFakeHub()                    // "🌐 Baixar modelos" contra o HF falso
await harness.evalGolden()                     // vazamento com os modelos
// ou o modo offline: await harness.app().openNerPack(await harness.loadPack(undefined, ["fp16"]))
const o = await harness.runFile("qualilab_demo.qualilab")   // abre tests/fixtures/, detecta, monta a saída
await harness.save("saida.qualilab", o.bytes)  // → tests/.cache/out/, para o verify_qualilab.mjs
```

`tests/fixtures/` tem um CSV de pesquisa fictício e o projeto de demonstração
do QualiLab (`examples/` do repositório dele, dados sintéticos, MIT).

## Desenho

A especificação completa (princípios, camadas, categorias, roadmap) está em
[`claude.md`](claude.md).

## Créditos

O AnonLab junta trabalho de muita gente. Os modelos, bibliotecas e dados
abaixo pertencem aos seus autores e seguem as próprias licenças.

**Modelos de linguagem (Hugging Face)**

| modelo | autoria | licença | papel no AnonLab |
|---|---|---|---|
| [dominguesm/legal-bert-ner-base-cased-ptbr](https://huggingface.co/dominguesm/legal-bert-ner-base-cased-ptbr) | [dominguesm](https://huggingface.co/dominguesm), treinado com documentos do STF ([projeto VICTOR](https://ailab.unb.br/victor/lrec2020), LREC 2020). Conversão para ONNX: [augustaklug](https://huggingface.co/augustaklug/legal-bert-ner-base-cased-ptbr-onnx), usada sem alterações | CC-BY-4.0 | **padrão**: pessoas, organizações, locais, datas |
| [OpenMed/OpenMed-PII-Portuguese-mLiteClinical-Base-135M-v1](https://huggingface.co/OpenMed/OpenMed-PII-Portuguese-mLiteClinical-Base-135M-v1) | [OpenMed](https://huggingface.co/OpenMed), a partir do [DistilBERT multilíngue](https://huggingface.co/distilbert/distilbert-base-multilingual-cased), com dados da [AI4Privacy](https://huggingface.co/datasets/ai4privacy/pii-masking-200k) e da NVIDIA (Nemotron-PII). ONNX publicado pela própria OpenMed | Apache-2.0 | **padrão**: dados pessoais (documentos, contas, endereços, contatos) |
| [celiudos/legal-bert-lgpd](https://huggingface.co/celiudos/legal-bert-lgpd) | Marcelo Anselmo de Souza Filho. Dissertação *Inteligência Artificial no MPF: Uma Solução Baseada em IA para Pseudonimização de Dados Pessoais* (UnB, 2025) | MIT | opcional, convertido por você (dados pessoais da LGPD) |
| [liaad/NER_harem_bert-base-portuguese-cased](https://huggingface.co/liaad/NER_harem_bert-base-portuguese-cased) | [LIAAD, INESC TEC](https://huggingface.co/liaad) | MIT | opcional, convertido por você (organizações e locais) |
| [marquesafonso/bertimbau-large-ner-total](https://huggingface.co/marquesafonso/bertimbau-large-ner-total) | BERT-CRF da NeuralMind (HAREM, cenário total), publicado por marquesafonso. ONNX de [rchuluc](https://huggingface.co/rchuluc/bertimbau-large-ner-total-onnx) | MIT | testado na comparação (fora do padrão) |
| [Davlan/bert-base-multilingual-cased-ner-hrl](https://huggingface.co/Davlan/bert-base-multilingual-cased-ner-hrl) | [Davlan](https://huggingface.co/Davlan). ONNX do [Xenova](https://huggingface.co/Xenova/bert-base-multilingual-cased-ner-hrl) | AFL-3.0 | testado na comparação (fora do padrão) |
| [pierreguillou/ner-bert-large-cased-pt-lenerbr](https://huggingface.co/pierreguillou/ner-bert-large-cased-pt-lenerbr) | Pierre Guillou | não declarada | base do legal-bert-lgpd; preset `lenerbr` |
| [neuralmind/bert-base-portuguese-cased](https://huggingface.co/neuralmind/bert-base-portuguese-cased) e [neuralmind/bert-large-portuguese-cased](https://huggingface.co/neuralmind/bert-large-portuguese-cased) (BERTimbau) | Fábio Souza, Rodrigo Nogueira e Roberto Lotufo, NeuralMind ([portuguese-bert](https://github.com/neuralmind-ai/portuguese-bert)) | MIT | base do legal-bert-lgpd, do HAREM do LIAAD e do BERT-CRF da NeuralMind |
| [rufimelo/Legal-BERTimbau-base](https://huggingface.co/rufimelo/Legal-BERTimbau-base) | Rui Melo | MIT | referência (ainda não usado: é um modelo de base, sem a parte de NER) |

**Software**

- [transformers.js](https://github.com/huggingface/transformers.js) (Hugging Face, Apache-2.0): carrega e roda os modelos no navegador.
- [ONNX Runtime Web](https://github.com/microsoft/onnxruntime) (Microsoft, MIT): execução em WebGPU e WebAssembly.
- Na conversão dos modelos (`tools/build_ner_pack.py`): [PyTorch](https://github.com/pytorch/pytorch), [🤗 Transformers](https://github.com/huggingface/transformers), [ONNX](https://github.com/onnx/onnx), [onnxconverter-common](https://github.com/microsoft/onnxconverter-common) e [huggingface_hub](https://github.com/huggingface/huggingface_hub).
- [QualiLab](https://github.com/LuizPF42/QualiLab) e [QualiLab-plugin](https://github.com/LuizPF42/QualiLab-plugin) (MIT): o formato `.qualilab`, a censura (`is_redaction`), o projeto de demonstração usado nos testes e o núcleo do servidor MCP usado para conferir as saídas. Nos testes do navegador, o [JSZip](https://github.com/Stuk/jszip) (MIT ou GPL-3.0), que o QualiLab usa para o `.qualilab` com PDF, confere a compatibilidade dos zips.

**Dados e referências**

- [LeNER-Br](https://github.com/peluz/lener-br) (Luz de Araujo et al., PROPOR 2018): frases de teste usadas para validar as versões quantizadas dos modelos. Só no build; não são redistribuídas.
- [HAREM](https://www.linguateca.pt/HAREM/) (Linguateca): corpus em que o modelo do LIAAD foi treinado.
- [anonimizador-dp](https://github.com/anatelgovbr/anonimizador-dp) (Anatel, GPL-3.0): referência de detectores com validação (CNS, RG etc.). Nenhum código foi copiado.
- Raquel Alexandra Moleira Domingos, *Aperfeiçoamento de Tecnologias de Anonimização para o Contexto de Dados Não Estruturados* (dissertação de mestrado, Faculdade de Ciências da Universidade de Lisboa, 2025). Comparação de modelos de NER para anonimização em português; inspirou o uso de modelos por domínio.
