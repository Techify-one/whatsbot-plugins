# Tutorial de Plugins do WhatsBot — versão Excalidraw

Esta é a versão **pensada para o Excalidraw**: cada capítulo abaixo é um painel
Mermaid único que já inclui o **título, a explicação em cartões e o diagrama**.
Ao importar, você não recebe só o desenho — recebe o tutorial completo como
formas editáveis, pronto para virar um quadro didático.

> ⚠️ **Forma mais fácil (sem erro):** use os arquivos `.mmd` **puros** em
> [diagramas-excalidraw/](diagramas-excalidraw/) — um por capítulo. Abra o
> arquivo → `Ctrl+A` → `Ctrl+C` → cole em **"Mermaid to Excalidraw"**.
>
> **Se for copiar daqui deste `.md`:** copie SÓ as linhas de dentro do bloco —
> **NÃO** inclua a cerca ` ``` ` nem o título `## Capítulo ...` que vem depois.
> Pegar esse texto a mais causa o erro
> `Parse error ... commC;```---## Capítulo 2`. Por isso os `.mmd` são mais seguros.
>
> **Como importar cada painel:** no Excalidraw → menu (hambúrguer) ou
> `Mais ferramentas` → **"Mermaid to Excalidraw"** → cole UM diagrama por vez →
> **Insert**. Cada capítulo vira um quadro; arraste-os lado a lado.
>
> Conteúdo idêntico em prosa tradicional está em
> [ARQUITETURA-PLUGINS.md](ARQUITETURA-PLUGINS.md).

---

## Capítulo 0 — Mapa do tutorial (índice visual)

```mermaid
flowchart TB
  cap0["`**Plugins do WhatsBot**
  Tutorial completo
  Importe os capitulos 1 a 7`"]

  cap0 --> c1["`**1.** Ecossistema
  e repositorios`"]
  cap0 --> c2["`**2.** Anatomia
  de um plugin`"]
  cap0 --> c3["`**3.** Ciclo de
  carregamento no boot`"]
  cap0 --> c4["`**4.** Eventos
  vs Filters`"]
  cap0 --> c5["`**5.** O que o plugin
  recebe - contexto`"]
  cap0 --> c6["`**6.** Fluxos reais
  - exemplos`"]
  cap0 --> c7["`**7.** Passo a passo
  para criar`"]

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef itemC fill:#fff3bf,stroke:#f08c00,stroke-width:2px,color:#5f3a00;
  class cap0 titleC;
  class c1,c2,c3,c4,c5,c6,c7 itemC;
```

---

## Capítulo 1 — Ecossistema e repositórios

```mermaid
flowchart TB
  titulo["`**Cap. 1 - Ecossistema e repositorios**
  Este repo e so a LOJA - fonte de dados.
  Quem RODA o plugin sao os apps backend.`"]

  subgraph Explicacao["O que e cada repo"]
    e1["`**whatsbot-plugins** - ESTE repo
    Guarda plugin.json - card - e .zip - codigo.
    Nao executa nada.`"]
    e2["`**whatsbot-pages**
    Vitrine em whatsbot.techify.one/plugins.
    Le este repo via GitHub API. Cache 5 min.`"]
    e3["`**whatsbot-pro**
    App backend Pro. Motor completo:
    RBAC, lifecycle, auditoria.`"]
    e4["`**whatsbot** - Community
    Mesmo motor, mais enxuto.
    Sem RBAC, lifecycle e audit.`"]
  end

  subgraph Fluxo["Caminho do plugin ate rodar"]
    autor["Autor do plugin"]
    loja["whatsbot-plugins - plugin.json + .zip"]
    page["whatsbot-pages - pagina /plugins"]
    pro["whatsbot-pro - RODA"]
    comm["whatsbot Community - RODA"]
    autor -->|"push main"| loja
    loja -->|"GitHub API"| page
    page -->|"download"| autor
    autor -->|"instala .zip"| pro
    autor -->|"instala .zip"| comm
  end

  titulo --> Explicacao --> Fluxo

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef noteC fill:#fff9db,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef lojaC fill:#ffe066,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef pageC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  classDef commC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  class titulo titleC;
  class e1,e2,e3,e4 noteC;
  class autor noteC;
  class loja lojaC;
  class page pageC;
  class pro proC;
  class comm commC;
```

