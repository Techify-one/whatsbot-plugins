# Arquitetura de Plugins do WhatsBot

Documentação didática de como funciona o sistema de plugins do WhatsBot —
o que é cada repositório, como um plugin é carregado, quais "ganchos" (hooks)
ele pode usar e o passo a passo para criar um.

> Os diagramas estão em blocos ` ```mermaid `. Para visualizar/editar no
> Excalidraw: abra https://excalidraw.com → menu (hambúrguer) → **"Mermaid to
> Excalidraw"** → cole o bloco → **Insert**.

---

## 1. Os 4 repositórios e onde o plugin "vive"

O ecossistema tem 4 repos com papéis distintos. **Este repositório
(`whatsbot-plugins`) é só a "loja": fonte de dados.** Ele NÃO executa plugin —
ele guarda o `plugin.json` (metadados do card) + o `.zip` (o código real).

```mermaid
flowchart LR
  subgraph Dev["Desenvolvimento"]
    autor["Autor do plugin"]
  end

  subgraph Loja["whatsbot-plugins (ESTE repo)"]
    pjson["plugin.json (card)"]
    zip["meu-plugin.zip (codigo)"]
  end

  subgraph Pagina["whatsbot-pages (Cloudflare Worker)"]
    page["whatsbot.techify.one/plugins"]
  end

  subgraph Apps["Apps backend (instalam e RODAM o plugin)"]
    pro["whatsbot-pro (versao Pro)"]
    comm["whatsbot (Community)"]
  end

  autor -->|"push pra main"| Loja
  Loja -->|"GitHub API / raw"| page
  page -->|"usuario baixa o .zip"| autor
  zip -->|"upload / instalacao"| pro
  zip -->|"upload / instalacao"| comm

  classDef devC fill:#fff3bf,stroke:#f08c00,stroke-width:2px,color:#5f3a00;
  classDef lojaC fill:#ffe066,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef pageC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  classDef commC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  class autor devC;
  class pjson,zip lojaC;
  class page pageC;
  class pro proC;
  class comm commC;
```

Resumo dos papéis:

| Repo | Papel |
|------|-------|
| **whatsbot-plugins** (este) | Fonte de dados: `plugin.json` + `.zip`. Não roda nada. |
| **whatsbot-pages** | Página de produção (`/plugins`), Cloudflare Worker. Lê este repo via GitHub API e serve o card + botão de download. Cache de 5 min no edge. |
| **whatsbot-pro** | App backend "Pro" (Python/FastAPI). Tem o **motor de plugins completo**: RBAC, lifecycle (`setup`/`teardown`), auditoria, supervisor de tasks/subprocessos. |
| **whatsbot** | App backend "Community", mais enxuto. Mesmo motor de plugins, **sem** RBAC, lifecycle e audit. |

### Esse repositório serve pro Pro e pro Community?

**Sim.** Um mesmo `.zip` pode ser instalado nos dois apps, porque ambos
expõem a **mesma API de plugin** (`plugins.context`, `db.repositories`, bus de
eventos/filters, migrations). A compatibilidade é controlada pelo campo
`whatsbot_api_version` do manifesto (semver).

A diferença é só de **capacidades extras** que existem só no Pro:

| Recurso do manifesto | Pro | Community |
|----------------------|-----|-----------|
| tools, prompts, events, filters, routes, settings, screens, migrations | ✅ | ✅ |
| `rbac:` (permissões de usuário) | ✅ | ignorado |
| `lifecycle` (`setup`/`teardown`, tasks, subprocessos) | ✅ | ausente |
| auditoria | ✅ | ausente |

Um plugin que só usa o núcleo comum roda nos dois. Um plugin que depende de
`lifecycle`/`rbac` só funciona pleno no Pro (no Community os campos extras são
ignorados, sem quebrar o boot).

---

## 2. Anatomia de um plugin (estrutura de pastas)

Cada plugin é uma pasta cujo **nome == `id` do manifesto**. Dentro do `.zip`,
a estrutura típica:

```
meu_plugin/
├── plugin.yaml          # MANIFESTO (obrigatório) — id, versão, entry, screens...
├── __init__.py          # marca a pasta como pacote Python (pode ser vazio)
├── events.py            # EVENT_HANDLERS = {"group.joined": fn}   (assina eventos)
├── filters.py           # FILTERS = {"filter.reply.part": fn}     (intercepta valores)
├── routes.py            # router = APIRouter()                    (endpoints REST)
├── settings.py          # class Settings(BaseModel)               (form automático)
├── tools.py             # CORE_TOOLS = [(schema, executor)]       (ferramentas de IA)
├── migrations/
│   └── 001_initial.sql  # tabelas plugin_<id>_*  (rodadas em ordem)
└── static/
    └── meu_plugin.js     # tela (screen) Preact renderizada no painel
