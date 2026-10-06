"""Peças compartilhadas entre o agendamento e o retorno automático.

Os dois plugins originais duplicavam quase tudo isto (captura do AgentHandler, dedup do
eco do GOWA, leitura de settings, escrita de nota privada e o turno em que a IA é acionada
e responde de verdade ao cliente). Aqui existe UMA cópia de cada, então os dois recursos
enviam do mesmo jeito, respeitam as mesmas travas e usam o mesmo anti-loop.
"""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import logging
import time
from datetime import timedelta, timezone
from typing import Any

from plugins.context import broadcast

logger = logging.getLogger("plugin.agendamento_e_retorno")

PLUGIN_ID = "agendamento_e_retorno"

# Plugins antigos que este substitui. Se algum continuar habilitado junto com este, os
# dois verificadores disparam em dobro — ver events.legacy_enabled().
LEGACY_IDS = ("agendamento_retorno", "retorno_automatico")

# Fuso do bloco "--- Data e hora atual ---" que o core injeta no system prompt
# (agent/handler.py): offset FIXO -03:00, sem DST e sem depender da TZ do processo.
BRT = timezone(timedelta(hours=-3))

TURN_TIMEOUT_SECONDS = 120.0


def now() -> float:
    return time.time()


# ── AgentHandler capturado no boot (events.py) ───────────────────────────────
#
# ``EventContext.handler`` já É o ``AgentHandler`` real; guardamos a referência para o
# verificador (que roda fora de qualquer dispatch de evento) conseguir usá-la.
_HANDLER = None


def set_handler(handler) -> None:
    global _HANDLER
    if handler is not None:
        _HANDLER = handler


def handler():
    return _HANDLER


# ── Anti-loop: turno proativo em curso ────────────────────────────────────────
#
# Ligado ao redor da chamada de ``aprocess_message``. Durante um turno proativo (retorno
# agendado OU nota do retorno automático), a ferramenta ``agendar_retorno_ia`` recusa:
# senão a IA criaria uma corrente IA→IA sem o cliente nunca falar. ``ContextVar`` porque o
# executor da tool roda na mesma cadeia de awaits/threads do turno.
_IN_TURN: contextvars.ContextVar = contextvars.ContextVar(
    "agendamento_e_retorno_in_turn", default=False)


def in_proactive_turn() -> bool:
    return bool(_IN_TURN.get())


# ── Dedup do próprio eco ──────────────────────────────────────────────────────
#
# O core usa ``state.recently_sent`` para reconhecer o eco de uma mensagem que ELE mandou
# quando ela volta pelo webhook (``is_from_me=True``); sem isso o GOWA ecoaria a resposta
# da IA e o core salvaria uma bolha "Manual" duplicada. ``state`` não é exposto a plugins,
# então mantemos a MESMA ideia aqui e a consumimos em filters.py via
# ``filter.message.outgoing``.
_recently_sent: dict[str, float] = {}


def mark_sent(phone: str, wire_text: str) -> None:
    _recently_sent[f"{phone}:{(wire_text or '')[:120]}"] = now()


def consume_recent_echo(phone: str, text_: str) -> bool:
    """``True`` (e remove) se este texto foi mandado por nós há menos de 30s."""
    ts = _recently_sent.pop(f"{phone}:{(text_ or '')[:120]}", None)
    return ts is not None and (now() - ts) < 30


def prune_recently_sent() -> None:
    cutoff = now() - 60
    for key in [k for k, v in _recently_sent.items() if v < cutoff]:
        _recently_sent.pop(key, None)


# ── Settings (lidas a cada uso — valem sem restart) ───────────────────────────

def load_settings():
    """Monta um ``Settings`` a partir das chaves ``plugin.agendamento_e_retorno.*``.

    Uma única leitura do ``config`` por chamada. Só as chaves salvas sobrescrevem os
    defaults do modelo. Config malformada nunca derruba o ciclo: cai nos defaults.
    """
    from db.repositories import config_repo

    from .settings import Settings

    prefix = f"plugin.{PLUGIN_ID}."
    try:
        stored = config_repo.get_all()
        data = {name: stored[prefix + name] for name in Settings.model_fields
                if (prefix + name) in stored and stored[prefix + name] is not None}
        return Settings(**data)
    except Exception:  # noqa: BLE001
        logger.warning("settings inválidas em config — usando os defaults", exc_info=True)
        return Settings()


