"""
Onboarding — fluxo conversacional campo-a-campo.

Arquitetura v8:
  O agente Python é a CAMADA CONVERSACIONAL.
  O BFA (Go) é a CAMADA DE NEGÓCIO.

  Responsabilidades do agente:
    - Interpretar linguagem natural (IA)
    - Saber qual campo pedir agora (state machine simples)
    - Gerar mensagens amigáveis (templates + IA para ambiguidade)
    - Devolver o campo + valor cru na resposta para o BFA validar

  Responsabilidades do BFA (Go):
    - Validar formato (CNPJ 14 dígitos, CPF 11 dígitos, email com @, etc.)
    - Validar regra de negócio (CNPJ único, representante 18+, dígito verificador)
    - Persistir dados
    - Retornar erro estruturado se inválido
    - Reenviar a mensagem com validation_error para o agente pedir correção

  O agente NUNCA valida formato. O cliente manda "12345", o agente
  devolve { current_field: "cnpj", field_value: "12345" } e o BFA decide.

Fluxo campo-a-campo:
  O agente pede UM campo por vez. O cliente responde. O agente identifica
  qual campo está sendo respondido e avança. Sem ambiguidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.observability.logging import get_logger

logger = get_logger("onboarding")


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


# Sequência ordenada — a ordem em que os campos serão pedidos
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

# Mensagens template — o que o agente diz ao pedir cada campo
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

# Labels para o resumo final
FIELD_LABELS: dict[OnboardingField, str] = {
    OnboardingField.CNPJ: "CNPJ",
    OnboardingField.RAZAO_SOCIAL: "Razão Social",
    OnboardingField.NOME_FANTASIA: "Nome Fantasia",
    OnboardingField.EMAIL: "E-mail",
    OnboardingField.REPRESENTANTE_NAME: "Representante",
    OnboardingField.REPRESENTANTE_CPF: "CPF do representante",
    OnboardingField.REPRESENTANTE_PHONE: "Telefone",
    OnboardingField.REPRESENTANTE_BIRTH_DATE: "Data de nascimento",
}

# Dicas de formato por campo (fallback se o BFA não retornar mensagem)
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
# State Machine — determina o campo atual pelo histórico
# =============================================================================

@dataclass
class OnboardingState:
    """Estado do onboarding derivado do histórico."""
    current_field: OnboardingField      # campo que o cliente ACABOU de responder (BFA valida)
    next_field: OnboardingField         # campo que o LLM deve PEDIR agora
    collected: dict[str, str] = field(default_factory=dict)
    is_complete: bool = False
    has_validation_error: bool = False
    validation_error: str = ""
    field_value: str = ""  # valor cru que o cliente enviou para o campo atual


def determine_current_field(
    history: list[dict[str, str]],
    current_query: str,
    validation_error: str = "",
) -> OnboardingState:
    """
    Analisa o histórico para determinar em qual campo estamos.

    Conceitos-chave:
      - current_field: campo que o cliente acabou de responder (BFA valida esse)
      - next_field: campo que o LLM deve PEDIR ao cliente agora
      - field_value: valor cru da query atual (BFA valida)

    Lógica:
      - history vazio: primeira mensagem → welcome (next_field = CNPJ)
      - Turno 0 no histórico: cliente pediu abertura → agente deu welcome
      - A partir do turno 1: cada turno = cliente respondeu um campo
      - Se validation_error != "": o BFA rejeitou o último campo → repetir
      - A query atual é o valor do campo que está sendo respondido agora

    Args:
        history: Turnos anteriores [{"query": "...", "answer": "..."}]
        current_query: Mensagem atual do cliente (valor do campo)
        validation_error: Erro do BFA se o último campo foi rejeitado

    Returns:
        OnboardingState com campo atual, próximo campo, valor e dados coletados.
    """
    collected: dict[str, str] = {}

    if not history:
        # Primeira mensagem — welcome + pedir CNPJ
        return OnboardingState(
            current_field=OnboardingField.WELCOME,
            next_field=OnboardingField.WELCOME,
            field_value=current_query,
        )

    # Contar turnos de dados (a partir do turno 1).
    # Turno 0 = cliente pediu abertura (não é dado).
    # Turno 1 = cliente respondeu CNPJ.
    # Turno 2 = cliente respondeu Razão Social.
    # ...
    data_turns = len(history) - 1  # descontar turno 0 (abertura)

    # Coletar dados dos turnos anteriores (não inclui a query atual)
    for i in range(data_turns):
        if i < len(DATA_FIELDS):
            field_enum = DATA_FIELDS[i]
            turn = history[i + 1]  # +1 porque turno 0 é abertura
            collected[field_enum.value] = turn["query"]

    # Se o BFA rejeitou o último campo, repetir
    if validation_error:
        if data_turns > 0 and data_turns <= len(DATA_FIELDS):
            # O último campo foi rejeitado — remover dos coletados
            rejected_field = DATA_FIELDS[data_turns - 1]
            collected.pop(rejected_field.value, None)
            return OnboardingState(
                current_field=rejected_field,
                next_field=rejected_field,  # pedir o MESMO campo de novo
                collected=collected,
                has_validation_error=True,
                validation_error=validation_error,
                field_value=current_query,
            )

    # O campo que o cliente está respondendo AGORA com current_query
    if data_turns < len(DATA_FIELDS):
        answering_field = DATA_FIELDS[data_turns]
    else:
        answering_field = DATA_FIELDS[-1]

    # Incluir a resposta atual nos coletados
    collected[answering_field.value] = current_query

    # Determinar o PRÓXIMO campo a pedir
    next_index = data_turns + 1
    if next_index >= len(DATA_FIELDS):
        # Todos os campos coletados → completo
        return OnboardingState(
            current_field=answering_field,
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
            field_value=current_query,
        )

    next_field = DATA_FIELDS[next_index]

    logger.info(
        "📋 [ONBOARDING] State determined",
        answering_field=answering_field.value,
        next_field=next_field.value,
        collected_count=len(collected),
        collected_fields=list(collected.keys()),
        history_turns=len(history),
        data_turns=data_turns,
    )

    return OnboardingState(
        current_field=answering_field,
        next_field=next_field,
        collected=collected,
        field_value=current_query,
    )


# =============================================================================
# Gerador de contexto para o LLM
# =============================================================================

def build_onboarding_context(state: OnboardingState) -> str:
    """
    Gera instrução determinística para o LLM.

    O LLM recebe o template de resposta e os dados já coletados.
    Só precisa humanizar o texto — a lógica está em Python.
    """
    lines: list[str] = []
    lines.append("\n## [INSTRUÇÃO DE ONBOARDING — SIGA À RISCA]")
    lines.append("IMPORTANTE: NÃO chame search_knowledge_base para onboarding. "
                 "Use SOMENTE as instruções abaixo.")

    if state.is_complete:
        lines.append("\n### ✅ ONBOARDING COMPLETO!")
        lines.append("Todos os dados foram coletados com sucesso.")
        lines.append("Informe ao cliente que o cadastro será processado.")
        lines.append("\nResumo dos dados (NÃO inclua a senha):")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_field, state.next_field.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_field, "")
        lines.append(f"\n### ⚠️ Dado rejeitado: {label}")
        lines.append(f"Erro: {state.validation_error}")
        if hint:
            lines.append(f"Formato esperado: {hint}")
        lines.append("\n→ AÇÃO: Informe o erro de forma amigável e peça para digitar novamente.")
        lines.append(f"   Peça SOMENTE o campo: {label}")
        return "\n".join(lines)

    # Campo normal — pedir ao cliente o PRÓXIMO campo
    prompt_text = FIELD_PROMPTS.get(state.next_field, "")
    label = FIELD_LABELS.get(state.next_field, state.next_field.value)
    lines.append(f"\n### Próximo campo: {label}")
    lines.append(f"\nResponda ao cliente com esta mensagem (pode humanizar levemente):")
    lines.append(f'"{prompt_text}"')
    lines.append("\n→ AÇÃO: Peça SOMENTE este campo. NÃO peça outros dados.")

    return "\n".join(lines)


# =============================================================================
# Detecção de intenção de onboarding
# =============================================================================

def is_onboarding_intent(query: str, history: list[dict[str, str]]) -> bool:
    """
    Detecta se a conversa é sobre abertura de conta.

    Verifica:
      1. Se o histórico já contém contexto de onboarding
      2. Se a query atual menciona abertura de conta
    """
    onboarding_keywords_in_history = [
        "abrir", "abertura", "conta pj", "conta PJ",
        "cnpj", "razão social", "razao social", "nome fantasia",
        "representante", "passo a passo", "dados da empresa",
    ]

    for turn in history:
        combined = (turn.get("query", "") + " " + turn.get("answer", "")).lower()
        if any(kw.lower() in combined for kw in onboarding_keywords_in_history):
            return True

    onboarding_keywords_query = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in onboarding_keywords_query)
