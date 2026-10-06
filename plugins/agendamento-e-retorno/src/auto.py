"""Retorno automático — cutuca o atendimento quando o cliente fica em SILÊNCIO.

Design STATELESS (herdado do plugin original): as próprias notas privadas do plugin SÃO a
memória. Toda nota carrega um prefixo fixo (:data:`NOTE_MARKER`) no início do texto — é ele,
e não uma coluna de autor (o Lite não tem), que a consulta agregada usa para reconhecer "notas
do plugin". Sem tabela própria: o comportamento se auto-recupera após restart.

Integração com o agendamento: um contato com retorno AGENDADO/em disparo é pulado (ver
``run_cycle``). E o turno em que a IA responde marca ``in_proactive_turn`` em ``common``, então
a IA não consegue agendar outro retorno dentro dele.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import text

from . import common
from .common import now
from .hours import is_open_now

logger = logging.getLogger("plugin.agendamento_e_retorno")

# Mesmo prefixo do plugin original `retorno_automatico` DE PROPÓSITO: notas já postadas por
# ele continuam contando (continuidade na migração). Fica FORA do template editável.
NOTE_MARKER = "🔔 Retorno Automático: "


def list_candidates(apply_to_groups: bool) -> list[dict]:
    """Contatos com a IA ligada e não arquivados. Grupos só com ``apply_to_groups``."""
    from db.engine import get_engine

    sql = text(
        "SELECT id AS contact_id, phone, name AS contact_name, group_name, is_group "
        "FROM contacts WHERE ai_enabled = 1 AND is_archived = 0 "
        "AND (is_group = 0 OR :apply_to_groups = 1) ORDER BY id"
    )
    with get_engine().connect() as conn:
        rows = conn.execute(sql, {"apply_to_groups": 1 if apply_to_groups else 0}).mappings().all()
    return [dict(r) for r in rows]


def contact_signals(contact_id: int) -> dict:
    """Os 4 sinais stateless de um contato numa única consulta agregada.

    * ``last_client_ts``    — MAX(ts) de ``role='user'`` (o RESET).
    * ``last_outbound_ts``  — MAX(ts) de ``assistant`` sem ``failed`` (IA + operador).
    * ``last_note_ts``      — MAX(ts) das notas do plugin (``content`` começa com o marcador).
    * ``notes_since_reply`` — nº dessas notas com ``ts > last_client_ts`` (o contador).
    """
    from db.engine import get_engine

    sql = text(
        "WITH lc AS (SELECT MAX(ts) AS t FROM messages WHERE contact_id = :cid AND role = 'user') "
        "SELECT (SELECT t FROM lc) AS last_client_ts, "
        "MAX(CASE WHEN role = 'assistant' AND (status IS NULL OR status <> 'failed') THEN ts END) AS last_outbound_ts, "
        "MAX(CASE WHEN role = 'private_note' AND content LIKE :marker THEN ts END) AS last_note_ts, "
        "SUM(CASE WHEN role = 'private_note' AND content LIKE :marker "
        "         AND ts > COALESCE((SELECT t FROM lc), 0) THEN 1 ELSE 0 END) AS notes_since_reply "
        "FROM messages WHERE contact_id = :cid"
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"cid": contact_id, "marker": NOTE_MARKER + "%"}).mappings().first()
    if row is None:
        return {"last_client_ts": None, "last_outbound_ts": None, "last_note_ts": None,
                "notes_since_reply": 0}

    def _f(v):
        return float(v) if v is not None else None

    return {"last_client_ts": _f(row["last_client_ts"]), "last_outbound_ts": _f(row["last_outbound_ts"]),
            "last_note_ts": _f(row["last_note_ts"]), "notes_since_reply": int(row["notes_since_reply"] or 0)}


@dataclass
class Decision:
    fire: bool
    reason: str
    tentativa: int | None = None


def decide(ts: float, signals: Mapping, cfg: Any) -> Decision:
    """Decide se um contato deve receber uma nota AGORA (pura, sem efeitos).

    Skip: ``sem_saida`` (IA/operador nunca falou), ``cliente_respondeu``, ``limite_atingido``
    (standby), ``nao_venceu`` (relógio), ``fora_expediente`` (adia p/ o próximo tick útil).
    """
    last_client = signals.get("last_client_ts")
    last_out = signals.get("last_outbound_ts")
    last_note = signals.get("last_note_ts")
    notes = int(signals.get("notes_since_reply") or 0)

    if last_out is None:
        return Decision(False, "sem_saida")
    if not ((last_client is None) or (last_client < last_out)):
        return Decision(False, "cliente_respondeu")
    if notes >= int(cfg.auto_max_consecutive_notes or 1):
        return Decision(False, "limite_atingido")
    anchor = max(last_out, last_note or 0.0)
    if (ts - anchor) < float(cfg.auto_silence_minutes or 0) * 60:
        return Decision(False, "nao_venceu")
    if not is_open_now(ts, cfg):
        return Decision(False, "fora_expediente")
    return Decision(True, "fire", tentativa=notes + 1)


# ── Texto da nota ────────────────────────────────────────────────────────────

class _SafeDict(dict):
    def __missing__(self, key):  # placeholder desconhecido fica literal
        return "{" + key + "}"


def _human_duration(total_minutes) -> str:
    """45→'45min', 60→'1h', 90→'1h30min', 180→'3h'."""
    try:
        m = int(round(float(total_minutes)))
    except (TypeError, ValueError):
        return str(total_minutes)
    if m < 60:
        return f"{m}min"
    h, rem = divmod(m, 60)
    return f"{h}h" if rem == 0 else f"{h}h{rem}min"


def render_note(template: str, *, cliente: str | None, minutes, tentativa, max_notes) -> str:
    try:
        hours = "%g" % (float(minutes) / 60.0)
    except (TypeError, ValueError):
        hours = str(minutes)
    values = _SafeDict(
        cliente=(cliente or "cliente").strip() or "cliente", tempo=_human_duration(minutes),
        minutos=int(minutes) if str(minutes).lstrip("-").isdigit() else minutes,
        horas=hours, tentativa=tentativa, max=max_notes)
    try:
        return str(template).format_map(values)
    except Exception:  # noqa: BLE001 — template quebrado nunca impede o disparo
        return str(template)


async def dispatch_note(candidate: Mapping, tentativa: int, cfg: Any) -> None:
    """Posta a nota privada e, com ``auto_ai_reply`` (padrão), aciona a IA para ler essa
    nota e responder de verdade ao cliente. Levanta se a NOTA falhar; a resposta da IA é
    best-effort e nunca desfaz a nota."""
    phone = candidate.get("phone")
    if not phone:
        raise RuntimeError("candidato sem phone")

    nome = candidate.get("group_name") if candidate.get("is_group") else candidate.get("contact_name")
    body = NOTE_MARKER + render_note(
        cfg.auto_note_template, cliente=nome, minutes=cfg.auto_silence_minutes,
        tentativa=tentativa, max_notes=cfg.auto_max_consecutive_notes)
    await common.write_private_note(phone, body)

    if cfg.auto_ai_reply:
        turn = await common.run_ai_turn(phone, body, source="retorno_automatico_ia")
        if turn.outcome != "sent":
            logger.info("[RetornoAutomatico] IA não respondeu (phone=%s): %s %s",
                        phone, turn.outcome, turn.error or "")


async def run_cycle(cfg, busy_phones: set[str]) -> dict:
    """Um ciclo do verificador. Falha de um item nunca derruba o ciclo."""
    ts = now()
    candidates = await asyncio.to_thread(list_candidates, bool(cfg.auto_apply_to_groups))

    fired = skipped = failed = 0
    for cand in candidates:
        try:
            if cand["phone"] in busy_phones:  # tem retorno agendado: o agendamento manda
                skipped += 1
                continue
            signals = await asyncio.to_thread(contact_signals, cand["contact_id"])
            decision = decide(ts, signals, cfg)
            if not decision.fire:
                skipped += 1
                continue
            await dispatch_note(cand, decision.tentativa, cfg)
            fired += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("[RetornoAutomatico] item falhou (contato=%s): %s", cand.get("contact_id"), e)
    return {"checked": len(candidates), "fired": fired, "skipped": skipped, "failed": failed}