---

## Capítulo 2 — Anatomia de um plugin

```mermaid
flowchart TB
  titulo["`**Cap. 2 - Anatomia de um plugin**
  Pasta com nome = id. O .zip contem o manifesto
  e os modulos de cada capacidade.`"]

  subgraph Aviso["Atencao - 2 arquivos diferentes"]
    a1["`**plugin.json** - na loja
    So o card: nome, icone, qual .zip baixar.`"]
    a2["`**plugin.yaml** - dentro do .zip
    O manifesto REAL que o app le:
    id, entry, screens, migrations.`"]
  end

  subgraph Mapa["entry: liga cada arquivo a uma capacidade"]
    yaml["plugin.yaml - entry"]
    yaml -->|"events"| ev["events.py - EVENT_HANDLERS"]
    yaml -->|"filters"| fi["filters.py - FILTERS"]
    yaml -->|"routes"| ro["routes.py - router REST"]
    yaml -->|"settings"| se["settings.py - Settings"]
    yaml -->|"tools"| to["tools.py - CORE_TOOLS"]
    yaml -->|"prompts"| pr["prompts.py - PROMPT_FRAGMENTS"]
    yaml -->|"lifecycle"| li["lifecycle.py - setup/teardown - so Pro"]
    yaml -.->|"migrations"| mg["migrations/*.sql - tabelas plugin_id_*"]
    yaml -.->|"screens"| sc["static/*.js - tela Preact"]
  end

  titulo --> Aviso --> Mapa

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef noteC fill:#fff9db,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef manC fill:#ffe066,stroke:#f59f00,stroke-width:3px,color:#5f3a00;
  classDef evC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef fiC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef apiC fill:#96f2d7,stroke:#0ca678,stroke-width:2px,color:#0a4a3a;
  classDef cfgC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef aiC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  classDef dataC fill:#dee2e6,stroke:#868e96,stroke-width:2px,color:#343a40;
  class titulo titleC;
  class a1,a2 noteC;
  class yaml manC;
  class ev evC;
  class fi fiC;
  class ro apiC;
  class se cfgC;
  class to,pr aiC;
  class li proC;
  class mg,sc dataC;
```

---

## Capítulo 3 — Ciclo de carregamento no boot

```mermaid
flowchart TB
  titulo["`**Cap. 3 - Ciclo de carregamento**
  No boot, o loader varre storages/plugins e carrega
  cada plugin HABILITADO. Erro fica isolado.`"]

  subgraph Notas["Pontos-chave"]
    n1["`Habilitar/desabilitar e um flag no banco.
    Nao apaga a pasta.`"]
    n2["`Migrations rodam em ordem 001, 002...
    Tabelas sempre com prefixo plugin_id_.`"]
    n3["`Plugin com erro registra load_error
    e o app sobe mesmo assim.`"]
  end

  subgraph Fluxo["Sequencia do loader"]
    start([Boot do servidor]) --> man{"plugin.yaml valido?"}
    man -->|"nao"| err1["Registra load_error e pula"]
    man -->|"sim"| en{"Habilitado?"}
    en -->|"nao"| skip["So descobre - nao carrega"]
    en -->|"sim"| deps["Instala deps pip - 1a vez"]
    deps --> imp["Importa modulos do entry"]
    imp --> migr["Roda migrations pendentes"]
    migr --> rbac["Sincroniza RBAC - so Pro"]
    rbac --> reg["Registra rotas e telas"]
    reg --> setup["lifecycle.setup - so Pro"]
    setup --> done([Plugin ativo])
  end

  titulo --> Notas --> Fluxo

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef noteC fill:#fff9db,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef startC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef decC fill:#ffec99,stroke:#f08c00,stroke-width:3px,color:#5f3a00;
  classDef procC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef errC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef skipC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef okC fill:#b2f2bb,stroke:#2f9e44,stroke-width:3px,color:#13491f;
  class titulo titleC;
  class n1,n2,n3 noteC;
  class start startC;
  class man,en decC;
  class deps,imp,migr,rbac,reg,setup procC;
  class err1 errC;
  class skip skipC;
  class done okC;
```

