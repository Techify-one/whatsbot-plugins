"""Verificador único — um laço por minuto para os DOIS recursos.

O whatsbot "simples" não tem tarefa supervisionada de plugin (isso é do whatsbot-pro): o
único jeito de rodar algo periódico é assinar ``app.startup``/``app.shutdown`` e gerenciar o
próprio ``asyncio.Task`` — mesmo padrão do ``monitor_conexao``. Antes eram DOIS laços (um por
plugin); agora é um só, e a ordem do ciclo faz o encaixe entre os recursos:

  1. dispara/expira os retornos AGENDADOS que venceram;
  2. depois, o retorno automático — pulando quem ainda tem retorno agendado.
"""

from __future__ import annotations

import asyncio
import logging

from plugins.context import broadcast

from . import auto, common, logic

logger = logging.getLogger("plugin.agendamento_e_retorno")

CHECK_INTERVAL_SECONDS = 60.0

# Task de polling. Módulo-level para app.startup criar e app.shutdown cancelar.
_task: "asyncio.Task | None" = None
_warned_legacy = False


async def _one_cycle() -> dict:
    global _warned_legacy

    cfg = await asyncio.to_thread(common.load_settings)
    common.prune_recently_sent()

    scheduled = await logic.run_due_cycle(cfg)

    auto_summary = None
    paused = False
    if cfg.auto_enabled:
        legacy = await asyncio.to_thread(common.legacy_enabled)
        if "retorno_automatico" in legacy:
            # O plugin antigo varre os mesmos contatos e posta notas com o mesmo marcador:
            # rodar os dois duplicaria a nota e a resposta da IA. Este se pausa.
            paused = True
            if not _warned_legacy:
                _warned_legacy = True
                logger.warning(
                    "retorno automático PAUSADO: o plugin antigo 'retorno_automatico' ainda está "
                    "habilitado. Desabilite-o em Gerenciar Plugins para este assumir.")
        else:
            busy = await asyncio.to_thread(logic.phones_with_active_items)
            auto_summary = await auto.run_cycle(cfg, busy)

    summary = {"scheduled": scheduled, "auto": auto_summary, "auto_paused": paused}
    try:
        broadcast("agendamento_e_retorno_tick", {"checked_at": common.now(), "auto_paused": paused})
    except Exception:  # noqa: BLE001 — broadcast ruim nunca mata o laço
        pass
    return summary


async def _checker_loop() -> None:
    logger.info("agendamento_e_retorno: verificador iniciado")
    try:
        while True:
            try:
                summary = await _one_cycle()
                s, a = summary["scheduled"], summary["auto"] or {}
                if s.get("sent") or s.get("expired") or s.get("failed") or a.get("fired") or a.get("failed"):
                    logger.info("[AgendamentoERetorno] ciclo: %s", summary)
            except Exception as e:  # noqa: BLE001 — um ciclo com erro não derruba o laço
                logger.warning("[AgendamentoERetorno] ciclo falhou: %s", e)
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("agendamento_e_retorno: verificador cancelado")
        raise


async def _on_startup(ctx, payload) -> None:
    global _task
    common.set_handler(ctx.handler)
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_checker_loop())


async def _on_shutdown(ctx, payload) -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    _task = None


EVENT_HANDLERS = {
    "app.startup": _on_startup,
    "app.shutdown": _on_shutdown,
}
