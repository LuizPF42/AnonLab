# Anonimizador de Documentos (airgapped)

Ferramenta **local, offline e sem instalador** para ajudar pesquisadores a
de-identificar documentos (entrevistas, prontuários, autos, transcrições, etc.)
antes de compartilhar ou analisar. Pensada para o contexto brasileiro (LGPD,
CPF/CNPJ/CNS, etc.).

> Status: **especificação + v1** (`anonimizador.html`), com NER opcional por
> modelo BERTimbau (transformers.js + WebGPU, seção 2.1).
> Este arquivo é a fonte da verdade do design. A implementação cobre um
> subconjunto; o que falta está no roadmap (seção 11).

---

## 1. Princípios (não-negociáveis)

1. **Airgapped de verdade.** Zero requisições de rede. Nada de CDN, fontes
   externas, analytics, telemetria. Tudo embutido em um único arquivo. O dado
   do pesquisador **nunca sai da máquina**. Uma CSP no próprio HTML faz o
   navegador *impor* isso (inclusive ao worker do modelo).
2. **Sem instalador.** Um único `anonimizador.html`. Abre com duplo clique em
   qualquer navegador moderno (funciona via `file://`). Nada de Python, Node,
   build, servidor. Única exceção, e opcional: o **pacote NER** (modelo de
   ~1 GB, grande demais para caber no HTML) é uma pasta local que o
   pesquisador seleciona. Continua offline, sem instalação, e o HTML funciona
   completo sem ela. Gerar o pacote exige Python, mas numa máquina de build
   com internet, uma única vez (`tools/build_ner_pack.py`).
3. **Pesquisador no controle.** A ferramenta **sugere**; a pessoa **decide**.
   Nada é removido automaticamente sem revisão (exceto, opcionalmente, padrões
   de altíssima confiança como CPF validado).
4. **Pseudonimização consistente.** O mesmo nome/entidade vira sempre o mesmo
   rótulo no documento inteiro (`[PESSOA_1]` em todo lugar), preservando a
   estrutura analítica do texto.
5. **Transparência sobre limites.** A ferramenta assiste, não garante anonimato.
   Avisa sobre risco de re-identificação por quase-identificadores.

---

## 2. Arquitetura técnica

- **Single-file HTML** com CSS e JS embutidos (`<style>` + `<script>` inline).
- Roda 100% no navegador, em memória. Entrada por **colar texto** ou **upload**
  (`<input type=file>` + `FileReader`) — tudo client-side.
- Saída por **copiar** ou **baixar** (`Blob` + âncora `download`).
- Fonte: *system font stack* (sem webfont). Cores e ícones inline (SVG/emoji).
- Sem `fetch`/`XMLHttpRequest`/`import` remoto. Dá pra auditar com um Ctrl+F por
  `http`/`fetch` no arquivo — não deve haver nenhum externo.

### Por que navegador e não .exe?
- Sem instalador, sem antivírus reclamando de binário, multiplataforma
  (Windows/Mac/Linux), auditável (é texto), e o sandbox do navegador é uma
  garantia extra de que nada vaza.

### 2.1 Modelo de linguagem (NER) — pacote opcional

**Pacote** (`dist/anonlab-ner/`, gerado por `tools/build_ner_pack.py`):

```
anonlab-ner.json          manifesto: versões e SHA-256 de cada arquivo
runtime/                  transformers.js 4.3.0 + onnxruntime-web (asyncify: WASM + WebGPU)
models/<slug>/            anonlab-model.json (rótulos, label_map, variantes, validação),
                          config.json, tokenizer.json, onnx/model_<dtype>.onnx
```

**Como roda no navegador:**
- O pesquisador seleciona a pasta (`<input webkitdirectory>` ou arrastar).
  Os arquivos viram `File` e vão para um **Web Worker** (blob:, módulo).
- O worker confere o SHA-256 do runtime contra `NER_RUNTIME`, **fixado no
  HTML** (a raiz de confiança é o HTML, não o pacote), e importa o
  transformers.js de um blob:. Os arquivos do modelo são conferidos contra o
  manifesto (tamanho e SHA-256).
- O `env.fetch` do transformers.js é substituído por um "sistema de arquivos"
  em memória: só entrega arquivos do pacote, e o resto recebe 404 sem sair
  da máquina. `allowRemoteModels=false`, caches desligados, `wasmBinary` e
  `wasmPaths.mjs` apontam para os blobs verificados.
