"""Agendamentos de retorno — armazenamento, regras e disparo.

Dois modos de disparo, os dois sobre a MESMA tabela e o MESMO verificador:

  * ``private_note`` — o atendente agenda pelo botão "Agendar" da conversa. No vencimento
    vira uma NOTA PRIVADA (lembrete interno, visível só no painel); nada vai ao cliente.
  * ``ia_turn``      — a própria IA agenda ("me chama amanhã às 9"). No vencimento ela é
    acionada de verdade: lê a instrução (``briefing``), escreve e envia a mensagem.

Escopo do retorno é o ``phone`` (o Lite não tem "conversa" separada do contato).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text as sqltext

from plugins.context import make_plugin_db

from . import common
from .common import TURN_TIMEOUT_SECONDS, notify_changed, now

logger = logging.getLogger("plugin.agendamento_e_retorno")

TABLE = "plugin_agendamento_e_retorno_items"

STATUS_SCHEDULED = "agendado"
STATUS_PROCESSING = "processando"   # claim atômico enquanto dispara
STATUS_SENT = "enviado"
STATUS_FAILED = "falhou"
STATUS_EXPIRED = "expirado"
STATUS_CANCELLED = "cancelado"

SEND_MODE_NOTE = "private_note"
SEND_MODE_IA = "ia_turn"

OUTCOME_SENT = "enviado"
OUTCOME_NOTE = "nota_privada"
OUTCOME_NO_REPLY = "sem_resposta"
OUTCOME_REPLACED = "substituido"
OUTCOME_CLIENT_REPLIED = "cliente_respondeu"

REASON_AI_OFF = "ia_desligada"
REASON_NO_REPLY = "sem_resposta"
REASON_PLUGIN_BLOCKED = "bloqueado_por_plugin"

# Prefixos INVARIANTES das notas deste plugin. filters.py usa os dois primeiros para
# esconder o lembrete interno da IA; o terceiro (instrução da IA) PRECISA chegar ao modelo.
RETURN_NOTE_MARKER = "A data prevista para o retorno do(a) cliente"
IA_FALLBACK_MARKER = "Retorno agendado pela IA não foi disparado"
IA_BRIEFING_MARKER = "Retorno agendado por você — instrução para esta mensagem:"

_MOTIVOS = {REASON_AI_OFF: "a IA está desligada para este contato agora."}

DESCRIPTION_MAX = 500


# ── Consultas ────────────────────────────────────────────────────────────────

def get_item(item_id: int) -> dict | None:
    with make_plugin_db() as conn:
        row = conn.execute(
            sqltext(f"SELECT * FROM {TABLE} WHERE id = :id"), {"id": item_id}
        ).mappings().first()
    return dict(row) if row else None


def list_items(*, status=None, phone=None, contact_id=None, limit: int = 500) -> list[dict]:
    clauses, params = [], {"limit": max(1, min(int(limit or 500), 1000))}
    if status and status not in ("todos", "all"):
        clauses.append("status = :status")
        params["status"] = STATUS_SCHEDULED if status in ("ativos", "ativo") else status
    if phone:
        clauses.append("phone = :phone")
        params["phone"] = phone
    if contact_id:
        clauses.append("contact_id = :contact_id")
        params["contact_id"] = int(contact_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with make_plugin_db() as conn:
        rows = conn.execute(
            sqltext(f"SELECT * FROM {TABLE} {where} ORDER BY due_at DESC LIMIT :limit"), params
        ).mappings().all()
    return [dict(r) for r in rows]


def phones_with_active_items() -> set[str]:
    """Telefones com retorno agendado/em disparo. O retorno automático pula esses contatos:
    quem já tem um retorno marcado não recebe também a cutucada por silêncio."""
    with make_plugin_db() as conn:
        rows = conn.execute(
            sqltext(f"SELECT DISTINCT phone FROM {TABLE} WHERE status IN (:a, :b)"),
            {"a": STATUS_SCHEDULED, "b": STATUS_PROCESSING},
        ).all()
    return {r[0] for r in rows}


# ── Criação / cancelamento / exclusão (atendente) ────────────────────────────

def create_item(*, phone: str, contact_name: str | None, due_at, description: str | None):
    """Agendamento do atendente (``private_note``). Devolve ``(item, erro)``."""
    from db.repositories import contact_repo

    phone = (phone or "").strip()
    if not phone:
        return None, "Selecione o cliente."
    try:
        due_at = float(due_at)
    except (TypeError, ValueError):
        return None, "Informe a data e a hora do retorno."
    if due_at < now() - 60:
        return None, "Escolha uma data/hora no futuro."

    contact = contact_repo.get_by_phone(phone)
    if not contact:
        return None, "Contato não encontrado."
    stored_name = (contact.get("group_name") if contact.get("is_group") else contact.get("name")) or ""
    ts = now()
    params = {
        "contact_id": contact["id"],
        "phone": contact.get("phone") or phone,
        "contact_name": (contact_name or "").strip() or stored_name,
        "due_at": due_at,
        "description": (description or "").strip()[:DESCRIPTION_MAX],
        "created_at": ts,
        "updated_at": ts,
    }
    with make_plugin_db() as conn:
        new_id = conn.execute(
            sqltext(
                f"INSERT INTO {TABLE} (contact_id, phone, contact_name, due_at, send_mode, "
                f"description, status, created_at, updated_at) VALUES (:contact_id, :phone, "
                f":contact_name, :due_at, '{SEND_MODE_NOTE}', :description, "
                f"'{STATUS_SCHEDULED}', :created_at, :updated_at) RETURNING id"
            ),
            params,
        ).scalar()
    notify_changed(new_id, STATUS_SCHEDULED)
    return get_item(new_id), None


def cancel_item(item_id: int):
    row = get_item(item_id)
    if not row:
        return None, "Agendamento não encontrado."
    if row["status"] != STATUS_SCHEDULED:
        return None, "Só é possível cancelar agendamentos ativos."
    _set_status(item_id, STATUS_CANCELLED)
    notify_changed(item_id, STATUS_CANCELLED)
    return get_item(item_id), None


def delete_item(item_id: int) -> bool:
    with make_plugin_db() as conn:
        res = conn.execute(sqltext(f"DELETE FROM {TABLE} WHERE id = :id"), {"id": item_id})
    ok = (res.rowcount or 0) > 0
    if ok:
        notify_changed(item_id, "deleted")
    return ok


def _set_status(item_id: int, status: str, *, last_error=None) -> None:
    with make_plugin_db() as conn:
        conn.execute(
            sqltext(f"UPDATE {TABLE} SET status = :s, updated_at = :u, last_error = :e WHERE id = :id"),
            {"s": status, "u": now(), "e": last_error, "id": item_id},
        )


# ── Retorno marcado pela própria IA ──────────────────────────────────────────

def cliente_respondeu(phone: str, since: float) -> bool:
    """Houve mensagem DO CLIENTE depois de ``since``? Se ele voltou a falar sozinho, o
    retorno perdeu a razão de existir — a IA não "cobra" quem já retomou."""
    try:
        from db.repositories import contact_repo, message_repo
        contact = contact_repo.get_by_phone(phone)
        if not contact:
            return False
        last_user = message_repo.get_last_user_message(contact["id"])
    except Exception:  # noqa: BLE001 — na dúvida NÃO cancela (o retorno foi combinado)
        return False
    return bool(last_user) and float(last_user.get("ts") or 0) > float(since or 0)


def chain_depth_for(phone: str) -> int:
    """Quantos retornos da IA já dispararam com este contato SEM ele responder.
    Uma mensagem do cliente depois do último disparo ZERA a corrente."""
    with make_plugin_db() as conn:
        row = conn.execute(
            sqltext(
                f"SELECT chain_depth, sent_at, updated_at FROM {TABLE} "
                f"WHERE phone = :phone AND send_mode = :mode "
                f"AND status IN ('{STATUS_SENT}', '{STATUS_FAILED}') "
                f"ORDER BY COALESCE(sent_at, updated_at) DESC, id DESC LIMIT 1"
            ),
            {"phone": phone, "mode": SEND_MODE_IA},
        ).mappings().first()
    if not row:
        return 0
    quando = row.get("sent_at") or row.get("updated_at") or 0
    if cliente_respondeu(phone, since=float(quando)):
        return 0
    return int(row.get("chain_depth") or 0) + 1


def create_ia_item(*, contact: dict, due_at: float, briefing: str, chain_depth: int = 0):
    """Cria o agendamento da IA, SUBSTITUINDO o anterior do mesmo contato (no máximo um
    ativo por contato). Substituição e inserção na MESMA transação: um vencimento nunca
    pega duas linhas ativas."""
    contact_id = contact.get("id")
    if not contact_id:
        return None, "contato inválido"
    ts = now()
    phone = contact.get("phone") or ""
    params = {
        "contact_id": contact_id, "phone": phone,
        "contact_name": (contact.get("name") or "").strip(),
        "due_at": float(due_at), "briefing": (briefing or "").strip(),
        "chain_depth": int(chain_depth or 0), "created_at": ts, "updated_at": ts,
    }
    with make_plugin_db() as conn:
        replaced = conn.execute(
            sqltext(
                f"UPDATE {TABLE} SET status = :cancelled, outcome = :outcome, updated_at = :now "
                f"WHERE phone = :phone AND send_mode = :mode AND created_by_ia = 1 "
                f"AND status = :scheduled"
            ),
            {"cancelled": STATUS_CANCELLED, "outcome": OUTCOME_REPLACED, "now": ts,
             "phone": phone, "mode": SEND_MODE_IA, "scheduled": STATUS_SCHEDULED},
        ).rowcount or 0
        new_id = conn.execute(
            sqltext(
                f"INSERT INTO {TABLE} (contact_id, phone, contact_name, due_at, send_mode, "
                f"briefing, status, created_by_ia, chain_depth, created_at, updated_at) "
                f"VALUES (:contact_id, :phone, :contact_name, :due_at, '{SEND_MODE_IA}', "
                f":briefing, '{STATUS_SCHEDULED}', 1, :chain_depth, :created_at, "
                f":updated_at) RETURNING id"
            ),
            params,
        ).scalar()
    notify_changed(new_id, STATUS_SCHEDULED)
    item = get_item(new_id) or {}
    item["_replaced"] = bool(replaced)
    return item, None


def cancel_active_ia_items(phone: str, *, motivo: str = "") -> int:
    with make_plugin_db() as conn:
        n = conn.execute(
            sqltext(
                f"UPDATE {TABLE} SET status = :cancelled, outcome_reason = :motivo, "
                f"updated_at = :now WHERE phone = :phone AND send_mode = :mode "
                f"AND created_by_ia = 1 AND status = :scheduled"
            ),
            {"cancelled": STATUS_CANCELLED, "motivo": (motivo or "")[:200], "now": now(),
             "phone": phone, "mode": SEND_MODE_IA, "scheduled": STATUS_SCHEDULED},
        ).rowcount or 0
    if n:
        notify_changed(0, STATUS_CANCELLED)
    return int(n)


# ── Disparo ──────────────────────────────────────────────────────────────────

def _claim(item_id: int) -> bool:
    """Tira a linha da fila (``agendado`` → ``processando``). ``False`` = outro levou."""
    with make_plugin_db() as conn:
        n = conn.execute(
            sqltext(
                f"UPDATE {TABLE} SET status = :processing, claimed_at = :now, updated_at = :now "
                f"WHERE id = :id AND status = :scheduled"
            ),
            {"processing": STATUS_PROCESSING, "now": now(), "id": int(item_id),
             "scheduled": STATUS_SCHEDULED},
        ).rowcount or 0
    return bool(n)


def _finish(item_id: int, status: str, outcome: str, reason: str = "", last_error=None) -> None:
    ts = now()
    with make_plugin_db() as conn:
        conn.execute(
            sqltext(
                f"UPDATE {TABLE} SET status = :status, outcome = :outcome, outcome_reason = :reason, "
                f"last_error = :err, updated_at = :now, sent_at = COALESCE(sent_at, :sent) "
                f"WHERE id = :id"
            ),
            {"status": status, "outcome": outcome, "reason": (reason or "")[:200],
             "err": last_error, "now": ts, "sent": ts if status == STATUS_SENT else None,
             "id": int(item_id)},
        )
    notify_changed(item_id, status)


def recover_stale_processing(older_than: float) -> int:
    """Linhas presas em ``processando`` (restart no meio do disparo) vão para o histórico
    como falha. Não reenvia: um turno interrompido pode ter mandado parte das mensagens."""
    with make_plugin_db() as conn:
        n = conn.execute(
            sqltext(
                f"UPDATE {TABLE} SET status = :failed, outcome = :outcome, "
                f"last_error = 'disparo interrompido (o servidor reiniciou durante o disparo)', "
                f"updated_at = :now WHERE status = :processing AND COALESCE(claimed_at, 0) < :cutoff"
            ),
            {"failed": STATUS_FAILED, "outcome": OUTCOME_NO_REPLY, "now": now(),
             "processing": STATUS_PROCESSING, "cutoff": float(older_than)},
        ).rowcount or 0
    return int(n)


def build_reminder_text(description: str | None, contact_name: str | None) -> str:
    """Texto da nota-lembrete do atendente. O prefixo é invariante (ver filters.py)."""
    who = (contact_name or "").strip()
    text = f"{RETURN_NOTE_MARKER} {who} chegou !!! 🔔".replace("  ", " ")
    desc = (description or "").strip()
    return f"{text}\n\nDescrição: {desc}" if desc else text


def _build_fallback_note(*, reason: str, briefing: str, contact_name: str = "") -> str:
    quem = (contact_name or "").strip() or "o cliente"
    return (
        f"{IA_FALLBACK_MARKER}: {_MOTIVOS.get(reason, reason)}"
        f"\n\nO que a IA ia tratar com {quem}: {(briefing or '').strip() or '(sem instrução registrada)'}"
        f"\n\nSe ainda fizer sentido, retome você mesmo."
    )


async def _fallback_note(row: dict, *, reason: str) -> None:
    body = _build_fallback_note(reason=reason, briefing=row.get("briefing") or "",
                                contact_name=row.get("contact_name") or "")
    await common.write_private_note(row.get("phone") or "", body)
    _finish(int(row["id"]), STATUS_SENT, OUTCOME_NOTE, reason)


async def _dispatch_note(row: dict) -> None:
    """Lembrete do atendente: uma nota privada, nada vai ao cliente."""
    body = build_reminder_text(row.get("description"), row.get("contact_name"))
    await common.write_private_note(row.get("phone") or "", body)
    _finish(int(row["id"]), STATUS_SENT, OUTCOME_NOTE)


async def _dispatch_ia(row: dict) -> None:
    item_id = int(row["id"])
    phone = row.get("phone") or ""
    briefing = (row.get("briefing") or "").strip()

    if common.handler() is None:
        _finish(item_id, STATUS_FAILED, OUTCOME_NO_REPLY, REASON_NO_REPLY,
                last_error="agent_handler indisponível")
        return

    # O cliente voltou a falar sozinho? Cancela sem nota — a conversa já está viva.
    if await asyncio.to_thread(cliente_respondeu, phone, row.get("created_at") or 0):
        _finish(item_id, STATUS_CANCELLED, OUTCOME_CLIENT_REPLIED)
        return

    from db.repositories import contact_repo
    contact = await asyncio.to_thread(contact_repo.get_by_phone, phone)
    if not contact or not contact.get("ai_enabled"):
        await _fallback_note(row, reason=REASON_AI_OFF)
        return

    await common.write_private_note(phone, f"{IA_BRIEFING_MARKER}\n\n{briefing}")
    turn = await common.run_ai_turn(phone, briefing, source="agendamento_e_retorno_ia")

    if turn.outcome == "sent":
        _finish(item_id, STATUS_SENT, OUTCOME_SENT)
    elif turn.outcome == "ai_off":
        await _fallback_note(row, reason=REASON_AI_OFF)
    elif turn.outcome == "blocked":
        _finish(item_id, STATUS_FAILED, OUTCOME_NO_REPLY, REASON_PLUGIN_BLOCKED)
    else:
        _finish(item_id, STATUS_FAILED, OUTCOME_NO_REPLY, REASON_NO_REPLY, last_error=turn.error)


async def run_due_cycle(cfg) -> dict:
    """Um ciclo: expira o que passou da tolerância e dispara o que venceu."""
    ts = now()
    tol = max(0, int(cfg.tolerance_minutes)) * 60
    try:
        await asyncio.to_thread(recover_stale_processing, ts - TURN_TIMEOUT_SECONDS * 3)
    except Exception:  # noqa: BLE001 — a varredura nunca derruba o ciclo
        logger.debug("varredura de 'processando' falhou", exc_info=True)

    def _load_due():
        with make_plugin_db() as conn:
            rows = conn.execute(
                sqltext(f"SELECT * FROM {TABLE} WHERE status = :st AND due_at <= :now ORDER BY due_at ASC"),
                {"st": STATUS_SCHEDULED, "now": ts},
            ).mappings().all()
        return [dict(r) for r in rows]

    due = await asyncio.to_thread(_load_due)
    sent = expired = failed = 0
    for row in due:
        if ts - float(row["due_at"]) > tol:
            await asyncio.to_thread(_set_status, row["id"], STATUS_EXPIRED)
            notify_changed(row["id"], STATUS_EXPIRED)
            expired += 1
            continue
        try:
            if not await asyncio.to_thread(_claim, row["id"]):
                continue  # outro ciclo levou
            fresh = await asyncio.to_thread(get_item, row["id"]) or row
            if fresh.get("send_mode") == SEND_MODE_IA:
                await _dispatch_ia(fresh)
            else:
                await _dispatch_note(fresh)
        except Exception as e:  # noqa: BLE001 — falha de um item nunca derruba o ciclo
            logger.warning("disparo falhou (id=%s): %s", row["id"], e)
            await asyncio.to_thread(_set_status, row["id"], STATUS_FAILED, last_error=str(e)[:500])
            notify_changed(row["id"], STATUS_FAILED)
            failed += 1
            continue
        final = (await asyncio.to_thread(get_item, row["id"])) or {}
        if final.get("status") == STATUS_FAILED:
            failed += 1
        elif final.get("status") != STATUS_CANCELLED:
            sent += 1
    return {"due": len(due), "sent": sent, "expired": expired, "failed": failed}
