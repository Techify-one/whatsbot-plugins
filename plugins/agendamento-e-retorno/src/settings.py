"""Settings declarativas do plugin Agendamento e Retorno.

Um único modelo com dois grupos de campos, marcados em ``json_schema_extra``:

  * ``"agendamento"`` — agendamentos de retorno (manuais e os que a própria IA marca);
  * ``"auto"``        — retorno automático (cliente em silêncio).

A tela de configuração (``static/config.js``) lê esse ``group`` do JSON Schema para
montar as duas abas do modal "Configurar". Tudo persiste em ``config`` com o prefixo
``plugin.agendamento_e_retorno.<campo>`` — os campos do retorno automático levam o
prefixo ``auto_`` para não colidir com os do agendamento.
"""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

AGENDAMENTO = {"group": "agendamento"}
AUTO = {"group": "auto"}
AUTO_DIA = {"group": "auto", "widget": "weekday"}


class Settings(BaseModel):
    # ── Aba "Agendamento" ────────────────────────────────────────────────────
    tolerance_minutes: int = Field(
        default=60, ge=0,
        title="Janela de tolerância (minutos)",
        description=(
            "Agendamentos vencidos há MENOS deste tempo ainda são disparados quando o "
            "verificador voltar de um período parado; os mais antigos são marcados como "
            "Expirado (não disparam). 0 = nunca disparar atrasado."
        ),
        json_schema_extra=AGENDAMENTO,
    )
    retorno_ia_enabled: bool = Field(
        default=True,
        title="Permitir que a IA agende o próprio retorno",
        description=(
            "Libera as ferramentas de IA “agendar_retorno_ia” e “cancelar_retorno_ia”. "
            "Desmarcado, a ferramenta recusa com uma frase que o modelo entende e a conversa "
            "segue normal — nenhum agendamento novo é criado."
        ),
        json_schema_extra=AGENDAMENTO,
    )
    retorno_ia_min_lead_minutes: int = Field(
        default=5, ge=1, le=1440,
        title="Antecedência mínima do retorno da IA (minutos)",
        description="A IA não consegue agendar um retorno mais perto do que isto.",
        json_schema_extra=AGENDAMENTO,
    )
    retorno_ia_max_horizon_days: int = Field(
        default=30, ge=1, le=365,
        title="Horizonte máximo do retorno da IA (dias)",
        description="A IA não consegue agendar um retorno mais longe do que isto.",
        json_schema_extra=AGENDAMENTO,
    )
    retorno_ia_max_chain: int = Field(
        default=3, ge=1, le=10,
        title="Retornos seguidos sem resposta do cliente",
        description=(
            "Depois deste número de retornos da IA sem NENHUMA mensagem do cliente entre eles, "
            "a ferramenta recusa novos agendamentos. Uma resposta do cliente zera a contagem."
        ),
        json_schema_extra=AGENDAMENTO,
    )

    # ── Aba "Retorno automático" ─────────────────────────────────────────────
    auto_enabled: bool = Field(
        default=True,
        title="Ativar retorno automático",
        description="Interruptor mestre do plugin. Desligado, o verificador não posta nenhuma nota.",
        json_schema_extra=AUTO,
    )
    auto_silence_minutes: int = Field(
        default=180, ge=1, le=10080,
        title="Silêncio do cliente antes da nota (minutos)",
        description=(
            "Minutos que o cliente pode ficar sem responder (contado a partir da última resposta "
            "da IA/operador ou da última nota) antes de uma nova nota ser postada. Contatos com "
            "um retorno agendado ativo são pulados. Ex.: 180 = 3 horas, 30 = meia hora, "
            "1 = teste rápido."
        ),
        json_schema_extra=AUTO,
    )
    auto_max_consecutive_notes: int = Field(
        default=3, ge=1, le=20,
        title="Máximo de notas consecutivas",
        description=(
            "Quantas notas podem ser postadas sem o cliente responder. Ao atingir o limite, o "
            "plugin entra em standby para esse contato até o cliente responder (reset)."
        ),
        json_schema_extra=AUTO,
    )
    auto_business_start: str = Field(
        default="08:00",
        title="Início do expediente (HH:MM)",
        description="Notas só são postadas dentro do expediente. Formato 24h, ex.: 08:00.",
        json_schema_extra=AUTO,
    )
    auto_business_end: str = Field(
        default="18:00",
        title="Fim do expediente (HH:MM)",
        description="Limite superior EXCLUSIVO do expediente. Formato 24h, ex.: 18:00.",
        json_schema_extra=AUTO,
    )
    auto_day_mon: bool = Field(default=True, title="Segunda-feira", json_schema_extra=AUTO_DIA)
    auto_day_tue: bool = Field(default=True, title="Terça-feira", json_schema_extra=AUTO_DIA)
    auto_day_wed: bool = Field(default=True, title="Quarta-feira", json_schema_extra=AUTO_DIA)
    auto_day_thu: bool = Field(default=True, title="Quinta-feira", json_schema_extra=AUTO_DIA)
    auto_day_fri: bool = Field(default=True, title="Sexta-feira", json_schema_extra=AUTO_DIA)
    auto_day_sat: bool = Field(default=False, title="Sábado", json_schema_extra=AUTO_DIA)
    auto_day_sun: bool = Field(default=False, title="Domingo", json_schema_extra=AUTO_DIA)
    auto_tz_offset_hours: float = Field(
        default=-3.0, ge=-12.0, le=14.0,
        title="Fuso horário (horas UTC)",
        description="Deslocamento fixo em relação ao UTC (Brasil = −3). Sem horário de verão.",
        json_schema_extra=AUTO,
    )
    auto_apply_to_groups: bool = Field(
        default=False,
        title="Aplicar a grupos",
        description="Se desligado (padrão), grupos são ignorados — só contatos individuais.",
        json_schema_extra=AUTO,
    )
    auto_ai_reply: bool = Field(
        default=True,
        title="IA responde automaticamente no chat",
        description=(
            "Além de postar a nota privada, aciona a IA para ler essa nota e responder DE VERDADE "
            "ao cliente no chat — igual ao toggle \"IA lê\" + \"IA responde no chat\" da Mensagem "
            "Privada manual. Desligado, o plugin só posta a nota e cabe ao operador retomar a "
            "conversa. Uma falha nessa etapa (ex.: IA desligada durante o turno) nunca impede a "
            "nota de ser postada."
        ),
        json_schema_extra=AUTO,
    )
    auto_note_template: str = Field(
        default=(
            "O cliente {cliente} está sem responder há {tempo}. "
            "Reative a IA para dar seguimento. (Tentativa {tentativa}/{max})"
        ),
        title="Modelo da nota",
        description=(
            "Texto da nota privada (o prefixo \"🔔 Retorno Automático: \" é adicionado "
            "automaticamente antes deste texto — é assim que o plugin reconhece as próprias notas "
            "depois de um restart, e não precisa ser digitado aqui). Placeholders: {cliente}, "
            "{tempo} (ex.: 3h / 30min), {minutos}, {horas}, {tentativa}, {max}. Um placeholder "
            "desconhecido é mantido literal (não quebra o disparo)."
        ),
        json_schema_extra=AUTO,
    )

    @field_validator("auto_business_start", "auto_business_end")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        value = (value or "").strip()
        m = _HHMM.match(value)
        if not m:
            raise ValueError("use o formato HH:MM (24h), ex.: 08:00")
        return f"{int(m.group(1)):02d}:{m.group(2)}"

    @model_validator(mode="after")
    def _expediente_coerente(self):
        if self.auto_business_start >= self.auto_business_end:
            raise ValueError("o início do expediente deve ser antes do fim")
        return self
