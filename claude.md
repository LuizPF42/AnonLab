# Anonimizador de Documentos (airgapped)

Ferramenta **local, offline e sem instalador** para ajudar pesquisadores a
de-identificar documentos (entrevistas, prontuários, autos, transcrições, etc.)
antes de compartilhar ou analisar. Pensada para o contexto brasileiro (LGPD,
CPF/CNPJ/CNS, etc.).

> Status: **especificação + protótipo v0** (`anonimizador.html`).
> Este arquivo é a fonte da verdade do design. O protótipo implementa um
> subconjunto e está marcado como v0.

---

## 1. Princípios (não-negociáveis)

1. **Airgapped de verdade.** Zero requisições de rede. Nada de CDN, fontes
   externas, analytics, telemetria. Tudo embutido em um único arquivo. O dado
   do pesquisador **nunca sai da máquina**.
2. **Sem instalador.** Um único `anonimizador.html`. Abre com duplo clique em
   qualquer navegador moderno (funciona via `file://`). Nada de Python, Node,
   build, servidor.
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

A força da ferramenta é combinar quatro camadas, da mais precisa à mais
heurística. As três últimas alimentam **sugestões revisáveis**.

| Camada | O que é | Precisão | Tratamento |
|---|---|---|---|
| **1. Padrões estruturados (regex)** | CPF, CNPJ, e-mail, telefone, CEP, datas, processo CNJ, cartão, IP… | Alta (alguns com validação de dígito) | Pode auto-aplicar ou sugerir já marcado |
| **2. Listas / gazetteer (as "caixinhas")** | 27 estados+UF, capitais, países, pronomes de tratamento, sufixos de empresa | Média-alta | Sugere quando a caixinha está ligada |
| **3. Heurística de nomes próprios (NER leve)** | sequências capitalizadas (com conectores "da/de/do") fora de início de frase | Média (gera falso-positivo de propósito) | Sempre sugestão revisável no contexto |
| **4. Termos livres do pesquisador** | lista custom (nomes, apelidos, codinomes, locais específicos) | Definida pelo usuário | Match exato/palavra inteira, com opção case-insensitive |

Notas de implementação:
- **Validação de dígito** em CPF/CNPJ (mod 11) e cartão (Luhn) corta muito
  falso-positivo. Vale a pena.
- **Resolução de sobreposição:** ao detectar, vários padrões podem casar o mesmo
  trecho. Precedência: estruturado validado > estruturado > gazetteer >
  heurística; em empate, **o casamento mais longo** vence.
- **Substituir do mais longo pro mais curto** evita quebrar entidades aninhadas
  ("Dr. João Silva" antes de "Silva").

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
- **v1:** presets por tipo de pesquisa; acordeões de categorias; fusão de
  entidades; atalhos de teclado; mais detectores (PIX, IBAN, CID, registros
  profissionais); aviso de quase-identificadores.
- **v2:** `.docx` (in/out preservando formatação básica); `.csv` por coluna;
  perfis salvos (export/import de config como JSON, ainda offline).
- **v3 (avaliar):** NER de verdade via modelo pequeno em WASM/ONNX embutido
  (custa tamanho do arquivo e complexidade — só se a heurística não bastar).

---

## 12. Decisões em aberto (para o pesquisador)

1. **Modo de substituição padrão**: tag de tipo (`[PESSOA_1]`) vs tarja? 
   (recomendo tag de tipo).
2. **Próximo formato**: `.docx` ou `.csv`? Depende do material da pesquisa.
3. **Sensíveis 🔴**: ligar por padrão (mais seguro, mais ruído) ou deixar opt-in?
4. **Codebook**: precisa reidentificar depois (longitudinal) ou é via de mão única?
5. **Municípios**: vale embutir lista grande (arquivo cresce) ou ficar no livre?

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