```

> ⚠️ Há **dois** arquivos de metadados, não confunda:
> - **`plugin.json`** (na raiz da pasta no repo `whatsbot-plugins`) → é só o
>   **card da loja** (nome, descrição, ícone, qual `.zip` baixar).
> - **`plugin.yaml`** (dentro do `.zip`) → é o **manifesto real** que o app lê
>   ao instalar: `id`, `entry`, `screens`, `migrations`, `permissions`, etc.

### Como o manifesto liga arquivos a capacidades

O bloco `entry:` mapeia cada capacidade ao módulo (`.py`) que a implementa.
O loader importa só o que estiver declarado.

```mermaid
flowchart LR
  yaml["plugin.yaml (entry:)"]

  yaml -->|events| ev["events.py -> EVENT_HANDLERS"]
  yaml -->|filters| fi["filters.py -> FILTERS"]
  yaml -->|routes| ro["routes.py -> router (APIRouter)"]
  yaml -->|settings| se["settings.py -> Settings (Pydantic)"]
  yaml -->|tools| to["tools.py -> CORE_TOOLS"]
  yaml -->|prompts| pr["prompts.py -> PROMPT_FRAGMENTS"]
  yaml -->|lifecycle| li["lifecycle.py -> setup() / teardown() (so Pro)"]

  yaml -.->|"migrations"| mg["migrations/*.sql"]
  yaml -.->|"screens"| sc["static/*.js (tela Preact)"]

  classDef manC fill:#ffe066,stroke:#f59f00,stroke-width:3px,color:#5f3a00;
  classDef evC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef fiC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef apiC fill:#96f2d7,stroke:#0ca678,stroke-width:2px,color:#0a4a3a;
  classDef cfgC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef aiC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  classDef dataC fill:#dee2e6,stroke:#868e96,stroke-width:2px,color:#343a40;
  class yaml manC;
  class ev evC;
  class fi fiC;
  class ro apiC;
  class se cfgC;
  class to,pr aiC;
  class li proC;
  class mg,sc dataC;
```

### Exemplo de `plugin.yaml`

```yaml
id: boas_vindas                       # snake_case, == nome da pasta
name: Boas-vindas em Grupos
version: 1.0.1                         # semver obrigatório
whatsbot_api_version: ">=1.0,<2.0"     # faixa de compatibilidade
description: >-
  Marca com @ quem entra num grupo ativado, pedindo que se apresente.
author: WhatsBot
entry:
  events: events                      # importa events.py
  routes: routes                      # importa routes.py
migrations: migrations                # pasta com os .sql
screens:
  - id: boas-vindas-config
    title: Boas-vindas em Grupos
    path: /boas-vindas
    icon: user-plus
    component: /plugins/boas_vindas/static/boas_vindas.js
    config: true                      # vira a tela do modal "Configurar"
permissions: []
dependencies: []                      # pacotes pip (instalados no 1o load)
```

---

## 3. Ciclo de carregamento (o que acontece no boot)

No startup do app, `discover_and_load(storages/plugins)` varre as pastas e,
para cada plugin **habilitado**, executa esta sequência. Plugin com erro é
isolado: registra `load_error` e o app continua subindo.

```mermaid
flowchart TD
  start([Boot do servidor]) --> recover["Recupera updates interrompidos (swap de pasta)"]
  recover --> scan["Varre storages/plugins/*"]
  scan --> man{"plugin.yaml valido?"}
  man -->|nao| err1["Registra load_error, pula"]
  man -->|sim| upsert["Upsert no banco (id, versao)"]
  upsert --> en{"Plugin habilitado?"}
  en -->|nao| skip["Pula carga (so fica descoberto)"]
  en -->|sim| deps["Instala dependencies pip (so na 1a vez)"]
  deps --> imp["Importa modulos do entry (tools, events, filters, routes...)"]
  imp --> mig["Roda migrations pendentes (001, 002...)"]
  mig --> rbac["Sincroniza permissoes RBAC (so Pro)"]
  rbac --> reg["Registra no PluginRegistry + monta rotas/telas"]
  reg --> setup["lifecycle.setup(ctx) (so Pro, se houver)"]
  setup --> done([Plugin ativo])
  err1 --> done
  skip --> done

  classDef startC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef decC fill:#ffec99,stroke:#f08c00,stroke-width:3px,color:#5f3a00;
  classDef procC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef errC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef skipC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef okC fill:#b2f2bb,stroke:#2f9e44,stroke-width:3px,color:#13491f;
  class start startC;
  class man,en decC;
  class recover,scan,upsert,deps,imp,mig,rbac,reg,setup procC;
  class err1 errC;
  class skip skipC;
  class done okC;
