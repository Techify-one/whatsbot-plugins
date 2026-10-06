"""As duas tools do retorno agendado pela própria IA.

Registradas no mesmo registry das tools core (``entry.tools``), então aparecem em
Configurações de IA → Tools. O Lite tem UM agente por instalação, então não há como
"esconder" a tool por perfil: as travas reais são exigir ``ai_enabled`` no contato, a
antecedência mínima, o horizonte máximo, o limite de retornos seguidos sem resposta do
cliente, a recusa durante um turno proativo e o kill-switch ``retorno_ia_enabled``.

Os NOMES (``agendar_retorno_ia``/``cancelar_retorno_ia``) são os mesmos do plugin antigo
``agendamento_retorno`` de propósito: overrides já feitos em Tools continuam valendo.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from . import common, logic

logger = logging.getLogger("plugin.agendamento_e_retorno")

# O primeiro formato é o que a description pede ao modelo; os demais são a tolerância
# barata para o que ele escreve na prática.
_FORMATOS = ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d/%m/%Y %H", "%d/%m %H:%M", "%Y-%m-%d %H:%M")

FORA_DO_TURNO = ("Você já está executando um retorno agora. Não agende outro agora — "
                 "responda ao cliente e siga a conversa.")


def _parse_due(raw) -> tuple[float | None, str]:
    """``'DD/MM/AAAA HH:MM'`` em BRT → epoch. Devolve ``(epoch, erro_para_o_modelo)``.

    O ``tzinfo`` explícito é obrigatório: ``strptime(...).timestamp()`` sobre um datetime
    ingênuo usaria a TZ do PROCESSO (UTC em container) e agendaria 3 horas errado, sem
    sintoma — enquanto o bloco "Data e hora atual" que o modelo leu está em -03:00 fixo."""
    texto = str(raw or "").strip().replace(" às ", " ").replace(" as ", " ").replace("T", " ").strip()
    for fmt in _FORMATOS:
        try:
            dt = datetime.strptime(texto, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt and "%y" not in fmt:  # "DD/MM HH:MM" → assume o ano corrente
            dt = dt.replace(year=datetime.now(common.BRT).year)
        return dt.replace(tzinfo=common.BRT).timestamp(), ""
    return None, ("Não entendi a data. Informe no formato DD/MM/AAAA HH:MM, calculando a "
                  "partir do bloco 'Data e hora atual' do seu contexto.")


AGENDAR_TOOL = {
    "type": "function",
    "display_label": "Retorno · Agendar meu próprio retorno",
    "function": {
        "name": "agendar_retorno_ia",
        "description": (
            "Agenda um RETORNO SEU: na data e hora marcadas você será acionada automaticamente "
            "e enviará uma mensagem a este cliente, sem que ninguém precise pedir de novo. Use "
            "quando o cliente pedir para ser chamado depois ('me chama amanhã às 9', 'me lembra "
            "na segunda', 'volta a falar comigo em 2 horas') ou quando você mesma prometer voltar "
            "a falar em um horário. COMO CALCULAR A DATA: use SEMPRE o bloco '--- Data e hora "
            "atual ---' do seu contexto como referência de 'agora'. 'amanhã' é a data de hoje "
            "mais um dia, 'daqui a 2 horas' é a hora atual mais duas. Nunca invente uma data e "
            "nunca use uma data que já passou. Existe no máximo UM retorno seu ativo por "
            "conversa: agendar de novo SUBSTITUI o anterior. NÃO use esta ferramenta para "
            "lembretes do operador nem para tarefas internas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "data_hora": {
                    "type": "string",
                    "description": ("Quando você deve voltar a falar, no formato DD/MM/AAAA HH:MM "
                                    "em 24 horas, no mesmo fuso do bloco 'Data e hora atual'. "
                                    "Exemplo: 22/08/2026 09:00."),
                },
                "briefing": {
                    "type": "string",
                    "description": ("Instrução para VOCÊ MESMA no vencimento, completa o bastante "
                                    "para agir sem reler a conversa. Exemplo: 'Retome a proposta "
                                    "do plano anual: pergunte se ele conseguiu falar com o sócio "
                                    "e ofereça fechar hoje.'"),
                },
            },
            "required": ["data_hora", "briefing"],
        },
    },
}

CANCELAR_TOOL = {
    "type": "function",
    "display_label": "Retorno · Cancelar meu retorno",
    "function": {
        "name": "cancelar_retorno_ia",
        "description": (
            "Cancela o retorno que VOCÊ havia agendado com este cliente. Use quando o cliente "
            "disser que não precisa mais ('pode deixar', 'já resolvi', 'não precisa me chamar') "
            "ou quando o assunto do retorno já tiver sido tratado agora. Não cancela agendamentos "
            "feitos manualmente pelo operador."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string",
                           "description": "Uma frase curta explicando por que não é mais preciso."},
            },
            "required": [],
        },
    },
}


def execute_agendar(ctx, args: dict) -> str:
    """Devolve SEMPRE uma string acionável: ela vira a tool message que o modelo lê. Erro de
    domínio é resposta, não exceção."""
    args = args or {}
    cfg = common.load_settings()
    if not cfg.retorno_ia_enabled:
        return ("O agendamento de retorno automático está desativado nesta instalação. "
                "Combine o retorno com o cliente sem usar esta ferramenta.")
    if common.in_proactive_turn():
        return FORA_DO_TURNO

    contact = ctx.contact
    phone = contact.phone
    if not getattr(contact, "ai_enabled", True):
        return "A IA está desligada para este contato — não é possível agendar."

    due_at, err = _parse_due(args.get("data_hora"))
    if err:
        return err
    briefing = str(args.get("briefing") or "").strip()
    if not briefing:
        return ("Escreva também o 'briefing' — a instrução que você mesma vai seguir quando o "
                "retorno vencer.")

    ts = time.time()
    lead = max(60, int(cfg.retorno_ia_min_lead_minutes) * 60)
    if due_at < ts + lead:
        return f"Essa data já passou ou é cedo demais. Agende para pelo menos {lead // 60} minutos a partir de agora."
    horizonte = max(86400, int(cfg.retorno_ia_max_horizon_days) * 86400)
    if due_at > ts + horizonte:
        return f"Não consigo agendar tão longe. O limite é {horizonte // 86400} dias a partir de hoje."

    try:
        depth = logic.chain_depth_for(phone)
    except Exception as e:  # noqa: BLE001 — contagem indisponível não bloqueia
        logger.debug("chain_depth falhou: %s", e)
        depth = 0
    if depth >= max(1, int(cfg.retorno_ia_max_chain)):
        return ("Você já tentou retomar esta conversa várias vezes e o cliente não respondeu "
                "nenhuma. Não vou agendar outro retorno — encerre de forma cordial e deixe a "
                "conversa aberta para quando ele voltar.")

    info = getattr(contact, "info", {}) or {}
    item, err = logic.create_ia_item(
        contact={"id": contact.id, "phone": phone,
                 "name": info.get("name") or getattr(contact, "group_name", "") or ""},
        due_at=due_at, briefing=briefing, chain_depth=depth)
    if err:
        return f"Não consegui agendar o retorno: {err}"

    quando = datetime.fromtimestamp(due_at, common.BRT).strftime("%d/%m/%Y às %H:%M")
    extra = " (substituí o retorno que já estava marcado)" if item.get("_replaced") else ""
    return (f"Retorno agendado para {quando}{extra}. Confirme ao cliente que você volta a falar "
            f"nesse horário e NÃO chame esta ferramenta de novo nesta conversa.")


def execute_cancelar(ctx, args: dict) -> str:
    motivo = str((args or {}).get("motivo") or "").strip()
    try:
        n = logic.cancel_active_ia_items(ctx.contact.phone, motivo=motivo)
    except Exception as e:  # noqa: BLE001
        logger.warning("cancelamento falhou: %s", e)
        return "Não consegui cancelar o retorno agora."
    if not n:
        return "Não havia nenhum retorno seu agendado com este cliente."
    return "Retorno cancelado. Avise o cliente que você não voltará a chamá-lo."


CORE_TOOLS = [
    (AGENDAR_TOOL, execute_agendar),
    (CANCELAR_TOOL, execute_cancelar),
]