- **Dispositivo:** WebGPU quando disponível. fp16 exige `shader-f16`; sem ele,
  usa q4 ou fp32. A CPU (WASM) é o fallback automático se a GPU recusar.
  Em `file://` não há `SharedArrayBuffer`, então o WASM roda numa thread; por
  isso a CPU usa **várias pistas** (2 a 4 workers, cada um com uma cópia do
  modelo) e divide o texto em trechos cortados em quebra de linha.
- O pipeline de NER do transformers.js não dá offsets e trunca em 512 tokens.
  Por isso o AnonLab tem o próprio **tokenizador BERT com offsets**
  (`<script id="ner-core">`), **janelas** de 512 tokens com sobreposição de
  128 (cada token usa a janela em que está mais ao centro) e a **agregação
  "first"** do HF. O transformers.js só roda o modelo. O `ner-core` é testado
  contra vetores gerados em Python (`tests/test_ner_core.mjs`).
- **CSP** do HTML: `default-src 'none'; script-src 'unsafe-inline' blob:
  'wasm-unsafe-eval'; worker-src blob:; connect-src blob: data:`. Não precisou
  de `'unsafe-eval'`.
- **Vários modelos** rodam juntos e as entidades se somam. O pacote padrão tem
  `legal-bert-lgpd` (dados pessoais; não tem ORGANIZACAO/LOCAL) e HAREM Base
  (geral; tem ORGANIZACAO/LOCAL). Na GPU os dois carregam sozinhos; na CPU, só
  o primeiro. Modelo sem variante para o dispositivo aparece desabilitado.
- O **Detectar espera** o pacote e os modelos terminarem de carregar.

---

## 3. Fluxo de uso

```
  [1] Entrada          [2] Detecção            [3] Revisão com contexto
  cola/upload   --->   camadas rodam      ---> lista de candidatos (KWIC),
  do texto             e geram candidatos      aceitar/rejeitar/editar
                                                      |
                                                      v
  [5] Saída            [4] Substituição
  copia/baixa    <---  pseudonimização
  + codebook?          consistente por tipo
```

1. **Entrada** — colar ou subir `.txt` (v0). Futuro: `.docx`, `.csv`, `.pdf`.
2. **Detecção** — marcam-se as *caixinhas* (categorias) desejadas + termos
   livres. As camadas varrem o texto e produzem candidatos.
3. **Revisão com contexto** — cada candidato aparece com um trecho ao redor
   (KWIC = *keyword in context*), tipo, contagem de ocorrências e rótulo
   proposto. O pesquisador aceita/rejeita/edita/funde entidades.
4. **Substituição** — os aceitos viram rótulos por tipo, de forma consistente.
5. **Saída** — texto anonimizado (copiar/baixar). Opcional: *codebook* (chave
   original→rótulo) **em arquivo separado**, com aviso de que reidentifica.

---

## 4. Camadas de detecção

A força da ferramenta é combinar cinco camadas, da mais precisa à mais
heurística. As quatro últimas alimentam **sugestões revisáveis**.

| Camada | O que é | Precisão | Tratamento |
|---|---|---|---|
| **1. Padrões estruturados (regex)** | CPF, CNPJ, e-mail, telefone, CEP, datas, processo CNJ, cartão, IP… | Alta (alguns com validação de dígito) | Pode auto-aplicar ou sugerir já marcado |
| **2. Modelo de linguagem (NER BERTimbau)** — opcional | nomes, endereços, organizações, locais, datas, CPF/telefone/e-mail (conforme o modelo) | Alta em contexto (F1 ~0,95 em nomes no legal-bert-lgpd) | Sugestão com score; ≥0,9 alta, ≥0,7 média, senão baixa (<0,35 descartado) |
| **3. Listas / gazetteer (as "caixinhas")** | 27 estados+UF, capitais, países, pronomes de tratamento, sufixos de empresa | Média-alta | Sugere quando a caixinha está ligada |
| **4. Heurística de nomes próprios (NER leve)** | sequências capitalizadas (com conectores "da/de/do") fora de início de frase | Média (gera falso-positivo de propósito) | Sempre sugestão revisável no contexto |
| **5. Termos livres do pesquisador** | lista custom (nomes, apelidos, codinomes, locais específicos) | Definida pelo usuário | Match exato/palavra inteira, com opção case-insensitive |