```

Pontos importantes:

- **Habilitar/desabilitar** é um flag no banco — não apaga a pasta. Plugin
  desabilitado é "descoberto" mas não carregado (não assina nada, não cria rota).
- **Migrations** rodam em ordem (`001_`, `002_`, ...) e são idempotentes
  (`CREATE TABLE IF NOT EXISTS`). Toda tabela do plugin **deve** começar com o
  prefixo `plugin_<id>_` — é a convenção de isolamento (não há banco separado
  por plugin; todos compartilham o mesmo engine SQLAlchemy).
- **Atualização sem perder dados**: o swap de pasta é feito em 2 renames com
  recuperação automática se a máquina cair no meio.

---

## 4. Os ganchos: Eventos vs Filters (o coração da extensibilidade)

Existem **dois mecanismos** para um plugin reagir ao core sem tocar no código
dele. Entender a diferença é o ponto-chave da arquitetura:

```mermaid
flowchart TB
  subgraph EV["EVENTOS (broadcast, fire-and-forget)"]
    direction LR
    core1["Core: emit('group.joined', payload)"] --> bus["Event bus"]
    bus -->|task isolada| h1["Plugin A handler"]
    bus -->|task isolada| h2["Plugin B handler"]
    note1["O plugin OBSERVA e reage. Nao bloqueia, nao altera o fluxo. Erro num handler nao afeta o core."]
  end

  subgraph FI["FILTERS (interceptivo, em cadeia)"]
    direction LR
    core2["Core: apply_filter('filter.reply.part', texto)"] --> f1["Filter prio 50"]
    f1 -->|valor modificado| f2["Filter prio 100"]
    f2 -->|valor final| volta["Core usa o resultado"]
    note2["O plugin MODIFICA o valor em transito. Retornar None ABORTA a acao."]
  end

  classDef coreC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef evC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef fiC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef noteC fill:#fff9db,stroke:#f59f00,stroke-width:1px,color:#5f3a00;
  classDef okC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  class core1,core2 coreC;
  class bus,h1,h2 evC;
  class f1,f2 fiC;
  class volta okC;
  class note1,note2 noteC;
  style EV fill:#e7f5ff,stroke:#1971c2,stroke-width:2px;
  style FI fill:#f3f0ff,stroke:#7048e8,stroke-width:2px;
```

| | **Eventos** | **Filters** |
|---|---|---|
| Intenção | "aconteceu X" (notificação) | "estou prestes a usar Y, quer mudar?" |
| Exporta | `EVENT_HANDLERS = {nome: fn}` | `FILTERS = {nome: fn}` ou `{nome: (fn, prioridade)}` |
| Assinatura | `fn(ctx, payload)` | `fn(ctx, value) -> value | None` |
| Pode alterar o fluxo? | Não (observador) | Sim (transforma o valor; `None` aborta) |
| Ordem | registro | por prioridade (menor roda antes) |
| Falha do plugin | isolada, ignorada | isolada; valor passa adiante sem alteração |

### Catálogo (principais nomes válidos)

**Eventos** (`KNOWN_EVENTS`) — alguns dos mais usados:
`message.received`, `message.sent`, `message.persisted`, `message.reaction`,
`group.participants_changed`, `group.joined`, `call.received`,
`connection.changed`, `conversation.created`, `conversation.status_changed`,
`contact.tagged`, `tag.created`, `llm.before`/`llm.after`,
`tool.before`/`tool.after`, `app.startup`/`app.shutdown`.
Especiais: `*` (curinga, recebe tudo) e `message.any` (recebe `received`+`sent`
com `direction`).

**Filters** (`KNOWN_FILTERS`) — alguns dos mais usados:
`filter.webhook.payload`, `filter.message.before_save`,
`filter.transcription.should_run`/`result`, `filter.contact.tags`,
`filter.system_prompt`, `filter.llm.messages`, `filter.llm.tools`,
`filter.tool.args`/`result`,
`filter.reply.raw`/`filter.reply.parts`/`filter.reply.part`,
`filter.event.before_emit`.

> Um nome fora do catálogo não é erro — só gera um WARNING (provável typo).
> Plugins podem inclusive publicar filters próprios para outros plugins consumirem.

---

## 5. O que o plugin recebe (contexto e serviços)

Todo handler recebe um objeto de contexto (`EventContext`, `FilterContext`,
`PluginContext`, `ToolContext`...). Os principais recursos disponíveis:

```mermaid
flowchart LR
  plugin["Codigo do plugin"]

  plugin -->|"ctx.plugin_db() / make_plugin_db()"| db["Tabelas plugin_id_* (engine compartilhado)"]
  plugin -->|"broadcast(evento, dados)"| ws["WebSocket -> painel ao vivo"]
  plugin -->|"config_repo.get / set"| cfg["Settings persistidas (plugin.id.*)"]
  plugin -->|"ctx.handler"| ag["AgentHandler (IA, mencoes, envio...)"]
  plugin -->|"agent.group_mentions._client"| gowa["Cliente GOWA (enviar WhatsApp)"]
  plugin -->|"ctx.on_unload(fn) - so Pro"| life["Cleanup no teardown"]
  plugin -->|"ctx.spawn_task / spawn_subprocess - so Pro"| sup["Tasks / subprocessos supervisionados"]

  classDef plugC fill:#ffe066,stroke:#f59f00,stroke-width:3px,color:#5f3a00;
  classDef dbC fill:#dee2e6,stroke:#868e96,stroke-width:2px,color:#343a40;
  classDef wsC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef cfgC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef agC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef gowaC fill:#96f2d7,stroke:#0ca678,stroke-width:2px,color:#0a4a3a;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  class plugin plugC;
  class db dbC;
  class ws wsC;
  class cfg cfgC;
  class ag agC;
  class gowa gowaC;
  class life,sup proC;
