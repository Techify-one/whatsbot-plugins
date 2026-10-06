"""Dois filtros do plugin.

1. ``filter.message.outgoing`` — descarta o ECO das mensagens que ESTE plugin acabou de
   mandar pelo GOWA. O core usa ``state.recently_sent`` para reconhecer o próprio envio quando
   ele volta pelo webhook (``is_from_me=True``); esse dicionário não é exposto a plugins, então
   ``common`` mantém uma cópia e este filtro a consome antes de virar uma bolha "Manual"
   duplicada no painel.

2. ``filter.llm.messages`` — esconde da IA os avisos INTERNOS do plugin. O core entrega toda
   ``private_note`` ao modelo como ``[Nota privada do operador]: ...``. O lembrete do atendente
   ("o retorno do cliente chegou") e a nota de fallback ("a IA não foi disparada porque...")
   são recados para humanos: se o modelo os lê, passa a falar deles ao cliente. A nota com a
   INSTRUÇÃO do retorno (e a nota do retorno automático) são o veículo que leva a ordem até o
   modelo e continuam passando.
"""

from __future__ import annotations

from . import common, logic

_NOTE_PREFIX = "[Nota privada do operador]: "
_HIDDEN = tuple(_NOTE_PREFIX + m for m in (logic.RETURN_NOTE_MARKER, logic.IA_FALLBACK_MARKER))


def drop_own_echo(ctx, value):
    if not isinstance(value, dict):
        return value
    if common.consume_recent_echo(value.get("phone") or "", value.get("text") or ""):
        return None
    return value


def hide_internal_notes(ctx, messages):
    if not isinstance(messages, list):
        return messages
    return [
        m for m in messages
        if not (isinstance(m, dict) and isinstance(m.get("content"), str)
                and m["content"].startswith(_HIDDEN))
    ]


FILTERS = {
    "filter.message.outgoing": drop_own_echo,
    "filter.llm.messages": hide_internal_notes,
}