Notas de implementação:
- **Validação de dígito** em CPF/CNPJ (mod 11) e cartão (Luhn) corta muito
  falso-positivo. Vale a pena.
- **Resolução de sobreposição:** ao detectar, vários padrões podem casar o mesmo
  trecho. Precedência: estruturado validado > termo livre > estruturado >
  NER (texto) > gazetteer > heurística; em empate, **o casamento mais longo**
  vence. Para dados estruturados (CPF, telefone, data…), o NER fica logo
  *abaixo* do padrão equivalente: o regex acerta a extensão, e o NER só
  acrescenta o que o regex não pegou (CPF com dígito errado, "março de 2020").
- **Pós-processamento do NER:** (a) junta pedaços da mesma entidade (o BERT
  parte "14.05.2013" em 3); (b) LOCAL/ENDERECO que casa exatamente com uma
  lista vira CIDADE/ESTADO/PAIS; (c) o número depois de uma rua ("Rua X,
  nº 120") entra no endereço; (d) **propagação**: o que o modelo achou num
  lugar é buscado no texto todo, porque o NER às vezes perde ocorrências.
- **Pós-processamento, continuação:** (e) pronome de tratamento sai da ponta
  do nome ("Sr. Benedito" → "Benedito"; senão vira outra entidade); (f) "nome"
  feito só de cargos ("JUIZ DE DIREITO DA") é descartado; (g) "bairro
  Eldorado" também propaga "Eldorado"; (h) complemento ("apto. 302", "bloco
  B") entra no endereço.
- **União do mesmo tipo:** se um span descartado estende um mantido do mesmo
  tipo ("Geraldo" do modelo e "Geraldo Figueiredo" da heurística), vale a
  união. Sem isso o sobrenome escapa. Para PESSOA, a extensão precisa ter cara
  de nome (palavras capitalizadas, espaço simples) e não pode ser pronome de
  tratamento.
- **Camadas que concordam** no mesmo trecho reforçam a confiança (vale a
  maior) e aparecem juntas na revisão ("modelo + lista"), desde que os tipos
  sejam compatíveis (iguais, ou ambos de lugar). Exemplo: o modelo marca
  "Jardim Aurélia" com 0,65 (baixa) e a heurística de bairro com confiança
  média; o resultado sai média e já vem aceito.
- **Um tipo por valor:** o mesmo texto recebe sempre o mesmo tipo, o do span
  de maior precedência. Sem isso, "Recife" viraria LOCAL aqui e CIDADE ali,
  com pseudônimos diferentes.
- **Substituir do mais longo pro mais curto** evita quebrar entidades aninhadas
  ("Dr. João Silva" antes de "Silva").
- A entrada é normalizada para **NFC**. Texto decomposto (NFD, comum vindo do
  macOS) quebraria as listas e o vocabulário do BERT.

---

## 5. A lista grande de "caixinhas" (categorias sugeridas)

Organizada por grupo. As marcadas com 🔴 são **dados sensíveis** pela LGPD
(art. 5º, II) e merecem atenção redobrada. ⚙️ = tem detector automático viável;
✋ = depende mais de heurística/termo livre.

### Identificadores / documentos
- ⚙️ CPF
- ⚙️ CNPJ
- ⚙️ RG (formato varia por estado — detector frouxo)
- ⚙️ CNH (nº de registro)
- ⚙️ Título de eleitor
- ⚙️ PIS / PASEP / NIT / NIS
- ⚙️ CNS — Cartão Nacional de Saúde (SUS) 🔴
- ⚙️ Passaporte
- ⚙️ Número de processo judicial (padrão CNJ `NNNNNNN-DD.AAAA.J.TR.OOOO`)
- ✋ Certidões (nascimento/casamento/óbito) — nº de matrícula
- ⚙️ Inscrição estadual / municipal
- ⚙️ RENAVAM
- ⚙️ Placa de veículo (antiga `ABC-1234` e Mercosul `ABC1D23`)
- ⚙️ Chassi (VIN)
- ✋ Registros profissionais: OAB, CRM, CREA, COREN, CRP…

### Contato e rede
- ⚙️ Telefone fixo (com/sem DDD)
- ⚙️ Celular
- ⚙️ E-mail
- ⚙️ CEP
- ✋ Endereço (logradouro + número) — heurística (Rua/Av./Travessa + …)
- ⚙️ URL / site
- ⚙️ @handle / redes sociais
- ⚙️ Endereço IP (v4/v6)
- ⚙️ MAC address

### Financeiro
- ⚙️ Cartão de crédito (Luhn)
- ⚙️ Agência e conta bancária
- ⚙️ Chave PIX (pode ser CPF / e-mail / telefone / aleatória)
- ⚙️ IBAN
- ⚙️ Valores monetários (R$) — *opcional; costuma ser ruído*

### Localização geográfica
- ⚙️ Estados (27 nomes + siglas UF)
- ⚙️ Capitais
- ✋ Municípios (lista grande — top N embutível; trade-off de tamanho)
- ✋ Bairros (livre/heurística)
- ⚙️ Países
- ✋ Nacionalidades / gentílicos

### Pessoas e atributos
- ✋ Nomes próprios (heurística de capitalização) — **o grande caso de uso**
- ⚙️ Pronomes de tratamento (Dr./Dra./Sr./Sra.) — usados como *pista* p/ nomes
- ⚙️ Datas (vários formatos) — nascimento e gerais
- ⚙️ Idade ("42 anos")
- ✋ Gênero / sexo
- ✋ Profissão / cargo
- ✋ Estado civil
- ✋ Raça / cor / etnia 🔴
- ✋ Religião 🔴
- ✋ Opinião política / filiação partidária 🔴
- ✋ Orientação sexual 🔴

### Saúde 🔴 (sensível)
- ✋ CID-10 (códigos `A00`–`Z99` + dígito)
- ✋ Nome de doença / condição
- ✋ Medicamentos
- ✋ Nome de hospital / clínica
- ⚙️ Número de prontuário
- ✋ Tipo sanguíneo
- ✋ Dados biométricos (menção) 🔴

### Organizações / instituições
- ✋ Empresas (heurística + sufixos `Ltda`, `S.A.`, `ME`, `EIRELI`)
- ✋ Escolas / universidades
- ✋ Órgãos públicos

### Datas e tempo
- ⚙️ Data (formatos `00/00/0000`, `00.00.00`, "12 de março de 2020")
- ⚙️ Hora
- ✋ Ano isolado (cuidado: muito falso-positivo)

### Genéricos / outros
- ⚙️ Sequências numéricas longas (catch-all configurável)
- ⚙️ Coordenadas GPS
- ✋ **Termos livres do pesquisador** (sempre disponível)

> Para a UI: agrupar em acordeões por esses grupos, com "marcar grupo inteiro".
> Sugestão de **presets**: "Entrevista qualitativa", "Prontuário/saúde",
> "Processo judicial", "Mínimo (só documentos)".

---

## 6. Estratégia de substituição

Três modos possíveis; **padrão recomendado = pseudônimo com tag de tipo**.

| Modo | Exemplo | Quando usar |
|---|---|---|
| **Tag de tipo + contador** (padrão) | `João Silva` → `[PESSOA_1]`, `Recife` → `[CIDADE_1]` | Pesquisa: preserva relações ("PESSOA_1 mora em CIDADE_1") |
| **Tarja / redação** | `João Silva` → `█████` ou `[REMOVIDO]` | Quando nem o tipo pode aparecer |
| **Rótulo genérico** | tudo → `[REMOVIDO]` | Máxima opacidade |

Regras do modo padrão:
- Contador **por tipo**: `[PESSOA_1]`, `[PESSOA_2]`, `[CIDADE_1]`, `[CPF_1]`…
- **Consistência**: mapa `valor → rótulo`; mesma entidade = mesmo rótulo sempre.
- **Fusão de entidades**: permitir marcar "João", "João Silva" e "Dr. Silva"
  como a mesma `[PESSOA_1]` (UI de merge).
- Rótulos **legíveis e estáveis** facilitam reler a análise depois.

---

## 7. Revisão "com contexto" — o diferencial

Resposta direta ao pedido *"algo para sugerir com contexto"*: cada candidato é
mostrado em **KWIC** (palavra-no-contexto), não numa lista solta.

Para cada entidade candidata, a linha de revisão mostra:
- ✅/❌ aceitar/rejeitar (atalho de teclado);
- o **trecho**: `…assinado por **João Silva** no dia 3…` (match destacado);
- **tipo** detectado e **confiança** (alta/média/baixa);
- **nº de ocorrências** (clica e navega entre elas);
- **rótulo proposto** (editável);
- ação **fundir com…** outra entidade.

Comportamentos úteis:
- Ordenar por confiança (mostrar incertos primeiro) ou por frequência.
- "Aceitar todos de alta confiança" / "rejeitar todos os de nome próprio".
- Realce ao vivo no painel do texto conforme se passa o mouse.
- Contagem viva: "47 candidatos, 31 aceitos, 9 sensíveis 🔴".

---

## 8. Codebook / chave de reidentificação

- Opcional. Gera um arquivo **separado** `codebook.csv` (`rótulo,valor_original`).
- **Nunca** embutido no documento anonimizado.
- Aviso explícito: "este arquivo REIDENTIFICA os dados; guarde em local seguro,
  separado do documento, ou descarte". 
- Útil quando a pesquisa precisa re-vincular depois (estudo longitudinal) — mas é
  o ponto de maior risco, então fica desligado por padrão.

---

## 9. Privacidade e limites (a ferramenta avisa)

- **Não garante anonimato.** Remove identificadores diretos; quase-identificadores
  (data + profissão rara + cidade pequena) ainda podem reidentificar
  (k-anonimato). Mostrar um aviso/checklist.
- **Heurística erra.** Pode deixar passar (falso-negativo) ou marcar demais. Por
  isso a revisão humana é obrigatória no fluxo.
- **Texto livre é traiçoeiro.** Apelidos, jargão interno, eventos únicos
  ("o acidente na fábrica em maio") não são pegos por regex — daí os termos
  livres e a heurística de nomes.
- **Sem desfazer mágico** depois de salvar sem codebook: a anonimização é
  destrutiva por design.

---

## 10. Formatos de documento

| Formato | v0 | Como |
|---|---|---|
| Texto colado | ✅ | direto |
| `.txt` | ✅ | `FileReader.readAsText` |
| `.docx` | 🔜 | docx é um zip de XML; dá pra ler offline com um unzip puro-JS pequeno embutido; extrair `word/document.xml` |
| `.csv` | 🔜 | anonimização por coluna (escolher colunas sensíveis) |
| `.pdf` | 🔜 | extração de texto exige pdf.js (pesado); avaliar; OCR fora de escopo |

Manter o princípio: qualquer lib usada é **embutida** no arquivo (ainda offline).

---

## 11. Roadmap

- **v0 (protótipo, feito):** colar/`.txt`, detectores regex principais com
  validação, gazetteer de estados/capitais/países, heurística de nomes, termos
  livres, revisão KWIC, pseudonimização consistente, copiar/baixar, codebook.
- **v1 (em andamento):**
  - Feito: **NER BERTimbau** (antecipado da v3) via transformers.js, com
    WebGPU e fallback WASM em várias pistas; dois modelos juntos (LGPD +
    HAREM); pacote local com SHA-256; CSP; propagação, união e tipo único por
    valor; selo de origem na revisão; NFC. Detectores novos: CNS validado,
    RG por contexto, registro profissional (OAB, CRM…), nº de prontuário,
    bairros (Jardim/Vila/Parque, "bairro X").
  - Falta: presets por tipo de pesquisa; fusão de entidades ("João" com "João
    da Silva"); atalhos de teclado; mais detectores (PIX, IBAN, CID); aviso de
    quase-identificadores.
- **v2:** `.docx` (in/out preservando formatação básica); `.csv` por coluna;
  perfis salvos (export/import de config como JSON, ainda offline).
- **v3 (avaliar):** modelo Base destilado do legal-bert-lgpd (3× mais rápido
  na CPU); lista de nomes do IBGE como gazetteer; pacote publicado em GitHub
  Releases.

---

## 12. Decisões em aberto (para o pesquisador)

1. **Modo de substituição padrão**: tag de tipo (`[PESSOA_1]`) vs tarja? 
   (recomendo tag de tipo).
2. **Próximo formato**: `.docx` ou `.csv`? Depende do material da pesquisa.
3. **Sensíveis 🔴**: ligar por padrão (mais seguro, mais ruído) ou deixar opt-in?
4. **Codebook**: precisa reidentificar depois (longitudinal) ou é via de mão única?
5. **Municípios**: vale embutir lista grande (arquivo cresce) ou ficar no livre?
6. **Modelos NER padrão**: hoje `legal-bert-lgpd` + HAREM Base. Na CPU só o
   LGPD roda (o HAREM não tem variante quantizada aprovada). Vale incluir o
   HAREM em fp32 (416 MB) para a CPU, ou destilar um modelo Base próprio?
7. **Distribuição do pacote** (~1 GB): cada equipe gera o seu, ou publicamos
   um zip nas Releases do GitHub? (Checar licenças: legal-bert-lgpd e HAREM
   são MIT; os modelos LeNER-Br do pierreguillou não declaram licença.)

---

## 13. Notas de implementação (referência rápida)

- Validação CPF: mod 11 sobre 9 dígitos → 2 dígitos verificadores.
- Validação CNPJ: mod 11 com pesos `5,4,3,2,9,8,7,6,...`.
- Luhn p/ cartão.
- Heurística de nome (regex aproximada):
  `\b[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+)+\b`
  + stoplist (meses, dias da semana, início de frase comum) para reduzir ruído.
- Substituição: coletar spans aceitos → ordenar por início → descartar
  sobrepostos (mantém o primeiro/mais longo) → reconstruir a string.
- Tudo case-/acento-aware onde importa (usar `À-Ý`, `à-ÿ`, ou `\p{L}` com flag `u`).

**NER (medido no legal-bert-lgpd, BERTimbau Large, 24 camadas):**
- Export para ONNX via `torch.onnx.export(..., dynamo=True)`. O exportador
  TorchScript antigo congela a máscara de atenção do transformers 5 e diverge
  do PyTorch (Δp até 0,5). Com dynamo, Δp fica em 1e-5.
- Variantes contra o PyTorch fp32, em 315 textos (corpus embutido + LeNER-Br
  teste): **fp16** 638 MB, F1 de entidades 1,000; **q4** (MatMulNBits
  assimétrico, bloco 32, sem quantizar o classificador) 306 MB, F1 0,977;
  **q8** dinâmico 321 MB, F1 0,90 (reprovado; por canal fica pior).
  A concordância por token passa de 99,6% em todas: não serve de critério.
- Navegador vs. PyTorch (vetores de teste): WebGPU fp16 com F1 0,997 no
  LGPD (370 entidades) e 0,994 no HAREM (439).
- **q8 não serve** para esses modelos: F1 0,90 (LGPD) e 0,47 (HAREM) no x86
  do build, e 0,84/0,76 no WASM do navegador (testado para descartar a
  hipótese de saturação do AVX2 sem VNNI). O HAREM também reprova no q4
  (0,88), então só roda na GPU (fp16).
- **Sensibilidade ao alinhamento das janelas:** mesmo em fp16, deslocar as
  janelas (pôr "Nota.\n" antes do texto) muda de 5 a 11% das entidades
  limítrofes em relação à referência. Por isso os trechos das pistas de CPU
  (que alinham as janelas de outro jeito) ficam em F1 ~0,91 contra a
  referência, dentro dessa variação, e não por perda de contexto (uma
  margem de 1.000 caracteres entre trechos não mudou nada). Ideia para depois:
  rodar duas passadas deslocadas e unir, para ganhar recall.
- Velocidade (RTX 3060 / Ryzen 5 5500): WebGPU fp16 ~80 ms por janela de 512
  tokens (lote de 4); WASM q4 ~12 s por janela por pista; 4 pistas processam
  3.540 tokens em ~40 s (1 pista: ~109 s).
- **Vazamento** (tests/golden, 54 dados pessoais, só o aceito por padrão):
  sem modelo 32 sobram; LGPD 1; LGPD + HAREM 0, sem excesso. Os documentos
  foram escritos junto com os ajustes: é regressão, não benchmark.
- Rótulos do modelo → tipos do AnonLab: `LABEL_MAP` no script de build
  (vai para `label_map` no pacote) e `NER_LABEL_MAP` no HTML (fallback).
