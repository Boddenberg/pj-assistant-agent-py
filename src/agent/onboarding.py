"""
Onboarding — fluxo conversacional campo-a-campo.

Arquitetura v8.1:
  O agente Python é a CAMADA CONVERSACIONAL.
  O BFA (Go) é a CAMADA DE NEGÓCIO.

  Responsabilidades do agente:
    - Interpretar linguagem natural (IA)
    - Saber qual campo pedir agora (state machine simples)
    - Gerar mensagens amigáveis (templates)
    - Validar formato básico dos campos (guard rail inline)
    - Devolver o campo + valor cru na resposta para o BFA validar

  Responsabilidades do BFA (Go):
    - Validar regras de negócio (CNPJ único, dígito verificador, 18+)
    - Persistir dados
    - Retornar erro estruturado se inválido
    - Reenviar a mensagem com validation_error para o agente pedir correção

  Validação inline (agente):
    O agente faz validações de FORMATO básicas para evitar que dados
    claramente inválidos avancem o fluxo. Isso é um guard rail — o BFA
    faz a validação completa depois. Quando o BFA estiver implementado,
    essa validação será redundante (mas inofensiva).

Fluxo campo-a-campo:
  O agente pede UM campo por vez. O cliente responde. O agente valida
  o formato. Se inválido, pede de novo. Se válido, avança e devolve
  o valor para o BFA validar regras de negócio.
"""

from __future__ import annotations

import re
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
# Validação de formato inline (guard rail)
# =============================================================================
# Estas validações evitam que dados claramente inválidos avancem o fluxo.
# São checagens de FORMATO apenas — regras de negócio ficam no BFA.
# Quando o BFA estiver implementado, essas validações serão redundantes.

def _only_digits(value: str) -> str:
    """Extrai apenas dígitos de uma string."""
    return re.sub(r"\D", "", value)


