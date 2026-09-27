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
`[ENDERECO_2]`…). Quem decide o que sai é o pesquisador.

**Testar online:** <https://luizpf42.github.io/AnonLab/anonimizador.html>
(GitHub Pages). Também dá para baixar o `anonimizador.html` e abrir com duplo
clique. As duas formas fazem a mesma coisa, mas a cópia local permite auditar e
fixar exatamente o código que roda.

## Uso rápido

1. Abra o `anonimizador.html` (Chrome ou Edge recomendados; Firefox e Safari também funcionam).
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

> Hoje o modelo vem de uma **pasta local** (o "pacote NER"). O próximo passo é
> baixar os modelos direto do Hugging Face, no próprio navegador, sem precisar
> montar o pacote. O texto continua sem sair da máquina. A pasta local seguirá
> disponível para quem precisar trabalhar sem internet.

O pacote é gerado **uma vez**, numa máquina com internet, e pode ser copiado
(pendrive, rede interna…) para outras máquinas:

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

### Privacidade: o texto não sai do navegador

- Todo o processamento (regras, listas e modelo) acontece **na sua máquina**.
  Nenhum servidor recebe o documento.
- A página tem uma **Content-Security-Policy** que restringe as conexões. Na
  versão atual, com o pacote local, ela bloqueia *qualquer* acesso à rede
  (`connect-src blob: data:`), inclusive no worker do modelo.
- O transformers.js recebe um `fetch` próprio, que só entrega arquivos do
  pacote. Qualquer outro endereço recebe 404 sem sair da máquina.
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

## Créditos

O AnonLab junta trabalho de muita gente. Os modelos, bibliotecas e dados
abaixo pertencem aos seus autores e seguem as próprias licenças.

**Modelos de linguagem (Hugging Face)**

| modelo | autoria | licença | papel no AnonLab |
|---|---|---|---|
| [celiudos/legal-bert-lgpd](https://huggingface.co/celiudos/legal-bert-lgpd) | Marcelo Anselmo de Souza Filho. Dissertação *Inteligência Artificial no MPF: Uma Solução Baseada em IA para Pseudonimização de Dados Pessoais* (UnB, 2025) | MIT | modelo principal (dados pessoais da LGPD) |
| [liaad/NER_harem_bert-base-portuguese-cased](https://huggingface.co/liaad/NER_harem_bert-base-portuguese-cased) | [LIAAD, INESC TEC](https://huggingface.co/liaad) | MIT | segundo modelo (organizações e locais) |
| [pierreguillou/ner-bert-large-cased-pt-lenerbr](https://huggingface.co/pierreguillou/ner-bert-large-cased-pt-lenerbr) | Pierre Guillou | não declarada | base do legal-bert-lgpd; preset `lenerbr` |
| [neuralmind/bert-base-portuguese-cased](https://huggingface.co/neuralmind/bert-base-portuguese-cased) e [neuralmind/bert-large-portuguese-cased](https://huggingface.co/neuralmind/bert-large-portuguese-cased) (BERTimbau) | Fábio Souza, Rodrigo Nogueira e Roberto Lotufo, NeuralMind ([portuguese-bert](https://github.com/neuralmind-ai/portuguese-bert)) | MIT | base de todos os modelos acima |
| [rufimelo/Legal-BERTimbau-base](https://huggingface.co/rufimelo/Legal-BERTimbau-base) | Rui Melo | MIT | referência (ainda não usado: é um modelo de base, sem a parte de NER) |

**Software**

- [transformers.js](https://github.com/huggingface/transformers.js) (Hugging Face, Apache-2.0): carrega e roda os modelos no navegador.
- [ONNX Runtime Web](https://github.com/microsoft/onnxruntime) (Microsoft, MIT): execução em WebGPU e WebAssembly.
- Na conversão dos modelos (`tools/build_ner_pack.py`): [PyTorch](https://github.com/pytorch/pytorch), [🤗 Transformers](https://github.com/huggingface/transformers), [ONNX](https://github.com/onnx/onnx), [onnxconverter-common](https://github.com/microsoft/onnxconverter-common) e [huggingface_hub](https://github.com/huggingface/huggingface_hub).

**Dados e referências**

- [LeNER-Br](https://github.com/peluz/lener-br) (Luz de Araujo et al., PROPOR 2018): frases de teste usadas para validar as versões quantizadas dos modelos. Só no build; não são redistribuídas.
- [HAREM](https://www.linguateca.pt/HAREM/) (Linguateca): corpus em que o modelo do LIAAD foi treinado.
- [anonimizador-dp](https://github.com/anatelgovbr/anonimizador-dp) (Anatel, GPL-3.0): referência de detectores com validação (CNS, RG etc.). Nenhum código foi copiado.
- Raquel Alexandra Moleira Domingos, *Aperfeiçoamento de Tecnologias de Anonimização para o Contexto de Dados Não Estruturados* (dissertação de mestrado, Faculdade de Ciências da Universidade de Lisboa, 2025). Comparação de modelos de NER para anonimização em português; inspirou o uso de modelos por domínio.
