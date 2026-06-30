# Diagramas prontos para o Excalidraw (.mmd puros)

Cada arquivo `.mmd` aqui contém **apenas o código Mermaid** — sem cercas ` ``` ` e
sem texto markdown em volta. São a fonte certa para importar no Excalidraw sem erro.

## ⭐ Quer TUDO de uma vez? (um Ctrl+C / Ctrl+V)

Use **[`TUTORIAL-COMPLETO-1-BLOCO.mmd`](TUTORIAL-COMPLETO-1-BLOCO.mmd)** — é o
tutorial **inteiro num único diagrama** (todos os 7 capítulos). Abra o arquivo →
`Ctrl+A` → `Ctrl+C` → cole em **"Mermaid to Excalidraw"** → **Insert**. Vem tudo
de uma vez só, em um quadro grande (leia de cima para baixo seguindo as setas
tracejadas "próximo").

> Os arquivos numerados `00`–`09` abaixo são a versão **um capítulo por arquivo**,
> caso você prefira importar e posicionar cada quadro separadamente.

## Por que estes arquivos existem

A caixa **"Mermaid to Excalidraw"** aceita só o código Mermaid puro. Se você
copiar de um arquivo `.md`, é fácil pegar junto a cerca ` ``` ` de fechamento e o
próximo título `## Capítulo ...` — e aí dá:

```
Parse error on line X: ...commC;```---## Capítulo 2
```

Esses `.mmd` não têm esse lixo, então é só **abrir → Ctrl+A → Ctrl+C → colar**.

## Como importar

1. Abra o arquivo `.mmd` (ex.: `01-capitulo-1-ecossistema-e-repositorios.mmd`).
2. Selecione tudo (`Ctrl+A`) e copie (`Ctrl+C`).
3. No Excalidraw → menu (☰) ou `Mais ferramentas` → **"Mermaid to Excalidraw"**.
4. Cole na caixa da esquerda → **Insert**.
5. Repita para o próximo arquivo. Arraste os quadros lado a lado para montar o
   tutorial inteiro numa só tela.

> Importe **um arquivo por vez**. A caixa converte um diagrama por importação.

## Ordem dos capítulos

| Arquivo | Capítulo |
|---------|----------|
| `00-...` | Mapa do tutorial (índice visual) |
| `01-...` | Ecossistema e repositórios |
| `02-...` | Anatomia de um plugin |
| `03-...` | Ciclo de carregamento no boot |
| `04-...` | Eventos vs Filters |
| `05-...` | Catálogo de nomes (eventos e filters) |
| `06-...` | Contexto e serviços que o plugin recebe |
| `07-...` | Fluxo 6a — Filter Auto Signature (sequência) |
| `08-...` | Fluxo 6b — Evento Boas-vindas (sequência) |
| `09-...` | Passo a passo para criar um plugin |

O tutorial em prosa está em [../ARQUITETURA-PLUGINS.md](../ARQUITETURA-PLUGINS.md);
a versão com os painéis montados (texto + diagrama juntos) está em
[../TUTORIAL-EXCALIDRAW.md](../TUTORIAL-EXCALIDRAW.md).
</content>