def validate_field_format(field: "OnboardingField", value: str) -> str | None:
    """
    Valida o formato básico de um campo.

    Args:
        field: Campo sendo validado.
        value: Valor enviado pelo cliente.

    Returns:
        None se válido, mensagem de erro se inválido.
    """
    value = value.strip()

    if field == OnboardingField.CNPJ:
        digits = _only_digits(value)
        if len(digits) != 14:
            return (
                f"CNPJ inválido — deve conter **14 dígitos** numéricos.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: XX.XXX.XXX/XXXX-XX"
            )

    elif field == OnboardingField.RAZAO_SOCIAL:
        if len(value) < 3:
            return "Razão Social deve ter no mínimo **3 caracteres**."

    elif field == OnboardingField.NOME_FANTASIA:
        if len(value) < 2:
            return "Nome Fantasia deve ter no mínimo **2 caracteres**."

    elif field == OnboardingField.EMAIL:
        if "@" not in value or "." not in value.split("@")[-1]:
            return (
                "E-mail inválido — deve conter **@** e um domínio válido.\n"
                "Exemplo: contato@suaempresa.com.br"
            )

    elif field == OnboardingField.REPRESENTANTE_NAME:
        if len(value) < 5:
            return "Nome do representante deve ter no mínimo **5 caracteres**."

    elif field == OnboardingField.REPRESENTANTE_CPF:
        digits = _only_digits(value)
        if len(digits) != 11:
            return (
                f"CPF inválido — deve conter **11 dígitos** numéricos.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: XXX.XXX.XXX-XX"
            )

    elif field == OnboardingField.REPRESENTANTE_PHONE:
        digits = _only_digits(value)
        if len(digits) < 10:
            return (
                f"Telefone inválido — deve conter no mínimo **10 dígitos**.\n"
                f"Você informou {len(digits)} dígito(s).\n"
                f"Formato: (XX) XXXXX-XXXX"
            )

    elif field == OnboardingField.REPRESENTANTE_BIRTH_DATE:
        # Aceita DD/MM/AAAA, DD-MM-AAAA, DD.MM.AAAA
        date_pattern = r"^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$"
        if not re.match(date_pattern, value):
            return (
                "Data de nascimento inválida.\n"
                "Use o formato: **DD/MM/AAAA**\n"
                "Exemplo: 15/03/1990"
            )

    elif field == OnboardingField.PASSWORD:
        if not re.match(r"^\d{6}$", value):
            return (
                "Senha inválida — deve ter exatamente **6 dígitos numéricos**.\n"
                "Sem letras ou caracteres especiais."
            )

    elif field == OnboardingField.PASSWORD_CONFIRMATION:
        if not re.match(r"^\d{6}$", value):
            return (
                "Confirmação de senha inválida — deve ter exatamente "
                "**6 dígitos numéricos**."
            )

    return None  # válido


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

    # Contar turnos de dados aceitos (a partir do turno 1).
    # Turno 0 = cliente pediu abertura (não é dado).
    # Turno 1+ = cliente respondeu um campo.
    # PORÉM: turnos de retry (rejeição) NÃO contam como dados aceitos.
    # Identificamos retries pela presença de "⚠️" na resposta do agente
    # (que é o marcador do template de erro de validação).
    data_turns = 0
    for i in range(1, len(history)):
        answer = history[i].get("answer", "")
        if "⚠️" in answer:
            # Turno de retry — não contar como dado aceito
            continue
        data_turns += 1
        # Coletar o dado deste turno
        if data_turns - 1 < len(DATA_FIELDS):
            field_enum = DATA_FIELDS[data_turns - 1]
            collected[field_enum.value] = history[i]["query"]

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
        # Todos os campos já foram respondidos nos turnos do history.
        # A query atual não é um campo — é apenas a mensagem final.
        return OnboardingState(
            current_field=DATA_FIELDS[-1],
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
            field_value=current_query,
        )

    # ─── Validação inline de formato (guard rail) ──────────────────
    # Checa formato básico ANTES de avançar. Se inválido, pede de novo.
    # Isso evita que o fluxo avance com dados lixo quando o BFA
    # ainda não está implementado. Quando o BFA existir, a validação
    # será redundante (BFA faz validação completa).
    format_error = validate_field_format(answering_field, current_query)
    if format_error:
        logger.info(
            "⚠️ [ONBOARDING] Inline validation failed",
            field=answering_field.value,
            value_preview=current_query[:20],
            error=format_error[:80],
        )
        collected.pop(answering_field.value, None)
        return OnboardingState(
            current_field=answering_field,
            next_field=answering_field,  # pedir o MESMO campo de novo
            collected=collected,
            has_validation_error=True,
            validation_error=format_error,
            field_value=current_query,
        )

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

def build_onboarding_response(state: OnboardingState) -> str:
    """
    Gera a resposta FINAL para o cliente — determinística, sem LLM.

    Arquitetura v8.1:
      O onboarding não precisa de IA para gerar respostas.
      Cada passo é um template fixo. Usar o LLM causava alucinações
      (ex: LLM respondia "E-mail recebido! Confirme telefone" quando
      a instrução dizia "Nome Fantasia recebido! Informe e-mail").

      Solução: bypass total do LLM para onboarding.
      O template do FIELD_PROMPTS É a resposta final.

    Returns:
        String com a resposta pronta para o cliente.
    """
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

    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_field, state.next_field.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_field, "")
        lines = [f"⚠️ O dado informado para **{label}** não está válido."]
        lines.append(f"Motivo: {state.validation_error}")
        if hint:
            lines.append(f"\n{hint}")
        lines.append(f"\nPor favor, informe o **{label}** novamente.")
        return "\n".join(lines)

    # Campo normal — usar o template diretamente
    prompt_text = FIELD_PROMPTS.get(state.next_field, "")
    if prompt_text:
        return prompt_text

    # Fallback (não deveria chegar aqui)
    label = FIELD_LABELS.get(state.next_field, state.next_field.value)
    return f"Agora preciso do **{label}**."


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