```

- **Banco**: `with ctx.plugin_db() as conn: conn.execute(text("..."))`. Use
  sempre o prefixo `plugin_<id>_` nas tabelas.
- **Tempo real**: `broadcast("new_message", {...})` empurra pro painel sem reload.
- **Settings**: declare uma `class Settings(BaseModel)` → o painel gera o
  formulário automático em `/plugins`; os valores ficam em `config` com prefixo
  `plugin.<id>.`.
- **REST do plugin**: tudo em `routes.py` fica sob `/api/plugins/<id>/...`,
  já protegido pela senha do painel (e por RBAC, no Pro, via `plugin_permission`).

---

## 6. Exemplos de fluxo real

### 6a. Filter interceptivo — Auto Signature

Adiciona uma assinatura no fim de cada parte de resposta enviada.

```mermaid
sequenceDiagram
  autonumber
  box rgb(255,216,168) Core
  participant Core as Core (envio de resposta)
  participant Bus as apply_filter
  end
  box rgb(208,191,255) Plugin
  participant P as Plugin auto_signature
  end
  Core->>Bus: apply_filter('filter.reply.part', texto, {source})
  Bus->>P: add_signature(ctx, texto)
  P->>P: le Settings (assinatura) e ctx.extras['source']
  P-->>Bus: texto + "\n\n*Mensagem enviada por IA*"
  Bus-->>Core: texto assinado (usado no envio)
```

### 6b. Evento — Boas-vindas em grupos

Reage a alguém entrando num grupo ativado, sem tocar no core.

```mermaid
sequenceDiagram
  autonumber
  box rgb(150,242,215) WhatsApp
  participant GOWA as Webhook (WhatsApp)
  end
  box rgb(255,216,168) Core
  participant Core as Core
  participant Bus as Event bus (emit)
  end
  box rgb(165,216,255) Plugin
  participant P as Plugin boas_vindas
  end
  box rgb(222,226,230) Infra
  participant DB as plugin_boas_vindas_*
  participant WA as Cliente GOWA
  end

  GOWA->>Core: alguem entrou no grupo
  Core->>Bus: emit('group.participants_changed', payload)
  Bus->>P: on_participants_changed(ctx, payload)
  P->>DB: grupo esta habilitado?
  DB-->>P: sim
  P->>P: thread: espera delay configurado
  P->>WA: send_message(grupo, "Ola @fulano, se apresente", mentions)
  P->>Core: save_operator_message + broadcast('new_message')
  Note over P,Core: mensagem aparece no painel ao vivo
```

---

## 7. Passo a passo: criar um plugin novo

1. **Crie a pasta** `meu_plugin/` (nome em `snake_case` = `id`).
2. **Escreva o `plugin.yaml`** (manifesto): `id`, `name`, `version`,
   `whatsbot_api_version`, e o bloco `entry:` apontando os módulos que você vai
   usar.
3. **Implemente as capacidades** que precisar:
   - reagir a algo → `events.py` com `EVENT_HANDLERS`;
   - modificar algo em trânsito → `filters.py` com `FILTERS`;
   - guardar estado → `migrations/001_initial.sql` (tabelas `plugin_meu_plugin_*`);
   - config pelo painel → `settings.py` (`Settings`) e/ou `routes.py` + `static/*.js`.
4. **Teste local** instalando no app (Pro e/ou Community).
5. **Empacote** o conteúdo da pasta num `.zip`.
6. **Publique na loja**: crie `plugins/meu-plugin/` neste repo com o `.zip` + um
   `plugin.json` (card) apontando o arquivo, e dê `push` na `main`. Em até 5 min
   aparece em `whatsbot.techify.one/plugins`.

> Regra de ouro do isolamento: **não toque no core**. Use eventos para observar,
> filters para modificar, tabelas com prefixo `plugin_<id>_` para o estado, e
> `broadcast` para a UI ao vivo. Assim o mesmo plugin roda no Pro e no Community.
