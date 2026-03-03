"""
Definição dos campos do onboarding — enum, sequência, templates e labels.

Este módulo centraliza TODAS as definições estáticas do fluxo de onboarding:
  - Quais campos existem (OnboardingField enum)
  - Em que ordem são pedidos (FIELD_SEQUENCE)
  - Quais são campos de dados vs controle (DATA_FIELDS)
  - Mensagens-template para cada campo (FIELD_PROMPTS)
  - Labels legíveis para exibição (FIELD_LABELS)
  - Dicas de formato para o cliente (FIELD_FORMAT_HINTS)

Para adicionar um novo campo ao onboarding:
  1. Adicionar à enum OnboardingField
  2. Inserir na posição correta em FIELD_SEQUENCE
  3. Adicionar template em FIELD_PROMPTS
  4. Adicionar label em FIELD_LABELS
  5. Adicionar hint em FIELD_FORMAT_HINTS
  6. Adicionar validação em validators.py
"""

from __future__ import annotations

from enum import Enum


# Máximo de tentativas por campo antes de desistir.
# O cliente terá MAX_RETRIES tentativas reais antes de ser bloqueado.
# Ex: MAX_RETRIES=3 → 3 tentativas (1ª + 2 retries) no inline path,
#     ou 3 rejeições do BFA + 4ª tentativa bloqueada no BFA path.
MAX_RETRIES = 3


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
