-- Agendamentos de retorno. Uma linha = um retorno programado para um contato.
--   send_mode 'private_note' = agendado pelo atendente: no vencimento vira uma NOTA PRIVADA
--                              (lembrete interno, nada vai ao cliente);
--   send_mode 'ia_turn'      = agendado pela própria IA: no vencimento ela é acionada e
--                              escreve/envia a mensagem ao cliente (briefing = instrução).
-- O retorno automático (cliente em silêncio) NÃO usa tabela: é stateless, as próprias notas
-- dele são a memória. Convenções: timestamps em epoch (DOUBLE PRECISION), sem FK
-- cross-table (contact_id/phone são snapshot solto), prefixo plugin_agendamento_e_retorno_
-- obrigatório. INTEGER PRIMARY KEY AUTOINCREMENT vira IDENTITY no Postgres sozinho.
CREATE TABLE IF NOT EXISTS plugin_agendamento_e_retorno_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id     INTEGER NOT NULL,
    phone          TEXT    NOT NULL,
    contact_name   TEXT    NOT NULL DEFAULT '',
    due_at         DOUBLE PRECISION NOT NULL,           -- instante de disparo (epoch)
    send_mode      TEXT    NOT NULL DEFAULT 'private_note', -- 'private_note' | 'ia_turn'
    description    TEXT    NOT NULL DEFAULT '',          -- descrição digitada pelo atendente
    briefing       TEXT    NOT NULL DEFAULT '',          -- instrução para a IA seguir (ia_turn)
    status         TEXT    NOT NULL DEFAULT 'agendado',  -- agendado|processando|enviado|falhou|expirado|cancelado
    outcome        TEXT    NOT NULL DEFAULT '',
    outcome_reason TEXT    NOT NULL DEFAULT '',
    last_error     TEXT,
    created_by_ia  INTEGER NOT NULL DEFAULT 0,
    chain_depth    INTEGER NOT NULL DEFAULT 0,
    claimed_at     DOUBLE PRECISION,
    created_at     DOUBLE PRECISION NOT NULL,
    updated_at     DOUBLE PRECISION NOT NULL,
    sent_at        DOUBLE PRECISION
);

-- Consulta do verificador (status + vencimento).
CREATE INDEX IF NOT EXISTS plugin_agendamento_e_retorno_due
    ON plugin_agendamento_e_retorno_items(status, due_at);

-- "Existe retorno ATIVO da IA para este telefone?" (um por contato), a corrente
-- (chain_depth) e "este contato tem agendamento ativo?" (o retorno automático pula).
CREATE INDEX IF NOT EXISTS plugin_agendamento_e_retorno_phone_active
    ON plugin_agendamento_e_retorno_items(phone, send_mode, status);
