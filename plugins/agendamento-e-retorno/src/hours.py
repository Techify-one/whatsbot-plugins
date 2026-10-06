"""Expediente do retorno automático — funções PURAS e testáveis (sem DB, sem estado).

Não há cálculo de "próxima janela": o disparo é GATED por :func:`is_open_now`; o loop por
minuto dispara sozinho no 1º tick dentro do expediente. O fuso é um offset FIXO (padrão −3,
Brasil sem DST) — evita ``datetime.now()`` ingênuo, que usaria a TZ do processo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("plugin.agendamento_e_retorno")

# weekday() → 0=segunda … 6=domingo; casa com a ordem dos toggles de Settings.
_DAY_FIELDS = ("auto_day_mon", "auto_day_tue", "auto_day_wed", "auto_day_thu",
               "auto_day_fri", "auto_day_sat", "auto_day_sun")


def parse_hhmm(value: str | None) -> int | None:
    """"HH:MM" → minutos desde a meia-noite (0..1439), ou ``None`` se inválido."""
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh * 60 + mm


def is_open_now(now_epoch: float, cfg: Any) -> bool:
    """Estamos DENTRO do expediente no instante ``now_epoch``?

    ``cfg`` é o ``Settings`` do plugin. Devolve ``False`` de forma defensiva se a config
    estiver malformada (nunca levanta — o pior caso é "não dispara agora").
    """
    try:
        tz = float(getattr(cfg, "auto_tz_offset_hours", -3.0) or 0.0)
        local = datetime.fromtimestamp(now_epoch + tz * 3600, timezone.utc)

        if not bool(getattr(cfg, _DAY_FIELDS[local.weekday()], False)):
            return False

        start = parse_hhmm(getattr(cfg, "auto_business_start", "08:00"))
        end = parse_hhmm(getattr(cfg, "auto_business_end", "18:00"))
        if start is None or end is None or start >= end:
            logger.warning("expediente inválido (start=%r end=%r) — tratando como fechado",
                           getattr(cfg, "auto_business_start", None),
                           getattr(cfg, "auto_business_end", None))
            return False

        minute = local.hour * 60 + local.minute
        return start <= minute < end
    except Exception:  # noqa: BLE001 — expediente nunca derruba o ciclo
        logger.exception("is_open_now falhou — tratando como fechado")
        return False