---

## Capítulo 4 — Eventos vs Filters (o coração)

```mermaid
flowchart TB
  titulo["`**Cap. 4 - Eventos vs Filters**
  Os 2 ganchos do plugin. Principio: nao tocar no core.`"]

  subgraph EV["EVENTOS - o plugin OBSERVA"]
    ev0["`Exporta EVENT_HANDLERS.
    Fire-and-forget. Nao altera o fluxo.
    Erro num handler nao afeta o core.`"]
    core1["Core - emit group.joined"] --> bus["Event bus"]
    bus -->|"task isolada"| h1["Handler do plugin A"]
    bus -->|"task isolada"| h2["Handler do plugin B"]
  end

  subgraph FI["FILTERS - o plugin MODIFICA"]
    fi0["`Exporta FILTERS.
    Intercepta o valor em transito.
    Retornar None ABORTA a acao.`"]
    core2["Core - apply_filter reply.part"] --> f1["Filter prio 50"]
    f1 -->|"valor mudado"| f2["Filter prio 100"]
    f2 -->|"valor final"| volta["Core usa o resultado"]
  end

  titulo --> EV
  titulo --> FI

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef noteC fill:#fff9db,stroke:#f59f00,stroke-width:2px,color:#5f3a00;
  classDef coreC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef evC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef fiC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  classDef okC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  class titulo titleC;
  class ev0,fi0 noteC;
  class core1,core2 coreC;
  class bus,h1,h2 evC;
  class f1,f2 fiC;
  class volta okC;
  style EV fill:#e7f5ff,stroke:#1971c2,stroke-width:2px;
  style FI fill:#f3f0ff,stroke:#7048e8,stroke-width:2px;
```

### Catálogo de nomes (cartão de consulta)

```mermaid
flowchart LR
  subgraph Eventos["Eventos mais usados"]
    ke["`message.received - message.sent
    message.persisted - message.reaction
    group.participants_changed - group.joined
    call.received - connection.changed
    conversation.created - conversation.status_changed
    contact.tagged - tag.created
    llm.before/after - tool.before/after
    Especiais: asterisco e message.any`"]
  end
  subgraph Filters["Filters mais usados"]
    kf["`filter.webhook.payload
    filter.message.before_save
    filter.transcription.should_run / result
    filter.contact.tags
    filter.system_prompt - filter.llm.messages
    filter.llm.tools
    filter.tool.args / result
    filter.reply.raw / parts / part
    filter.event.before_emit`"]
  end

  classDef evC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef fiC fill:#d0bfff,stroke:#7048e8,stroke-width:2px,color:#3b2080;
  class ke evC;
  class kf fiC;
```

---

## Capítulo 5 — O que o plugin recebe (contexto e serviços)

```mermaid
flowchart TB
  titulo["`**Cap. 5 - Contexto e servicos**
  Todo handler recebe um ctx com acesso a estes recursos.`"]

  subgraph Recursos["Servicos disponiveis no ctx"]
    plugin["Codigo do plugin"]
    plugin -->|"ctx.plugin_db()"| db["Tabelas plugin_id_* - engine compartilhado"]
    plugin -->|"broadcast(evento, dados)"| ws["WebSocket - painel ao vivo"]
    plugin -->|"config_repo get/set"| cfg["Settings persistidas - plugin.id.*"]
    plugin -->|"ctx.handler"| ag["AgentHandler - IA, mencoes, envio"]
    plugin -->|"group_mentions._client"| gowa["Cliente GOWA - enviar WhatsApp"]
    plugin -->|"ctx.on_unload - so Pro"| life["Cleanup no teardown"]
    plugin -->|"ctx.spawn_task - so Pro"| sup["Tasks e subprocessos supervisionados"]
  end

  titulo --> Recursos

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef plugC fill:#ffe066,stroke:#f59f00,stroke-width:3px,color:#5f3a00;
  classDef dbC fill:#dee2e6,stroke:#868e96,stroke-width:2px,color:#343a40;
  classDef wsC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef cfgC fill:#ffd8a8,stroke:#e8590c,stroke-width:2px,color:#7a2e00;
  classDef agC fill:#ffc9c9,stroke:#e03131,stroke-width:2px,color:#7a1212;
  classDef gowaC fill:#96f2d7,stroke:#0ca678,stroke-width:2px,color:#0a4a3a;
  classDef proC fill:#b2f2bb,stroke:#2f9e44,stroke-width:2px,color:#13491f;
  class titulo titleC;
  class plugin plugC;
  class db dbC;
  class ws wsC;
  class cfg cfgC;
  class ag agC;
  class gowa gowaC;
  class life,sup proC;
```

