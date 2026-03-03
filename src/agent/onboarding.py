"""
Onboarding — fluxo conversacional campo-a-campo (v9).

Arquitetura:
  O agente Python é a CAMADA CONVERSACIONAL.
  O BFA (Go) é a CAMADA DE NEGÓCIO.

  Responsabilidades do agente:
    - Detectar intenção de abertura de conta
    - Determinar o step atual com base no history enriquecido
    - Validar formato básico dos campos (guard rail inline)
    - Gerar respostas determinísticas (templates, sem LLM)
    - Devolver step + valor cru + next_step na resposta

  Responsabilidades do BFA (Go):
    - Validar regras de negócio (CNPJ único, dígito verificador, 18+)
    - Persistir dados
    - Retornar validated=True/False no history
    - Controlar o fluxo de sessão

Contrato do history (BFA → Agente):
  Cada turno no history tem 4 campos:
    - query:     O que o cliente digitou
    - answer:    O que o agente respondeu
    - step:      Qual step aquele turno representava (ex: "cnpj")
    - validated: Se o BFA validou aquele campo (True/False/None)

  Com step+validated, o agente não precisa "adivinhar" onde parou.
  Ele lê o último turno validado e sabe exatamente o próximo step.

Limite de retries:
  Se o cliente erra o mesmo campo mais de MAX_RETRIES vezes,
  o agente encerra o onboarding com mensagem amigável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from src.observability.logging import get_logger

logger = get_logger("onboarding")


# Máximo de tentativas por campo antes de desistir.
# O cliente terá MAX_RETRIES tentativas reais antes de ser bloqueado.
# Ex: MAX_RETRIES=3 → 3 tentativas (1ª + 2 retries) no inline path,
#     ou 3 rejeições do BFA + 4ª tentativa bloqueada no BFA path.
MAX_RETRIES = 3


# =============================================================================
# Definição dos campos do onboarding (sequência fixa)
# =============================================================================

class OnboardingField(str, Enum):
    """Campos do onboarding na ordem em que serão pedidos."""
    WELCOME = "welcome"
    CNPJ = "cnpj"
    RAZAO_SOCIAL = "razaoSocial"
    NOME_FANTASIA = "nomeFantasia"
    EMAIL = "email"
    REPRESENTANTE_NAME = "representanteName"
    REPRESENTANTE_CPF = "representanteCpf"
    REPRESENTANTE_PHONE = "representantePhone"
    REPRESENTANTE_BIRTH_DATE = "representanteBirthDate"
    PASSWORD = "password"
    PASSWORD_CONFIRMATION = "passwordConfirmation"
    COMPLETED = "completed"


# Sequência ordenada
FIELD_SEQUENCE: list[OnboardingField] = [
    OnboardingField.WELCOME,
    OnboardingField.CNPJ,
    OnboardingField.RAZAO_SOCIAL,
    OnboardingField.NOME_FANTASIA,
    OnboardingField.EMAIL,
    OnboardingField.REPRESENTANTE_NAME,
    OnboardingField.REPRESENTANTE_CPF,
    OnboardingField.REPRESENTANTE_PHONE,
    OnboardingField.REPRESENTANTE_BIRTH_DATE,
    OnboardingField.PASSWORD,
    OnboardingField.PASSWORD_CONFIRMATION,
    OnboardingField.COMPLETED,
]

# Apenas campos de dados (sem welcome e completed)
DATA_FIELDS: list[OnboardingField] = [
    f for f in FIELD_SEQUENCE
    if f not in (OnboardingField.WELCOME, OnboardingField.COMPLETED)
]

# Mensagens template
FIELD_PROMPTS: dict[OnboardingField, str] = {
    OnboardingField.WELCOME: (
        "Que ótimo que quer abrir sua conta PJ! 😊\n"
        "Vou te guiar passo a passo. São dados simples e leva poucos minutos.\n\n"
        "Para começar, me informe o **CNPJ** da empresa.\n"
        "Formato: XX.XXX.XXX/XXXX-XX"
    ),
    OnboardingField.CNPJ: (
        "Me informe o **CNPJ** da empresa.\n"
        "Formato: XX.XXX.XXX/XXXX-XX"
    ),
    OnboardingField.RAZAO_SOCIAL: (
        "CNPJ recebido! ✅\n\n"
        "Agora me diga a **Razão Social** da empresa (nome oficial no contrato social)."
    ),
    OnboardingField.NOME_FANTASIA: (
        "Razão Social recebida! ✅\n\n"
        "Qual o **Nome Fantasia** da empresa? (nome comercial, como os clientes conhecem)"
    ),
    OnboardingField.EMAIL: (
        "Nome Fantasia recebido! ✅\n\n"
        "Informe o **e-mail** corporativo para contato.\n"
        "Exemplo: contato@suaempresa.com.br"
    ),
    OnboardingField.REPRESENTANTE_NAME: (
        "E-mail recebido! ✅ Dados da empresa completos!\n\n"
        "Agora preciso dos dados do **representante legal**.\n"
        "Qual o **nome completo** do representante?"
    ),
    OnboardingField.REPRESENTANTE_CPF: (
        "Nome recebido! ✅\n\n"
        "Informe o **CPF** do representante.\n"
        "Formato: XXX.XXX.XXX-XX"
    ),
    OnboardingField.REPRESENTANTE_PHONE: (
        "CPF recebido! ✅\n\n"
        "Qual o **telefone** do representante?\n"
        "Formato: (XX) XXXXX-XXXX"
    ),
    OnboardingField.REPRESENTANTE_BIRTH_DATE: (
        "Telefone recebido! ✅\n\n"
        "Qual a **data de nascimento** do representante?\n"
        "Formato: DD/MM/AAAA"
    ),
    OnboardingField.PASSWORD: (
        "Data de nascimento recebida! ✅ Dados do representante completos!\n\n"
        "Quase lá! 🔒\n"
        "Crie uma **senha numérica de 6 dígitos** para acesso à conta."
    ),
    OnboardingField.PASSWORD_CONFIRMATION: (
        "Senha recebida! ✅\n\n"
        "Por segurança, **digite a senha novamente** para confirmar."
    ),
}

FIELD_LABELS: dict[OnboardingField, str] = {
    OnboardingField.CNPJ: "CNPJ",
    OnboardingField.RAZAO_SOCIAL: "Razão Social",
    OnboardingField.NOME_FANTASIA: "Nome Fantasia",
    OnboardingField.EMAIL: "E-mail",
    OnboardingField.REPRESENTANTE_NAME: "Nome completo do representante",
    OnboardingField.REPRESENTANTE_CPF: "CPF do representante",
    OnboardingField.REPRESENTANTE_PHONE: "Telefone",
    OnboardingField.REPRESENTANTE_BIRTH_DATE: "Data de nascimento",
}

FIELD_FORMAT_HINTS: dict[OnboardingField, str] = {
    OnboardingField.CNPJ: "Formato: XX.XXX.XXX/XXXX-XX (14 dígitos)",
    OnboardingField.RAZAO_SOCIAL: "Mínimo 3 caracteres",
    OnboardingField.NOME_FANTASIA: "Mínimo 2 caracteres",
    OnboardingField.EMAIL: "Exemplo: contato@empresa.com",
    OnboardingField.REPRESENTANTE_NAME: "Nome completo (mínimo 5 caracteres)",
    OnboardingField.REPRESENTANTE_CPF: "Formato: XXX.XXX.XXX-XX (11 dígitos)",
    OnboardingField.REPRESENTANTE_PHONE: "Formato: (XX) XXXXX-XXXX",
    OnboardingField.REPRESENTANTE_BIRTH_DATE: "Formato: DD/MM/AAAA",
    OnboardingField.PASSWORD: "Exatamente 6 dígitos numéricos",
    OnboardingField.PASSWORD_CONFIRMATION: "Mesma senha de 6 dígitos",
}


# =============================================================================
# Validação de formato inline (guard rail)
# =============================================================================

def _only_digits(value: str) -> str:
    """Extrai apenas dígitos de uma string."""
    return re.sub(r"\D", "", value)


def validate_field_format(field_enum: OnboardingField, value: str) -> str | None:
    """
    Valida o formato básico de um campo.

    Returns:
        None se válido, mensagem de erro se inválido.
    """
    value = value.strip()

    if field_enum == OnboardingField.CNPJ:
        digits = _only_digits(value)
        if len(digits) != 14:
            return (
                f"O CNPJ deve conter **14 dígitos** numéricos, "
                f"mas você informou {len(digits)} dígito(s).\n"
                f"Exemplo: 12.345.678/0001-90"
            )

    elif field_enum == OnboardingField.RAZAO_SOCIAL:
        if len(value) < 3:
            return "A Razão Social deve ter no mínimo **3 caracteres**. Tente novamente."

    elif field_enum == OnboardingField.NOME_FANTASIA:
        if len(value) < 2:
            return "O Nome Fantasia deve ter no mínimo **2 caracteres**. Tente novamente."

    elif field_enum == OnboardingField.EMAIL:
        if "@" not in value or "." not in value.split("@")[-1]:
            return (
                "O e-mail informado parece inválido — precisa ter **@** e um domínio.\n"
                "Exemplo: contato@suaempresa.com.br"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_NAME:
        if len(value) < 5:
            return (
                "O nome do representante deve ter no mínimo **5 caracteres**.\n"
                "Informe o nome completo (nome e sobrenome)."
            )

    elif field_enum == OnboardingField.REPRESENTANTE_CPF:
        digits = _only_digits(value)
        if len(digits) != 11:
            return (
                f"O CPF deve conter **11 dígitos** numéricos, "
                f"mas você informou {len(digits)} dígito(s).\n"
                f"Exemplo: 123.456.789-00"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_PHONE:
        digits = _only_digits(value)
        if len(digits) < 10:
            return (
                f"O telefone deve conter no mínimo **10 dígitos** (DDD + número), "
                f"mas você informou {len(digits)} dígito(s).\n"
                f"Exemplo: (11) 98765-4321"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_BIRTH_DATE:
        date_pattern = r"^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$"
        if not re.match(date_pattern, value):
            return (
                "A data de nascimento precisa estar no formato **DD/MM/AAAA**.\n"
                "Exemplo: 15/03/1990"
            )

    elif field_enum == OnboardingField.PASSWORD:
        if not re.match(r"^\d{6}$", value):
            if len(value) != 6:
                return (
                    f"A senha deve ter exatamente **6 dígitos**, "
                    f"mas você informou {len(value)} caractere(s)."
                )
            return (
                "A senha deve conter **apenas números** (6 dígitos).\n"
                "Sem letras ou caracteres especiais."
            )

    elif field_enum == OnboardingField.PASSWORD_CONFIRMATION:
        if not re.match(r"^\d{6}$", value):
            return (
                "A confirmação deve ter exatamente **6 dígitos numéricos**, "
                "igual à senha que você criou."
            )

    return None


# =============================================================================
# State Machine
# =============================================================================

@dataclass
class OnboardingState:
    """Estado do onboarding derivado do history enriquecido."""
    step: OnboardingField               # step que o cliente ACABOU de responder
    next_step: OnboardingField          # step que o agente vai PEDIR agora
    collected: dict[str, str] = field(default_factory=dict)
    is_complete: bool = False
    has_validation_error: bool = False
    validation_error: str = ""
    validation_error_source: str = ""   # "bfa" se veio do BFA, "inline" se validação local
    field_value: str = ""               # valor cru que o cliente enviou
    retry_count: int = 0                # quantas vezes errou o step atual
    max_retries_exceeded: bool = False   # se excedeu o limite de retries
    is_restart: bool = False             # se o cliente pediu para recomeçar


def _get_next_field(current: OnboardingField) -> OnboardingField:
    """Retorna o próximo campo na sequência após 'current'."""
    idx = FIELD_SEQUENCE.index(current)
    if idx + 1 < len(FIELD_SEQUENCE):
        return FIELD_SEQUENCE[idx + 1]
    return OnboardingField.COMPLETED


def determine_current_field(
    history: list[dict],
    current_query: str,
    validation_error: str = "",
    collected_data: list[dict] | None = None,
) -> OnboardingState:
    """
    Determina o estado do onboarding com base no history enriquecido.

    O BFA envia cada turno com step + validated. O agente:
      1. Pré-carrega collected_data (campos de sessão anterior, se houver)
      2. Percorre o history para encontrar o último step validado
      3. Determina o próximo step
      4. Valida formato inline da query atual
      5. Conta retries consecutivos no mesmo step

    Args:
        history: Turnos com {query, answer, step, validated}
        current_query: Mensagem atual do cliente
        validation_error: Erro do BFA se rejeitou o último campo
        collected_data: Campos já coletados em sessão anterior (retomada).
                        Lista de dicts com {key, value, validated}.

    Returns:
        OnboardingState completo
    """
    collected: dict[str, str] = {}

    # ─── Pre-seed: campos de sessão anterior (collected_data) ──────
    # O BFA pode enviar campos já validados de uma sessão anterior
    # para que o onboarding retome de onde parou, sem re-coletar.
    if collected_data:
        for item in collected_data:
            key = item.get("key", "")
            value = item.get("value", "")
            validated = item.get("validated", True)
            if key and value and validated:
                # Só aceitar se é um campo válido do onboarding
                try:
                    OnboardingField(key)
                    collected[key] = value
                except ValueError:
                    logger.warning(
                        "⚠️ [ONBOARDING] Unknown field in collected_data — ignoring",
                        key=key,
                    )

        if collected:
            logger.info(
                "📋 [ONBOARDING] PRE-SEEDED from collected_data (session resumption)",
                collected_count=len(collected),
                collected_fields=list(collected.keys()),
            )

    # ─── Sem history → primeira mensagem ou retomada ───────────────
    if not history:
        if collected:
            # Retomada: temos campos pré-carregados, determinar o próximo
            # Percorre apenas campos de dados (sem WELCOME e COMPLETED)
            last_collected_step: OnboardingField | None = None
            for fld in DATA_FIELDS:
                if fld.value in collected:
                    last_collected_step = fld
                else:
                    break

            if last_collected_step:
                next_step = _get_next_field(last_collected_step)
                if next_step == OnboardingField.COMPLETED:
                    return OnboardingState(
                        step=OnboardingField.COMPLETED,
                        next_step=OnboardingField.COMPLETED,
                        collected=collected,
                        is_complete=True,
                        field_value=current_query,
                    )
                # A "step" aqui é o welcome pois é a primeira mensagem,
                # mas o next_step avança para o próximo campo pendente.
                logger.info(
                    "🔄 [ONBOARDING] RESUMING — Retomando de sessão anterior",
                    collected_count=len(collected),
                    next_step=next_step.value,
                )
                return OnboardingState(
                    step=OnboardingField.WELCOME,
                    next_step=next_step,
                    collected=collected,
                    field_value=current_query,
                )

        return OnboardingState(
            step=OnboardingField.WELCOME,
            next_step=OnboardingField.WELCOME,
            field_value=current_query,
        )

    # ─── Restart: cliente pediu para recomeçar ─────────────────────
    # IMPORTANTE: Verificar restart ANTES de qualquer retry/max_retries check.
    # Isso evita que o cliente fique preso em loop quando erra muitas vezes
    # e tenta recomeçar com "abrir conta".
    # O BFA deve limpar a sessão ao receber step=welcome + is_restart=True.
    if _is_restart_request(current_query):
        has_previous_onboarding = any(
            turn.get("step") is not None for turn in history
        )
        if has_previous_onboarding:
            logger.info(
                "🔄 [ONBOARDING] RESTART — Cliente pediu para recomeçar o onboarding",
                query=current_query,
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

    # ─── Detectar max_retries anterior ────────────────────────────
    # Se o último answer no history indica max_retries (contém "após algumas
    # tentativas" ou "não conseguimos validar"), qualquer nova mensagem é
    # tratada como restart — o max_retries JÁ encerrou o fluxo.
    # O cliente que volta a escrever quer continuar.
    #
    # Também detecta se o BFA marcou max_retries_exceeded=True no último turno
    # (caso o BFA tenha adicionado ao history mesmo sem dever).
    if history:
        last_turn = history[-1]
        last_answer = last_turn.get("answer", "")
        max_retries_phrases = [
            "após algumas tentativas",
            "não conseguimos validar",
            "limite de tentativas",
            "recomeçamos",            # new message format
            "é só me enviar",         # new message format
        ]
        is_post_max_retries = any(
            phrase in last_answer.lower() for phrase in max_retries_phrases
        )

        # Fallback: se o BFA adicionou max_retries_exceeded ao turno
        if not is_post_max_retries and last_turn.get("max_retries_exceeded"):
            is_post_max_retries = True

        if is_post_max_retries:
            logger.info(
                "🔄 [ONBOARDING] RESTART (post max_retries) — Reiniciando após max retries",
                query=current_query,
                last_answer_preview=last_answer[:100],
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

    # ─── Percorrer o history para encontrar o estado ───────────────
    # Estratégia: identificar o último step VALIDADO pelo BFA.
    # O próximo step é o seguinte na sequência.
    last_validated_step: OnboardingField | None = None
    last_rejected_step: OnboardingField | None = None
    retry_count = 0

    for turn in history:
        step_str = turn.get("step")
        validated = turn.get("validated")

        if step_str is None:
            # Turno sem step (ex: welcome, saudação) → ignorar
            continue

        # Converter string para enum
        try:
            step_enum = OnboardingField(step_str)
        except ValueError:
            continue

        if validated is True:
            last_validated_step = step_enum
            collected[step_enum.value] = turn["query"]
            retry_count = 0  # resetar contagem ao validar
            last_rejected_step = None  # resetar rejeição
        elif validated is False:
            # Só contar rejeições do step ATUAL (step seguinte ao último validado).
            # Rejeições de steps anteriores já foram resolvidas.
            retry_count += 1
            last_rejected_step = step_enum

    # ─── Determinar o step que o cliente está respondendo AGORA ────
    if last_validated_step is None:
        # Nenhum campo validado ainda → cliente está respondendo CNPJ
        current_step = OnboardingField.CNPJ
    else:
        current_step = _get_next_field(last_validated_step)

    logger.debug(
        "📋 [ONBOARDING] HISTORY_TRAVERSED",
        last_validated_step=last_validated_step.value if last_validated_step else None,
        current_step=current_step.value,
        retry_count_from_history=retry_count,
        collected_count=len(collected),
        current_query_preview=current_query[:30],
    )

    # Se já completou todos os campos
    if current_step == OnboardingField.COMPLETED:
        return OnboardingState(
            step=OnboardingField.COMPLETED,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
            field_value=current_query,
        )

    # ─── Fallback: BFA rejeitou (validated=false) sem validation_error ─
    # Se o último turno do history tem validated=false e o BFA NÃO enviou
    # validation_error (string vazia), gerar uma mensagem genérica
    # contextual ao campo — para que a resposta não pareça "chumbada".
    if not validation_error and last_rejected_step is not None:
        label = FIELD_LABELS.get(current_step, current_step.value)
        validation_error = (
            f"O **{label}** informado não foi aceito pelo sistema. "
            f"Verifique o dado e tente novamente."
        )
        logger.info(
            "⚠️ [ONBOARDING] BFA rejected without error message — using fallback",
            step=current_step.value,
            last_rejected_step=last_rejected_step.value,
            retry_count=retry_count,
        )

    # ─── Verificar limite de retries ───────────────────────────────
    # retry_count já contém todas as tentativas falhadas do history.
    # validation_error indica que o BFA rejeitou a última tentativa —
    # mas essa rejeição já está contada como validated=False no history.
    # NÃO incrementar novamente para evitar double-counting.

    logger.debug(
        "📋 [ONBOARDING] RETRY_CHECK",
        step=current_step.value,
        retry_count=retry_count,
        max_retries=MAX_RETRIES,
        has_validation_error=bool(validation_error),
        has_last_rejected_step=last_rejected_step is not None,
    )

    if retry_count >= MAX_RETRIES:
        # Safety net: se mesmo depois de todos os checks anteriores
        # ainda chegou aqui com um pedido de restart, forçar restart
        # para não prender o cliente em loop infinito.
        if _is_restart_request(current_query):
            logger.info(
                "🔄 [ONBOARDING] RESTART (safety net in max_retries) — Forçando restart",
                step=current_step.value,
                retry_count=retry_count,
                query=current_query,
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

        logger.info(
            "🚫 [ONBOARDING] Max retries exceeded",
            step=current_step.value,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
        )
        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=validation_error or "Limite de tentativas excedido",
            validation_error_source="bfa" if validation_error else "inline",
            field_value=current_query,
            retry_count=retry_count,
            max_retries_exceeded=True,
        )

    # ─── Se o BFA rejeitou → pedir o mesmo campo de novo ──────────
    if validation_error:
        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=validation_error,
            validation_error_source="bfa",
            field_value=current_query,
            retry_count=retry_count,
        )

    # ─── Validação inline de formato (guard rail) ──────────────────
    format_error = validate_field_format(current_step, current_query)
    if format_error:
        retry_count += 1

        logger.info(
            "⚠️ [ONBOARDING] Inline validation failed",
            step=current_step.value,
            value_preview=current_query[:20],
            error_preview=format_error[:80],
            retry_count_after_increment=retry_count,
            max_retries=MAX_RETRIES,
            will_exceed_max=retry_count >= MAX_RETRIES,
        )

        if retry_count >= MAX_RETRIES:
            return OnboardingState(
                step=current_step,
                next_step=current_step,
                collected=collected,
                has_validation_error=True,
                validation_error=format_error,
                validation_error_source="inline",
                field_value=current_query,
                retry_count=retry_count,
                max_retries_exceeded=True,
            )

        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=format_error,
            validation_error_source="inline",
            field_value=current_query,
            retry_count=retry_count,
        )

    # ─── Formato válido → avançar ──────────────────────────────────
    collected[current_step.value] = current_query
    next_step = _get_next_field(current_step)

    is_complete = next_step == OnboardingField.COMPLETED

    logger.info(
        "📋 [ONBOARDING] State determined",
        step=current_step.value,
        next_step=next_step.value,
        collected_count=len(collected),
        is_complete=is_complete,
    )

    return OnboardingState(
        step=current_step,
        next_step=next_step,
        collected=collected,
        is_complete=is_complete,
        field_value=current_query,
    )


# =============================================================================
# Gerador de resposta determinística (sem LLM)
# =============================================================================

def build_onboarding_response(state: OnboardingState) -> str:
    """
    Gera a resposta FINAL para o cliente — determinística, sem LLM.

    Returns:
        String com a resposta pronta para o cliente.
    """
    # ─── Max retries excedido → encerrar com mensagem amigável ─────
    if state.max_retries_exceeded:
        label = FIELD_LABELS.get(state.step, state.step.value)
        return (
            f"Não conseguimos validar o **{label}** após {MAX_RETRIES} tentativas. 😕\n\n"
            "Mas sem problemas! Quando estiver com os dados corretos em mãos, "
            "é só me enviar qualquer mensagem e recomeçamos. 😊"
        )

    # ─── Restart → recomeçar com welcome ───────────────────────────
    if state.is_restart:
        return FIELD_PROMPTS[OnboardingField.WELCOME]

    # ─── Onboarding completo ──────────────────────────────────────
    if state.is_complete:
        lines = ["Parabéns! 🎉 Sua conta PJ foi aberta com sucesso!\n"]
        lines.append("Aqui está o resumo do cadastro:\n")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- **{label}**: {value}")
        lines.append(
            "\nSeu cadastro será processado e em breve sua conta "
            "PJ estará pronta! 🚀\n\n"
            "Se precisar de mais alguma coisa, é só avisar! 😊"
        )
        return "\n".join(lines)

    # ─── Retomada de sessão (welcome com collected_data) ───────────
    # Se step é welcome, tem campos coletados, e o next_step NÃO é welcome,
    # significa que estamos retomando de uma sessão anterior.
    if (
        state.step == OnboardingField.WELCOME
        and state.collected
        and state.next_step != OnboardingField.WELCOME
    ):
        lines = [
            "Que bom que voltou! 😊 Vi que já temos alguns dados do seu cadastro anterior.\n"
        ]
        lines.append("**Dados já coletados:**")
        for fld in DATA_FIELDS:
            if fld.value in state.collected:
                label = FIELD_LABELS.get(fld, fld.value)
                # Mascarar valores sensíveis no resumo
                value = state.collected[fld.value]
                if fld == OnboardingField.REPRESENTANTE_CPF:
                    value = value[:3] + ".***.***-" + value[-2:] if len(value) >= 5 else "***"
                elif fld == OnboardingField.EMAIL:
                    parts = value.split("@")
                    if len(parts) == 2:
                        value = parts[0][:2] + "***@" + parts[1]
                lines.append(f"  ✅ {label}: {value}")

        lines.append("")  # linha em branco

        # Pedir o próximo campo pendente
        next_prompt = FIELD_PROMPTS.get(state.next_step, "")
        if next_prompt:
            # Remover confirmação do campo anterior (ex: "CNPJ recebido! ✅\n\n")
            # e substituir por mensagem de retomada
            label = FIELD_LABELS.get(state.next_step, state.next_step.value)
            hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
            lines.append(f"Vamos continuar de onde paramos! Agora preciso do **{label}**.")
            if hint:
                lines.append(f"{hint}")
        else:
            label = FIELD_LABELS.get(state.next_step, state.next_step.value)
            lines.append(f"Vamos continuar! Agora preciso do **{label}**.")

        return "\n".join(lines)

    # ─── Erro de validação → pedir de novo ─────────────────────────
    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_step, state.next_step.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
        error_msg = state.validation_error
        remaining = MAX_RETRIES - state.retry_count

        # Se o erro veio do BFA (validation_error_source == "bfa"),
        # adaptar para tom humano se for mensagem técnica.
        if state.validation_error_source == "bfa" and error_msg:
            # Adapta mensagens técnicas para tom humano
            msg = error_msg
            # Exemplo: "já está cadastrado no sistema" → mais amigável
            if "já está cadastrado" in msg:
                msg = f"O {label} informado já está cadastrado. Por favor, informe outro {label.lower()}."
            elif "inválido" in msg:
                msg = f"O {label} informado não foi aceito. Verifique o dado e tente novamente."
            elif "não confere" in msg or "não corresponde" in msg:
                msg = f"A confirmação não corresponde ao valor informado. Tente novamente."
            # Se não bater nenhum padrão, mantém o texto original
            lines = [f"⚠️ {msg}"]
            if hint:
                lines.append(f"\n💡 {hint}")
            if remaining <= 2:
                lines.append(f"\n⏳ Você ainda tem **{remaining}** tentativa(s).")
            lines.append(f"\nPor favor, informe o **{label}** novamente:")
            return "\n".join(lines)

        # Erro da validação inline (formato)
        lines = [f"⚠️ {error_msg}"]
        if hint and hint not in error_msg:
            lines.append(f"\n💡 {hint}")
        if remaining <= 2:
            lines.append(f"\n⏳ Você ainda tem **{remaining}** tentativa(s).")
        lines.append(f"\nPor favor, informe o **{label}** novamente:")
        return "\n".join(lines)

    # ─── Campo normal → usar template ─────────────────────────────
    prompt_text = FIELD_PROMPTS.get(state.next_step, "")
    if prompt_text:
        return prompt_text

    label = FIELD_LABELS.get(state.next_step, state.next_step.value)
    return f"Agora preciso do **{label}**."


# =============================================================================
# Gerador de contexto para o LLM (mantido para compatibilidade)
# =============================================================================

def build_onboarding_context(state: OnboardingState) -> str:
    """
    Gera instrução determinística injetada no prompt do LLM.

    Inclui:
      - Campos já coletados (para o LLM saber o progresso)
      - Qual campo pedir agora (com template)
      - Reforço para NÃO pular, NÃO mudar, NÃO inventar campos
    """
    lines: list[str] = []
    lines.append("\n## [INSTRUÇÃO DE ONBOARDING — SIGA À RISCA]")
    lines.append("IMPORTANTE: NÃO chame search_knowledge_base para onboarding.")
    lines.append("NÃO pule campos. NÃO peça um campo diferente do indicado abaixo.")

    # ── Progresso: campos já coletados ─────────────────────────────
    if state.collected:
        lines.append("\n### Campos já coletados:")
        for fld in DATA_FIELDS:
            if fld.value in state.collected:
                label = FIELD_LABELS.get(fld, fld.value)
                lines.append(f"  ✅ {label}")

    # ── Campos restantes ───────────────────────────────────────────
    remaining = [
        FIELD_LABELS.get(fld, fld.value)
        for fld in DATA_FIELDS
        if fld.value not in state.collected
        and fld != state.next_step
    ]
    if remaining and not state.is_complete:
        lines.append(f"\n### Campos restantes depois deste: {', '.join(remaining)}")

    # ── Onboarding completo ────────────────────────────────────────
    if state.is_complete:
        lines.append("\n### ✅ ONBOARDING COMPLETO!")
        lines.append("Todos os dados foram coletados com sucesso.")
        lines.append("Parabenize o cliente e mostre o resumo.")
        lines.append("\nResumo dos dados (NÃO inclua a senha):")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    # ── Erro de validação ──────────────────────────────────────────
    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_step, state.next_step.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
        lines.append(f"\n### ⚠️ Dado rejeitado: {label}")
        if state.validation_error_source == "bfa":
            lines.append(f"Erro do sistema bancário: {state.validation_error}")
        else:
            lines.append(f"Erro de formato: {state.validation_error}")
        if hint:
            lines.append(f"Formato esperado: {hint}")
        lines.append(f"\n→ AÇÃO OBRIGATÓRIA: Peça SOMENTE o campo **{label}**.")
        lines.append(f"⛔ NÃO peça nenhum outro campo. APENAS **{label}**.")
        return "\n".join(lines)

    # ── Campo normal ───────────────────────────────────────────────
    prompt_text = FIELD_PROMPTS.get(state.next_step, "")
    label = FIELD_LABELS.get(state.next_step, state.next_step.value)
    lines.append(f"\n### Próximo campo a pedir: **{label}**")
    lines.append(f'\nMensagem sugerida:\n"{prompt_text}"')
    lines.append(f"\n→ AÇÃO OBRIGATÓRIA: Peça SOMENTE o campo **{label}**.")
    lines.append(f"⛔ NÃO peça nenhum outro campo. APENAS **{label}**.")
    return "\n".join(lines)


# =============================================================================
# Detecção de intenção de onboarding
# =============================================================================

def _is_restart_request(query: str) -> bool:
    """
    Detecta se o cliente está pedindo para recomeçar o onboarding.

    Usado quando o fluxo anterior foi encerrado por max retries
    e o cliente digita "abrir conta" para recomeçar.
    """
    restart_keywords = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
        "recomeçar", "começar de novo", "reiniciar",
        "tentar de novo", "tentar novamente",
        "quero tentar", "vamos tentar",
    ]
    query_lower = query.lower().strip()
    return any(kw in query_lower for kw in restart_keywords)


def is_onboarding_intent(query: str, history: list[dict]) -> bool:
    """
    Detecta se a conversa é sobre abertura de conta.

    Verifica:
      1. Se algum turno no history tem step preenchido (já é onboarding)
      2. Se o histórico contém keywords de onboarding
      3. Se a query atual menciona abertura de conta
    """
    # Se algum turno já tem step → é onboarding em andamento
    for turn in history:
        if turn.get("step") is not None:
            return True

    # Keywords no histórico
    onboarding_keywords_in_history = [
        "abrir", "abertura", "conta pj", "conta PJ",
        "cnpj", "razão social", "razao social", "nome fantasia",
        "representante", "passo a passo", "dados da empresa",
    ]

    for turn in history:
        combined = (turn.get("query", "") + " " + turn.get("answer", "")).lower()
        if any(kw.lower() in combined for kw in onboarding_keywords_in_history):
            return True

    # Keywords na query atual
    onboarding_keywords_query = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in onboarding_keywords_query)