# ── Nota privada ─────────────────────────────────────────────────────────────

def _save_note(phone: str, body: str) -> dict | None:
    from db.repositories import message_repo

    contact = _HANDLER._get_contact(phone)
    contact.add_message("private_note", body)
    return message_repo.get_last(contact.id)


async def write_private_note(phone: str, body: str) -> dict:
    """Grava uma nota privada (painel-only) e avisa o painel. Levanta se não conseguir."""
    if _HANDLER is None:
        raise RuntimeError("agent_handler indisponível (runtime não conectado)")
    saved = await asyncio.to_thread(_save_note, phone, body) or {}
    message = {"role": "private_note", "content": body,
               "ts": saved.get("ts") or now(), "status": None}
    if saved.get("_id"):
        message["_id"] = saved["_id"]
    if saved.get("msg_id"):
        message["msg_id"] = saved["msg_id"]
    try:
        broadcast("new_message", {"phone": phone, "message": message})
    except Exception:  # noqa: BLE001 — broadcast nunca quebra a operação
        logger.debug("broadcast new_message falhou")
    return saved


# ── Envio real pelo GOWA ─────────────────────────────────────────────────────

def _gowa_client():
    from db.repositories import config_repo
    from gowa.client import GOWAClient

    return GOWAClient(port=int(config_repo.get("gowa_port", 3000) or 3000))


def _is_sandbox(phone: str) -> bool:
    """Contato de teste (Sandbox): o número não existe no WhatsApp, então o envio fica local."""
    try:
        from db.repositories import config_repo
        return bool(config_repo.get(f"sandbox_contact.{phone}"))
    except Exception:  # noqa: BLE001
        return False


async def _resolve_send_text(phone: str, part: str) -> tuple[str, list[str] | None]:
    if "@g.us" not in phone:
        return part, None
    try:
        from agent import group_mentions
        return await asyncio.to_thread(group_mentions.resolve_outgoing, phone, part)
    except Exception:  # noqa: BLE001 — grupo sem resolução cai pro texto cru
        logger.debug("resolve_outgoing falhou", exc_info=True)
        return part, None


async def _emit_sent(phone: str, text_: str, msg_id: str | None, *, source: str) -> None:
    try:
        from plugins.events import emit_with_filter
        await emit_with_filter("message.sent", {
            "phone": phone, "text": text_, "msg_id": msg_id,
            "media_type": None, "media_path": None,
            "source": source, "status": "sent", "ts": now(),
        })
    except Exception:  # noqa: BLE001
        logger.debug("emit message.sent falhou", exc_info=True)


# ── Turno da IA: ler a instrução (nota privada) e responder DE VERDADE ────────

@dataclasses.dataclass
class TurnResult:
    outcome: str          # sent | no_reply | ai_off | blocked | timeout | error | send_failed
    sent: int = 0
    error: str | None = None