---

## Capítulo 6 — Fluxos reais (exemplos)

### 6a. Filter interceptivo — Auto Signature

```mermaid
sequenceDiagram
  autonumber
  box rgb(255,216,168) Core
  participant Core as Core - envio
  participant Bus as apply_filter
  end
  box rgb(208,191,255) Plugin
  participant P as Plugin auto_signature
  end
  Core->>Bus: apply_filter reply.part - texto
  Bus->>P: add_signature ctx, texto
  P->>P: le Settings e ctx.extras source
  P-->>Bus: texto + assinatura
  Bus-->>Core: texto assinado - usado no envio
```

### 6b. Evento — Boas-vindas em grupos

```mermaid
sequenceDiagram
  autonumber
  box rgb(150,242,215) WhatsApp
  participant GOWA as Webhook
  end
  box rgb(255,216,168) Core
  participant Core as Core
  participant Bus as Event bus
  end
  box rgb(165,216,255) Plugin
  participant P as Plugin boas_vindas
  end
  box rgb(222,226,230) Infra
  participant DB as plugin_boas_vindas
  participant WA as Cliente GOWA
  end

  GOWA->>Core: alguem entrou no grupo
  Core->>Bus: emit group.participants_changed
  Bus->>P: on_participants_changed
  P->>DB: grupo esta habilitado?
  DB-->>P: sim
  P->>P: thread - espera o delay
  P->>WA: send_message - marca a pessoa com @
  P->>Core: salva e faz broadcast new_message
  Note over P,Core: mensagem aparece no painel ao vivo
```

---

## Capítulo 7 — Passo a passo para criar um plugin

```mermaid
flowchart TB
  titulo["`**Cap. 7 - Criar um plugin**
  Do zero ate publicar na loja.`"]

  p1["`**1.** Crie a pasta meu_plugin
  nome snake_case = id`"]
  p2["`**2.** Escreva o plugin.yaml
  id, name, version, whatsbot_api_version, entry`"]
  p3["`**3.** Implemente as capacidades
  events / filters / migrations / settings`"]
  p4["`**4.** Teste local
  instale no app Pro e/ou Community`"]
  p5["`**5.** Empacote
  zipe o conteudo da pasta`"]
  p6["`**6.** Publique na loja
  plugin.json + .zip neste repo, push main`"]
  fim(["`Aparece em /plugins
  em ate 5 minutos`"])

  regra["`**Regra de ouro:** nao toque no core.
  Eventos para observar - filters para modificar -
  tabelas plugin_id_ para estado - broadcast para a UI.`"]

  titulo --> p1 --> p2 --> p3 --> p4 --> p5 --> p6 --> fim
  fim --> regra

  classDef titleC fill:#7048e8,stroke:#3b2080,stroke-width:3px,color:#ffffff;
  classDef stepC fill:#a5d8ff,stroke:#1971c2,stroke-width:2px,color:#0b3a66;
  classDef okC fill:#b2f2bb,stroke:#2f9e44,stroke-width:3px,color:#13491f;
  classDef regraC fill:#ffe066,stroke:#f59f00,stroke-width:3px,color:#5f3a00;
  class titulo titleC;
  class p1,p2,p3,p4,p5,p6 stepC;
  class fim okC;
  class regra regraC;
```
