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


# Máximo de tentativas por campo antes de desistir
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
                f"CNPJ inválido — deve conter **14 dígitos** numéricos.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: XX.XXX.XXX/XXXX-XX"
            )

    elif field_enum == OnboardingField.RAZAO_SOCIAL:
        if len(value) < 3:
            return "Razão Social deve ter no mínimo **3 caracteres**."

    elif field_enum == OnboardingField.NOME_FANTASIA:
        if len(value) < 2:
            return "Nome Fantasia deve ter no mínimo **2 caracteres**."

    elif field_enum == OnboardingField.EMAIL:
        if "@" not in value or "." not in value.split("@")[-1]:
            return (
                "E-mail inválido — deve conter **@** e um domínio válido.\n"
                "Exemplo: contato@suaempresa.com.br"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_NAME:
        if len(value) < 5:
            return "Nome do representante deve ter no mínimo **5 caracteres**."

    elif field_enum == OnboardingField.REPRESENTANTE_CPF:
        digits = _only_digits(value)
        if len(digits) != 11:
            return (
                f"CPF inválido — deve conter **11 dígitos** numéricos.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: XXX.XXX.XXX-XX"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_PHONE:
        digits = _only_digits(value)
        if len(digits) < 10:
            return (
                f"Telefone inválido — deve conter no mínimo **10 dígitos**.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: (XX) XXXXX-XXXX"
            )

    elif field_enum == OnboardingField.REPRESENTANTE_BIRTH_DATE:
        date_pattern = r"^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$"
        if not re.match(date_pattern, value):
            return (
                "Data de nascimento inválida.\n"
                "Use o formato: **DD/MM/AAAA**\n"
                "Exemplo: 15/03/1990"
            )

    elif field_enum == OnboardingField.PASSWORD:
        if not re.match(r"^\d{6}$", value):
            return (
                "Senha inválida — deve ter exatamente **6 dígitos numéricos**.\n"
                "Sem letras ou caracteres especiais."
            )

    elif field_enum == OnboardingField.PASSWORD_CONFIRMATION:
        if not re.match(r"^\d{6}$", value):
            return (
                "Confirmação de senha inválida — deve ter exatamente "
                "**6 dígitos numéricos**."
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
    field_value: str = ""               # valor cru que o cliente enviou
    retry_count: int = 0                # quantas vezes errou o step atual
    max_retries_exceeded: bool = False   # se excedeu o limite de retries


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
) -> OnboardingState:
    """
    Determina o estado do onboarding com base no history enriquecido.

    O BFA envia cada turno com step + validated. O agente:
      1. Percorre o history para encontrar o último step validado
      2. Determina o próximo step
      3. Valida formato inline da query atual
      4. Conta retries consecutivos no mesmo step

    Args:
        history: Turnos com {query, answer, step, validated}
        current_query: Mensagem atual do cliente
        validation_error: Erro do BFA se rejeitou o último campo

    Returns:
        OnboardingState completo
    """
    collected: dict[str, str] = {}

    # ─── Sem history → primeira mensagem (welcome) ─────────────────
    if not history:
        return OnboardingState(
            step=OnboardingField.WELCOME,
            next_step=OnboardingField.WELCOME,
            field_value=current_query,
        )

    # ─── Percorrer o history para encontrar o estado ───────────────
    # Estratégia: identificar o último step VALIDADO pelo BFA.
    # O próximo step é o seguinte na sequência.
    last_validated_step: OnboardingField | None = None
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
        elif validated is False:
            retry_count += 1

    # ─── Determinar o step que o cliente está respondendo AGORA ────
    if last_validated_step is None:
        # Nenhum campo validado ainda → cliente está respondendo CNPJ
        current_step = OnboardingField.CNPJ
    else:
        current_step = _get_next_field(last_validated_step)

    # Se já completou todos os campos
    if current_step == OnboardingField.COMPLETED:
        return OnboardingState(
            step=OnboardingField.COMPLETED,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
            field_value=current_query,
        )

    # ─── Verificar limite de retries ───────────────────────────────
    # Se o BFA retornou validated=False no último turno, contar como retry.
    # Se já mandou validation_error, é mais um retry.
    if validation_error:
        retry_count += 1

    if retry_count >= MAX_RETRIES:
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
            retry_count=retry_count,
        )

        if retry_count >= MAX_RETRIES:
            return OnboardingState(
                step=current_step,
                next_step=current_step,
                collected=collected,
                has_validation_error=True,
                validation_error=format_error,
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
            f"Não conseguimos validar o **{label}** após algumas tentativas. 😕\n\n"
            "Quando estiver com os dados em mãos para a abertura de conta, "
            "estaremos por aqui! 😊\n\n"
            "É só digitar **\"abrir conta\"** para recomeçar."
        )

    # ─── Onboarding completo ──────────────────────────────────────
    if state.is_complete:
        lines = ["Todos os dados foram recebidos! ✅🎉\n"]
        lines.append("Confira o resumo do cadastro:\n")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- **{label}**: {value}")
        lines.append(
            "\nSeu cadastro será processado e em breve sua conta "
            "PJ estará pronta! 🚀"
        )
        return "\n".join(lines)

    # ─── Erro de validação → pedir de novo ─────────────────────────
    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_step, state.next_step.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
        lines = [f"⚠️ O dado informado para **{label}** não está válido."]
        lines.append(f"Motivo: {state.validation_error}")
        if hint:
            lines.append(f"\n{hint}")
        lines.append(f"\nPor favor, informe o **{label}** novamente.")
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
        lines.append(f"Erro: {state.validation_error}")
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
