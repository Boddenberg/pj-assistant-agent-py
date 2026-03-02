"""
Onboarding — validação determinística e máquina de estados.

Por que NÃO confiar no LLM para validar dados e controlar fluxo?
  - LLM é probabilístico: pode "esquecer" passos ou pular etapas
  - Validação de CNPJ/CPF/email precisa ser determinística (regex)
  - Controle de fluxo precisa ser rígido (etapa 1 → 2 → 3 → 4)
  - LLM é bom para CONVERSAR, não para seguir regras de negócio

Arquitetura:
  1. OnboardingValidator — validação de formato (regex, regras)
  2. OnboardingStateMachine — detecta etapa atual pelo histórico
  3. build_onboarding_context() — gera instruções determinísticas pro LLM

O runner chama build_onboarding_context() antes de invocar o grafo.
O LLM recebe a etapa atual + dados validados + próximos campos a pedir.
Assim o LLM só precisa ser conversacional — a lógica está em Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

from src.observability.logging import get_logger

logger = get_logger("onboarding")


# =============================================================================
# Constantes
# =============================================================================

class OnboardingStep(IntEnum):
    """Etapas do onboarding — ordem é obrigatória."""
    STEP_1_COMPANY = 1      # CNPJ, Razão Social, Nome Fantasia, E-mail
    STEP_2_REPRESENTATIVE = 2  # Nome, CPF, Telefone, Data de nascimento
    STEP_3_PASSWORD = 3      # Senha numérica de 6 dígitos
    STEP_4_CONFIRM = 4       # Confirmação da senha
    COMPLETED = 5            # Fluxo concluído


# Campos por etapa
STEP_FIELDS: dict[int, list[str]] = {
    1: ["cnpj", "razaoSocial", "nomeFantasia", "email"],
    2: ["representanteName", "representanteCpf", "representantePhone", "representanteBirthDate"],
    3: ["password"],
    4: ["passwordConfirmation"],
}

# Labels amigáveis para cada campo (português)
FIELD_LABELS: dict[str, str] = {
    "cnpj": "CNPJ",
    "razaoSocial": "Razão Social",
    "nomeFantasia": "Nome Fantasia",
    "email": "E-mail",
    "representanteName": "Nome do representante",
    "representanteCpf": "CPF do representante",
    "representantePhone": "Telefone",
    "representanteBirthDate": "Data de nascimento",
    "password": "Senha (6 dígitos numéricos)",
    "passwordConfirmation": "Confirmação da senha",
}


# =============================================================================
# Validador — regras determinísticas de formato
# =============================================================================

@dataclass
class ValidationResult:
    """Resultado de uma validação de campo."""
    valid: bool
    value: str = ""           # Valor limpo/normalizado
    error: str = ""           # Mensagem de erro (se inválido)


class OnboardingValidator:
    """
    Validador determinístico de campos do onboarding.

    Cada método retorna ValidationResult com:
      - valid: se passou na validação
      - value: valor normalizado (CNPJ sem pontos, etc.)
      - error: mensagem de erro legível para o cliente
    """

    @staticmethod
    def validate_cnpj(raw: str) -> ValidationResult:
        """Valida CNPJ: 14 dígitos numéricos."""
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 14:
            return ValidationResult(
                valid=False,
                error=f"CNPJ inválido: '{raw}'. O CNPJ deve ter 14 dígitos (ex: 12.345.678/0001-90).",
            )
        formatted = f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
        return ValidationResult(valid=True, value=formatted)

    @staticmethod
    def validate_cpf(raw: str) -> ValidationResult:
        """Valida CPF: 11 dígitos numéricos."""
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 11:
            return ValidationResult(
                valid=False,
                error=f"CPF inválido: '{raw}'. O CPF deve ter 11 dígitos (ex: 123.456.789-00).",
            )
        formatted = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return ValidationResult(valid=True, value=formatted)

    @staticmethod
    def validate_email(raw: str) -> ValidationResult:
        """Valida e-mail: deve conter @ e domínio."""
        email = raw.strip()
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            return ValidationResult(
                valid=False,
                error=f"E-mail inválido: '{raw}'. Deve conter @ e um domínio válido (ex: empresa@email.com).",
            )
        return ValidationResult(valid=True, value=email)

    @staticmethod
    def validate_razao_social(raw: str) -> ValidationResult:
        """Valida Razão Social: mínimo 3 caracteres."""
        value = raw.strip()
        if len(value) < 3:
            return ValidationResult(
                valid=False,
                error=f"Razão Social muito curta: '{raw}'. Mínimo 3 caracteres.",
            )
        return ValidationResult(valid=True, value=value)

    @staticmethod
    def validate_nome_fantasia(raw: str) -> ValidationResult:
        """Valida Nome Fantasia: mínimo 2 caracteres."""
        value = raw.strip()
        if len(value) < 2:
            return ValidationResult(
                valid=False,
                error=f"Nome Fantasia muito curto: '{raw}'. Mínimo 2 caracteres.",
            )
        return ValidationResult(valid=True, value=value)

    @staticmethod
    def validate_representante_name(raw: str) -> ValidationResult:
        """Valida nome do representante: mínimo 5 caracteres."""
        value = raw.strip()
        if len(value) < 5:
            return ValidationResult(
                valid=False,
                error=f"Nome do representante muito curto: '{raw}'. Mínimo 5 caracteres (nome completo).",
            )
        return ValidationResult(valid=True, value=value)

    @staticmethod
    def validate_phone(raw: str) -> ValidationResult:
        """Valida telefone: (XX) XXXXX-XXXX ou (XX) XXXX-XXXX."""
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10 or len(digits) > 11:
            return ValidationResult(
                valid=False,
                error=f"Telefone inválido: '{raw}'. Use o formato (XX) XXXXX-XXXX (10 ou 11 dígitos).",
            )
        if len(digits) == 11:
            formatted = f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        else:
            formatted = f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        return ValidationResult(valid=True, value=formatted)

    @staticmethod
    def validate_birth_date(raw: str) -> ValidationResult:
        """Valida data de nascimento: DD/MM/AAAA, 18+ anos."""
        value = raw.strip()
        # Tentar parsear DD/MM/AAAA
        match = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", value)
        if not match:
            return ValidationResult(
                valid=False,
                error=f"Data inválida: '{raw}'. Use o formato DD/MM/AAAA (ex: 19/02/1996).",
            )
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            birth = datetime(year, month, day)
        except ValueError:
            return ValidationResult(
                valid=False,
                error=f"Data inválida: '{raw}'. Verifique dia/mês/ano.",
            )
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age < 18:
            return ValidationResult(
                valid=False,
                error=f"O representante deve ter 18 anos ou mais. Data informada: {value}.",
            )
        formatted = f"{day:02d}/{month:02d}/{year}"
        return ValidationResult(valid=True, value=formatted)

    @staticmethod
    def validate_password(raw: str) -> ValidationResult:
        """Valida senha: exatamente 6 dígitos numéricos."""
        value = raw.strip()
        if not re.match(r"^\d{6}$", value):
            return ValidationResult(
                valid=False,
                error="Senha inválida. A senha deve ter exatamente 6 dígitos numéricos (ex: 123456).",
            )
        return ValidationResult(valid=True, value=value)

    @staticmethod
    def validate_password_confirmation(raw: str, password: str) -> ValidationResult:
        """Valida confirmação de senha: deve ser idêntica à senha."""
        value = raw.strip()
        if value != password:
            return ValidationResult(
                valid=False,
                error="As senhas não coincidem. Por favor, digite a mesma senha de 6 dígitos.",
            )
        return ValidationResult(valid=True, value=value)


# Mapeamento campo → método de validação
_VALIDATORS: dict[str, str] = {
    "cnpj": "validate_cnpj",
    "razaoSocial": "validate_razao_social",
    "nomeFantasia": "validate_nome_fantasia",
    "email": "validate_email",
    "representanteName": "validate_representante_name",
    "representanteCpf": "validate_cpf",
    "representantePhone": "validate_phone",
    "representanteBirthDate": "validate_birth_date",
    "password": "validate_password",
}


# =============================================================================
# Extrator — tenta extrair dados da mensagem do cliente
# =============================================================================

class OnboardingExtractor:
    """
    Extrai dados de onboarding de uma mensagem de texto livre.

    Usa regex patterns para encontrar CNPJ, CPF, e-mail, telefone, etc.
    em texto não estruturado. Retorna dict com campos encontrados.
    """

    @staticmethod
    def extract_from_message(text: str) -> dict[str, str]:
        """Extrai campos identificáveis da mensagem do cliente."""
        found: dict[str, str] = {}

        # CNPJ: XX.XXX.XXX/XXXX-XX ou 14 dígitos seguidos
        cnpj_match = re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", text)
        if cnpj_match:
            found["cnpj"] = cnpj_match.group()
        else:
            # Fallback: se o texto menciona "CNPJ", capturar o que vem depois
            # para permitir validação de formato inválido (gerar erro)
            cnpj_fallback = re.search(
                r"cnpj[:\s]+([0-9./\-]+)", text, re.IGNORECASE,
            )
            if cnpj_fallback:
                found["cnpj"] = cnpj_fallback.group(1).strip(", ")

        # CPF: XXX.XXX.XXX-XX ou 11 dígitos seguidos (mas não dentro de CNPJ)
        # Procurar CPF depois de remover o CNPJ do texto para evitar falso positivo
        text_no_cnpj = text
        if cnpj_match:
            text_no_cnpj = text[:cnpj_match.start()] + text[cnpj_match.end():]
        cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_no_cnpj)
        if cpf_match:
            found["representanteCpf"] = cpf_match.group()

        # E-mail
        email_match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        if email_match:
            found["email"] = email_match.group()
        else:
            # Fallback: se o texto menciona "email"/"e-mail", capturar o valor
            # para permitir validação de formato inválido (gerar erro)
            email_fallback = re.search(
                r"e-?mail[:\s]+([^\s,]+)", text, re.IGNORECASE,
            )
            if email_fallback:
                found["email"] = email_fallback.group(1).strip(", ")

        # Telefone: (XX) XXXXX-XXXX ou variações
        phone_match = re.search(r"\(?\d{2}\)?\s*\d{4,5}-?\d{4}", text)
        if phone_match:
            found["representantePhone"] = phone_match.group()

        # Data de nascimento: DD/MM/AAAA
        date_match = re.search(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}", text)
        if date_match:
            found["representanteBirthDate"] = date_match.group()

        # Senha: 6 dígitos isolados (não parte de outro número)
        # Só procurar se a mensagem for curta ou explicitamente mencionou "senha"
        if re.search(r"senha", text, re.IGNORECASE) or len(text.strip()) <= 10:
            pwd_match = re.search(r"\b(\d{6})\b", text)
            if pwd_match:
                # Verificar se não é parte de CNPJ, CPF ou telefone
                pwd_val = pwd_match.group(1)
                is_part_of_other = False
                for key in ["cnpj", "representanteCpf", "representantePhone"]:
                    if key in found and pwd_val in re.sub(r"\D", "", found[key]):
                        is_part_of_other = True
                        break
                if not is_part_of_other:
                    found["password"] = pwd_val

        # Razão Social: após "razão social" ou "razao social"
        rs_match = re.search(
            r"raz[ãa]o\s+social[:\s]+([^,\n]+?)(?:,\s*(?:nome|e-?mail|cnpj)|$)",
            text, re.IGNORECASE,
        )
        if rs_match:
            found["razaoSocial"] = rs_match.group(1).strip()

        # Nome Fantasia: após "nome fantasia"
        nf_match = re.search(
            r"nome\s+fantasia[:\s]+([^,\n]+?)(?:,\s*(?:raz[ãa]o|e-?mail|cnpj)|$)",
            text, re.IGNORECASE,
        )
        if nf_match:
            found["nomeFantasia"] = nf_match.group(1).strip()

        # Nome do representante: text que vem antes do CPF, ou após "nome"
        # Heurística: nome completo é texto com letras antes do CPF
        name_match = re.search(
            r"(?:^|nome[:\s]+)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{3,}?)(?:,|\s*CPF|\s*cpf|\s*\d{3}\.)",
            text, re.IGNORECASE,
        )
        if name_match:
            candidate = name_match.group(1).strip()
            # Não pegar "Razão Social" ou "Nome Fantasia" como nome do representante
            if not re.search(r"raz[ãa]o|fantasia|social", candidate, re.IGNORECASE):
                found["representanteName"] = candidate

        return found


# =============================================================================
# State Machine — controla o fluxo de onboarding
# =============================================================================

@dataclass
class OnboardingState:
    """Estado completo do onboarding extraído do histórico."""
    current_step: int = 1
    collected: dict[str, str] = field(default_factory=dict)  # campo → valor validado
    errors: list[str] = field(default_factory=list)           # erros da mensagem atual
    pending_fields: list[str] = field(default_factory=list)   # campos faltando na etapa atual
    is_complete: bool = False


class OnboardingStateMachine:
    """
    Máquina de estados do onboarding.

    Analisa o histórico de conversa para reconstruir o estado:
      1. Percorre cada turno (query + answer)
      2. Extrai dados de cada mensagem do cliente
      3. Valida cada dado extraído
      4. Determina a etapa atual

    Depois processa a mensagem ATUAL do cliente:
      1. Extrai novos dados
      2. Valida
      3. Retorna o estado atualizado com erros e campos pendentes
    """

    def __init__(self) -> None:
        self.validator = OnboardingValidator()
        self.extractor = OnboardingExtractor()

    def _validate_field(
        self, field_name: str, raw_value: str, collected: dict[str, str],
    ) -> ValidationResult:
        """Valida um campo usando o validador adequado."""
        if field_name == "passwordConfirmation":
            password = collected.get("password", "")
            return self.validator.validate_password_confirmation(raw_value, password)

        method_name = _VALIDATORS.get(field_name)
        if not method_name:
            return ValidationResult(valid=False, error=f"Campo desconhecido: {field_name}")

        method = getattr(self.validator, method_name)
        return method(raw_value)

    def _determine_step(self, collected: dict[str, str]) -> int:
        """Determina a etapa atual com base nos dados coletados."""
        # Etapa 1 completa?
        step1_fields = STEP_FIELDS[1]
        if not all(f in collected for f in step1_fields):
            return 1

        # Etapa 2 completa?
        step2_fields = STEP_FIELDS[2]
        if not all(f in collected for f in step2_fields):
            return 2

        # Etapa 3 completa?
        if "password" not in collected:
            return 3

        # Etapa 4 completa?
        if "passwordConfirmation" not in collected:
            return 4

        return 5  # Completo

    def _extract_and_validate(
        self, text: str, current_step: int, collected: dict[str, str],
    ) -> tuple[dict[str, str], list[str]]:
        """
        Extrai dados do texto e valida os que pertencem à etapa atual.
        Retorna (novos campos validados, erros).
        """
        extracted = self.extractor.extract_from_message(text)
        new_collected: dict[str, str] = {}
        errors: list[str] = []

        # Campos da etapa atual
        current_fields = STEP_FIELDS.get(current_step, [])

        for field_name in current_fields:
            if field_name in collected:
                continue  # Já coletado

            raw = extracted.get(field_name)
            if raw is None:
                continue  # Não encontrado nesta mensagem

            result = self._validate_field(field_name, raw, collected)
            if result.valid:
                new_collected[field_name] = result.value
            else:
                errors.append(result.error)

        return new_collected, errors

    def process(
        self,
        history: list[dict[str, str]],
        current_query: str,
    ) -> OnboardingState:
        """
        Processa o histórico completo + mensagem atual.

        Args:
            history: Lista de turnos [{"query": "...", "answer": "..."}]
            current_query: Mensagem atual do cliente

        Returns:
            OnboardingState com etapa atual, dados coletados, erros e campos pendentes.
        """
        collected: dict[str, str] = {}

        # 1. Reconstruir estado a partir do histórico
        for turn in history:
            step = self._determine_step(collected)
            new_data, _ = self._extract_and_validate(
                turn["query"], step, collected,
            )
            collected.update(new_data)

            # Recalcular step após coletar dados
            step = self._determine_step(collected)

        # 2. Processar mensagem atual
        current_step = self._determine_step(collected)
        new_data, errors = self._extract_and_validate(
            current_query, current_step, collected,
        )
        collected.update(new_data)

        # 3. Recalcular etapa final e campos pendentes
        final_step = self._determine_step(collected)
        pending = [
            f for f in STEP_FIELDS.get(final_step, [])
            if f not in collected
        ]

        is_complete = final_step == 5

        state = OnboardingState(
            current_step=final_step,
            collected=collected,
            errors=errors,
            pending_fields=pending,
            is_complete=is_complete,
        )

        logger.info(
            "📋 [ONBOARDING] State computed",
            current_step=final_step,
            collected_fields=list(collected.keys()),
            errors=errors,
            pending_fields=pending,
            is_complete=is_complete,
        )

        return state


# =============================================================================
# Build context — gera instrução determinística para o LLM
# =============================================================================

def build_onboarding_context(state: OnboardingState) -> str:
    """
    Gera uma instrução clara e determinística para o LLM.

    Em vez de confiar no LLM para detectar etapa/validar dados,
    dizemos EXATAMENTE o que ele deve fazer:

    - Qual etapa estamos
    - Quais dados já foram coletados (validados)
    - Quais erros de validação ocorreram
    - Quais campos ainda faltam

    O LLM só precisa ser conversacional — a lógica está em Python.
    """
    lines: list[str] = []
    lines.append("\n## [INSTRUÇÃO DE ONBOARDING — GERADA POR CÓDIGO, SIGA À RISCA]")

    if state.is_complete:
        lines.append("\n### ✅ ONBOARDING COMPLETO!")
        lines.append("Todos os dados foram coletados e validados com sucesso.")
        lines.append("Informe ao cliente que o cadastro será processado.")
        lines.append("\nResumo dos dados coletados (NÃO inclua a senha no resumo):")
        for field_name, value in state.collected.items():
            if field_name in ("password", "passwordConfirmation"):
                continue
            label = FIELD_LABELS.get(field_name, field_name)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    step_names = {
        1: "Etapa 1 — Dados da Empresa",
        2: "Etapa 2 — Dados do Representante Legal",
        3: "Etapa 3 — Criação de Senha",
        4: "Etapa 4 — Confirmação de Senha",
    }

    lines.append(f"\n### Etapa atual: {step_names.get(state.current_step, 'Desconhecida')}")

    # Dados já coletados
    if state.collected:
        lines.append("\n**Dados já coletados e validados ✅:**")
        for field_name, value in state.collected.items():
            if field_name in ("password", "passwordConfirmation"):
                lines.append(f"- Senha: ******")
                continue
            label = FIELD_LABELS.get(field_name, field_name)
            lines.append(f"- {label}: {value}")

    # Erros de validação
    if state.errors:
        lines.append("\n**⚠️ Erros de validação encontrados (INFORME AO CLIENTE):**")
        for error in state.errors:
            lines.append(f"- {error}")
        lines.append("\nPeça ao cliente para corrigir os dados acima ANTES de avançar.")

    # Campos pendentes
    if state.pending_fields:
        lines.append("\n**Campos que FALTAM nesta etapa (PEÇA AO CLIENTE):**")
        for field_name in state.pending_fields:
            label = FIELD_LABELS.get(field_name, field_name)
            lines.append(f"- {label}")

    # Instrução final
    if state.errors:
        lines.append(
            "\n→ AÇÃO: Informe os erros de validação acima e peça a correção. "
            "NÃO avance para a próxima etapa."
        )
    elif state.pending_fields:
        lines.append(
            "\n→ AÇÃO: Peça os campos faltantes listados acima. "
            "NÃO avance para a próxima etapa até ter todos."
        )
    else:
        lines.append(
            "\n→ AÇÃO: Todos os campos desta etapa foram coletados. "
            "Confirme os dados e peça os da próxima etapa."
        )

    return "\n".join(lines)


def is_onboarding_intent(query: str, history: list[dict[str, str]]) -> bool:
    """
    Detecta se a conversa é de onboarding (abertura de conta).

    Verifica:
      1. Se o histórico já contém contexto de onboarding
      2. Se a query atual menciona abertura de conta
    """
    # Verificar se o histórico já tem respostas de onboarding (etapa, CNPJ, etc.)
    onboarding_keywords_in_history = [
        "abrir", "abertura", "conta pj", "conta PJ",
        "cnpj", "razão social", "razao social", "nome fantasia",
        "representante", "etapa",
    ]

    for turn in history:
        combined = (turn.get("query", "") + " " + turn.get("answer", "")).lower()
        if any(kw.lower() in combined for kw in onboarding_keywords_in_history):
            return True

    # Verificar query atual
    onboarding_keywords_query = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in onboarding_keywords_query)
