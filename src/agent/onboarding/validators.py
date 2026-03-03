"""
Validação de formato inline (guard rail).

Estas validações são executadas ANTES de enviar ao BFA.
São "guard rails" básicos — se o formato está claramente errado,
o agente nem envia ao BFA (economia de latência).

O BFA faz validações de negócio mais profundas:
  - CNPJ único no sistema
  - Dígito verificador
  - Maior de 18 anos
  - etc.
"""

from __future__ import annotations

import re

from src.agent.onboarding.fields import OnboardingField


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
