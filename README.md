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

Com um modelo BERTimbau, a detecção passa a entender o contexto. Ele acha nomes
no começo de frase ou em minúsculas, endereços ("Rua das Flores, nº 120",
"Jardim Esmeralda"), datas por extenso e outros dados que as regras não pegam.
Tudo o que o modelo acha num lugar é procurado também no resto do texto, para
nenhuma ocorrência escapar.

**O modelo vem até o navegador; o texto não vai a lugar nenhum.** No cartão
"Modelo de linguagem", clique em **🌐 Baixar modelos**. O navegador baixa os
modelos do Hugging Face uma vez (~850 MB na GPU, ~310 MB na CPU) e guarda para
as próximas visitas. A opção "carregar sozinho ao abrir" já vem marcada. O
modelo roda **no próprio computador**, pelo
[transformers.js](https://github.com/huggingface/transformers.js) com
onnxruntime-web: na **GPU via WebGPU** ou, se não houver, na **CPU via
WebAssembly**.

Por padrão rodam dois modelos juntos na GPU:

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

### De onde vêm os modelos

Os modelos originais do Hugging Face estão em PyTorch. O navegador precisa deles
em ONNX, então o projeto os converte e publica:

```bash
uv run tools/build_ner_pack.py                           # converte e valida → dist/anonlab-ner/ (~1,2 GB)
hf auth login                                            # uma vez, token com escrita
uv run tools/publish_hub.py --user SEU_USUARIO_HF        # publica <usuário>/<modelo>-onnx
```

O `publish_hub.py` cria um repositório por modelo, com um model card que
credita o original, e fixa no `anonimizador.html` (`NER_HUB`) o commit
publicado. Assim o navegador baixa sempre exatamente aqueles arquivos. Ele se
recusa a publicar derivados de modelos sem licença declarada.

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
```

`tests/vectors/*.json` é gerado pelo build (`--vectors tests/vectors`) com o
tokenizador e o modelo originais.

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
