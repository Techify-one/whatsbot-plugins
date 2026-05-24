# WhatsBot Plugins

Repositório oficial de plugins do **WhatsBot** — extensões que adicionam novas funcionalidades ao bot.

Os plugins listados aqui ficam disponíveis para download em:

**https://whatsbot.techify.one/plugins**

A página lê automaticamente este repositório via GitHub API. Basta seguir a estrutura abaixo que o plugin aparece lá sem precisar editar nada na página.

## Como adicionar um plugin novo

Cada plugin vive em uma subpasta dentro de [`plugins/`](plugins/). A subpasta precisa ter, no mínimo:

```
plugins/
└── meu-plugin/
    ├── plugin.json        # metadados (obrigatório)
    └── meu-plugin.zip     # arquivo de download (apontado por plugin.json)
```

### `plugin.json`

```json
{
  "name": "Nome amigável do plugin",
  "description": "Descrição curta (uma linha) do que o plugin faz.",
  "version": "1.0.0",
  "icon": "🔌",
  "file": "meu-plugin.zip"
}
```

Campos:

| Campo         | Obrigatório | Descrição                                                                 |
|---------------|-------------|---------------------------------------------------------------------------|
| `name`        | sim         | Nome exibido no card.                                                     |
| `description` | sim         | Frase curta explicando o que o plugin faz.                                |
| `version`     | sim         | Versão semântica (ex.: `1.0.0`).                                          |
| `icon`        | não         | Emoji exibido no card (default: `🔌`).                                    |
| `file`        | sim         | Nome do arquivo de download dentro da pasta do plugin (`.zip` recomendado). |
| `author`      | não         | Nome do autor/responsável pelo plugin.                                    |
| `homepage`    | não         | URL com mais informações (documentação, vídeo, etc).                      |

### Botão de download

O botão de download na página aponta para o arquivo `plugins/<id>/<file>` do branch `main` deste repositório (via `raw.githubusercontent.com`).

## Cache

A página em produção cacheia a listagem por 5 minutos no edge da Cloudflare. Plugins novos aparecem em até 5 minutos depois do push para `main`.