async def run_ai_turn(phone: str, instruction: str, *, source: str) -> TurnResult:
    """Aciona a IA para ler a nota privada já gravada e mandar a resposta ao cliente.

    A nota privada é o ÚNICO veículo da instrução até o modelo: ``aprocess_message``
    descarta ``text`` quando ``save_user_message=False``, e o core traduz ``private_note``
    para ``role="user"`` com o prefixo "[Nota privada do operador]: ...". Por isso quem
    chama grava a nota ANTES e ``instruction`` aqui só documenta a chamada.

    Nunca levanta: devolve um ``TurnResult`` para o chamador decidir o que registrar.
    """
    from db.repositories import contact_repo
    from plugins.events import apply_filter

    h = _HANDLER
    if h is None:
        return TurnResult("error", error="agent_handler indisponível")

    token = _IN_TURN.set(True)
    try:
        result = await asyncio.wait_for(
            h.aprocess_message(phone, instruction, save_user_message=False, save_response=False),
            timeout=TURN_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return TurnResult("timeout", error="turno da IA excedeu o tempo limite")
    except Exception as e:  # noqa: BLE001
        logger.warning("turno da IA falhou (phone=%s): %s", phone, e)
        return TurnResult("error", error=str(e)[:500])
    finally:
        _IN_TURN.reset(token)

    reply = (getattr(result, "reply", "") or "").strip()
    # O core devolve erros do próprio app como texto "[WhatsBot-Lite] ..." (chave inválida,
    # limite de requisições, falha do modelo). Isso NUNCA pode ir para o cliente.
    if not reply or reply.startswith("[WhatsBot"):
        return TurnResult("no_reply", error=reply[:500] or None)

    # Reconfere DEPOIS do turno: a IA pode ter sido desligada enquanto redigia (o turno
    # leva dezenas de segundos) — não se fala por cima de quem desligou.
    contact = await asyncio.to_thread(contact_repo.get_by_phone, phone)
    if not contact or not contact.get("ai_enabled"):
        return TurnResult("ai_off")

    reply = await apply_filter("filter.reply.raw", reply, {"phone": phone})
    if reply is None:
        return TurnResult("blocked")

    split = True
    try:
        from db.repositories import config_repo
        split = bool(config_repo.get("split_messages", True))
    except Exception:  # noqa: BLE001
        pass
    from server.helpers import parse_split_reply
    parts = parse_split_reply(reply) if split else [reply]
    parts = await apply_filter("filter.reply.parts", parts, {"phone": phone, "source": source})
    if not parts:
        return TurnResult("blocked")

    from gowa.client import extract_msg_id
    sandbox = _is_sandbox(phone)
    client = None if sandbox else _gowa_client()

    sent = 0
    last_error = None
    for index, raw in enumerate(parts):
        part = await apply_filter(
            "filter.reply.part", raw,
            {"phone": phone, "index": index, "total": len(parts), "source": source})
        if part is None or not str(part).strip():
            continue
        part = str(part).strip()

        msg_id = None
        if client is not None:
            send_text, mentions = await _resolve_send_text(phone, part)
            mark_sent(phone, send_text)
            try:
                send_result = await asyncio.to_thread(client.send_message, phone, send_text, mentions)
            except Exception as e:  # noqa: BLE001 — para no meio; o que já saiu fica salvo
                logger.warning("envio da resposta da IA falhou (phone=%s): %s", phone, e)
                last_error = str(e)[:500]
                break
            msg_id = extract_msg_id(send_result)

        saved = await asyncio.to_thread(
            h.save_assistant_message, phone, part, msg_id=msg_id, status="sent")
        try:
            contact_mem = await asyncio.to_thread(h._get_contact, phone)
            await asyncio.to_thread(contact_mem.increment_unread_ai)
        except Exception:  # noqa: BLE001
            pass
        sent += 1
        try:
            broadcast("new_message", {"phone": phone, "message": saved})
        except Exception:  # noqa: BLE001
            pass
        await _emit_sent(phone, part, msg_id, source=source)

    if sent == 0:
        return TurnResult("send_failed", error=last_error)
    return TurnResult("sent", sent=sent)


def legacy_enabled() -> list[str]:
    """Plugins antigos (que este substitui) ainda HABILITADOS neste app.

    Os dois registram a mesma ferramenta de IA e o retorno automático antigo varre os mesmos
    contatos que o novo. Habilitados juntos, o retorno automático novo se pausa (ver
    ``events.py``) para não postar nota/resposta em dobro. Só consulta o banco."""
    try:
        from db.repositories import plugin_repo
        return [pid for pid in LEGACY_IDS if (plugin_repo.get(pid) or {}).get("enabled")]
    except Exception:  # noqa: BLE001
        return []


def notify_changed(item_id: Any = 0, status: str = "") -> None:
    """Avisa o painel (lista de agendamentos) que algo mudou. Nunca levanta."""
    try:
        broadcast("agendamento_e_retorno_changed", {"id": item_id, "status": status})
    except Exception:  # noqa: BLE001
        pass
