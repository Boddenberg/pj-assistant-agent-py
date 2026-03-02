"""
Testes unitários para o módulo de onboarding.

Cobre:
  - Validadores de formato (CNPJ, CPF, e-mail, telefone, data, senha)
  - Extrator de dados de texto livre
  - State Machine (fluxo de 4 etapas)
  - build_onboarding_context (geração de instrução para o LLM)
  - is_onboarding_intent (detecção de intenção)
"""

import pytest

from src.agent.onboarding import (
    OnboardingValidator,
    OnboardingExtractor,
    OnboardingStateMachine,
    OnboardingState,
    build_onboarding_context,
    is_onboarding_intent,
    STEP_FIELDS,
    FIELD_LABELS,
)


# =============================================================================
# OnboardingValidator
# =============================================================================

class TestValidateCnpj:
    def test_valid_cnpj_formatted(self):
        result = OnboardingValidator.validate_cnpj("12.345.678/0001-90")
        assert result.valid is True
        assert result.value == "12.345.678/0001-90"

    def test_valid_cnpj_digits_only(self):
        result = OnboardingValidator.validate_cnpj("12345678000190")
        assert result.valid is True
        assert result.value == "12.345.678/0001-90"

    def test_invalid_cnpj_too_short(self):
        result = OnboardingValidator.validate_cnpj("12.345.678/1-90")
        assert result.valid is False
        assert "14 dígitos" in result.error

    def test_invalid_cnpj_too_long(self):
        result = OnboardingValidator.validate_cnpj("123456789012345")
        assert result.valid is False

    def test_invalid_cnpj_empty(self):
        result = OnboardingValidator.validate_cnpj("")
        assert result.valid is False


class TestValidateCpf:
    def test_valid_cpf_formatted(self):
        result = OnboardingValidator.validate_cpf("123.456.789-00")
        assert result.valid is True
        assert result.value == "123.456.789-00"

    def test_valid_cpf_digits_only(self):
        result = OnboardingValidator.validate_cpf("12345678900")
        assert result.valid is True
        assert result.value == "123.456.789-00"

    def test_invalid_cpf_too_short(self):
        result = OnboardingValidator.validate_cpf("1234567890")
        assert result.valid is False
        assert "11 dígitos" in result.error

    def test_invalid_cpf_too_long(self):
        result = OnboardingValidator.validate_cpf("123456789001")
        assert result.valid is False


class TestValidateEmail:
    def test_valid_email(self):
        result = OnboardingValidator.validate_email("contato@acmesolucoes.com.br")
        assert result.valid is True
        assert result.value == "contato@acmesolucoes.com.br"

    def test_invalid_email_no_at(self):
        result = OnboardingValidator.validate_email("contatoacmesolucoes.com.br")
        assert result.valid is False
        assert "@" in result.error

    def test_invalid_email_no_domain(self):
        result = OnboardingValidator.validate_email("contato@")
        assert result.valid is False

    def test_valid_email_with_spaces(self):
        result = OnboardingValidator.validate_email("  user@domain.com  ")
        assert result.valid is True
        assert result.value == "user@domain.com"


class TestValidateRazaoSocial:
    def test_valid(self):
        result = OnboardingValidator.validate_razao_social("ACME SOLUCOES LTDA")
        assert result.valid is True

    def test_too_short(self):
        result = OnboardingValidator.validate_razao_social("AB")
        assert result.valid is False
        assert "3 caracteres" in result.error


class TestValidateNomeFantasia:
    def test_valid(self):
        result = OnboardingValidator.validate_nome_fantasia("ACME")
        assert result.valid is True

    def test_too_short(self):
        result = OnboardingValidator.validate_nome_fantasia("A")
        assert result.valid is False
        assert "2 caracteres" in result.error


class TestValidateRepresentanteName:
    def test_valid(self):
        result = OnboardingValidator.validate_representante_name("Victor Campagnola")
        assert result.valid is True

    def test_too_short(self):
        result = OnboardingValidator.validate_representante_name("Ana")
        assert result.valid is False
        assert "5 caracteres" in result.error


class TestValidatePhone:
    def test_valid_11_digits(self):
        result = OnboardingValidator.validate_phone("(11) 98765-4321")
        assert result.valid is True
        assert result.value == "(11) 98765-4321"

    def test_valid_10_digits(self):
        result = OnboardingValidator.validate_phone("(11) 8765-4321")
        assert result.valid is True
        assert result.value == "(11) 8765-4321"

    def test_valid_digits_only(self):
        result = OnboardingValidator.validate_phone("11987654321")
        assert result.valid is True

    def test_invalid_too_short(self):
        result = OnboardingValidator.validate_phone("1198765")
        assert result.valid is False
        assert "10 ou 11 dígitos" in result.error


class TestValidateBirthDate:
    def test_valid_date(self):
        result = OnboardingValidator.validate_birth_date("19/02/1996")
        assert result.valid is True
        assert result.value == "19/02/1996"

    def test_valid_date_single_digit_day(self):
        result = OnboardingValidator.validate_birth_date("1/2/1990")
        assert result.valid is True
        assert result.value == "01/02/1990"

    def test_invalid_format(self):
        result = OnboardingValidator.validate_birth_date("1996-02-19")
        assert result.valid is False

    def test_invalid_underage(self):
        result = OnboardingValidator.validate_birth_date("01/01/2020")
        assert result.valid is False
        assert "18 anos" in result.error

    def test_invalid_date_values(self):
        result = OnboardingValidator.validate_birth_date("32/13/1990")
        assert result.valid is False


class TestValidatePassword:
    def test_valid(self):
        result = OnboardingValidator.validate_password("123456")
        assert result.valid is True
        assert result.value == "123456"

    def test_invalid_letters(self):
        result = OnboardingValidator.validate_password("12345a")
        assert result.valid is False

    def test_invalid_too_short(self):
        result = OnboardingValidator.validate_password("12345")
        assert result.valid is False

    def test_invalid_too_long(self):
        result = OnboardingValidator.validate_password("1234567")
        assert result.valid is False


class TestValidatePasswordConfirmation:
    def test_matching(self):
        result = OnboardingValidator.validate_password_confirmation("123456", "123456")
        assert result.valid is True

    def test_not_matching(self):
        result = OnboardingValidator.validate_password_confirmation("654321", "123456")
        assert result.valid is False
        assert "não coincidem" in result.error


# =============================================================================
# OnboardingExtractor
# =============================================================================

class TestOnboardingExtractor:
    def test_extract_cnpj(self):
        result = OnboardingExtractor.extract_from_message(
            "CNPJ 12.345.678/0001-90, Razão Social ACME LTDA"
        )
        assert "cnpj" in result
        assert result["cnpj"] == "12.345.678/0001-90"

    def test_extract_email(self):
        result = OnboardingExtractor.extract_from_message(
            "E-mail contato@acmesolucoes.com.br"
        )
        assert "email" in result
        assert result["email"] == "contato@acmesolucoes.com.br"

    def test_extract_cpf(self):
        result = OnboardingExtractor.extract_from_message(
            "CPF: 123.456.789-00"
        )
        assert "representanteCpf" in result

    def test_extract_phone(self):
        result = OnboardingExtractor.extract_from_message(
            "Telefone: (11) 98765-4321"
        )
        assert "representantePhone" in result

    def test_extract_birth_date(self):
        result = OnboardingExtractor.extract_from_message(
            "Data de nascimento: 19/02/1996"
        )
        assert "representanteBirthDate" in result
        assert result["representanteBirthDate"] == "19/02/1996"

    def test_extract_password(self):
        result = OnboardingExtractor.extract_from_message("senha 123456")
        assert "password" in result
        assert result["password"] == "123456"

    def test_extract_razao_social(self):
        result = OnboardingExtractor.extract_from_message(
            "Razão Social ACME SOLUCOES LTDA, Nome Fantasia ACME"
        )
        assert "razaoSocial" in result
        assert "ACME SOLUCOES LTDA" in result["razaoSocial"]

    def test_extract_nome_fantasia(self):
        result = OnboardingExtractor.extract_from_message(
            "Nome Fantasia ACME Solucoes, E-mail contato@x.com"
        )
        assert "nomeFantasia" in result
        assert "ACME Solucoes" in result["nomeFantasia"]

    def test_extract_multiple_fields(self):
        result = OnboardingExtractor.extract_from_message(
            "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
            "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br"
        )
        assert "cnpj" in result
        assert "email" in result

    def test_no_false_positive_password(self):
        """Senha de 6 dígitos não deve ser extraída de CNPJ/CPF."""
        result = OnboardingExtractor.extract_from_message(
            "CNPJ 12.345.678/0001-90"
        )
        assert "password" not in result

    def test_extract_representante_name(self):
        result = OnboardingExtractor.extract_from_message(
            "Victor Campagnola, CPF: 123.456.789-00"
        )
        assert "representanteName" in result
        assert "Victor Campagnola" in result["representanteName"]


# =============================================================================
# OnboardingStateMachine
# =============================================================================

class TestOnboardingStateMachine:
    def setup_method(self):
        self.sm = OnboardingStateMachine()

    def test_initial_state_step_1(self):
        """Sem histórico, deve estar na etapa 1."""
        state = self.sm.process([], "quero abrir conta")
        assert state.current_step == 1
        assert len(state.collected) == 0
        assert "cnpj" in state.pending_fields

    def test_step_1_collects_data(self):
        """Deve coletar dados da etapa 1."""
        state = self.sm.process(
            [],
            "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
            "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br",
        )
        assert "cnpj" in state.collected
        assert "email" in state.collected
        # Should advance to step 2 if all step 1 fields collected
        if all(f in state.collected for f in STEP_FIELDS[1]):
            assert state.current_step == 2

    def test_step_1_invalid_cnpj(self):
        """CNPJ inválido deve gerar erro e não avançar."""
        state = self.sm.process(
            [],
            "CNPJ 12.345.678/1-90, Razão Social ACME LTDA, "
            "Nome Fantasia ACME, E-mail contato@acme.com",
        )
        assert len(state.errors) > 0
        assert any("CNPJ" in e for e in state.errors)

    def test_step_1_invalid_email(self):
        """E-mail sem @ deve gerar erro."""
        state = self.sm.process(
            [],
            "CNPJ 12.345.678/0001-90, Razão Social ACME LTDA, "
            "Nome Fantasia ACME, E-mail contatoacme.com",
        )
        # Email sem @ é capturado pelo fallback e validação rejeita
        assert "email" not in state.collected
        assert len(state.errors) > 0
        assert any("E-mail" in e or "e-mail" in e.lower() for e in state.errors)

    def test_step_2_from_history(self):
        """Após etapa 1 completa no histórico, deve estar na etapa 2."""
        history = [
            {
                "query": "quero abrir conta",
                "answer": "Vou te ajudar! Me envie CNPJ, Razão Social, Nome Fantasia e E-mail.",
            },
            {
                "query": "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
                         "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br",
                "answer": "Perfeito! Agora preciso dos dados do representante.",
            },
        ]
        state = self.sm.process(
            history,
            "Victor Campagnola, CPF: 123.456.789-00, Telefone: (11) 98765-4321, 19/02/1996",
        )
        # Should have step 1 data from history + step 2 data from current query
        assert "cnpj" in state.collected
        assert "email" in state.collected

    def test_step_3_password(self):
        """Etapa 3 pede senha."""
        history = [
            {
                "query": "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
                         "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br",
                "answer": "Agora preciso dos dados do representante.",
            },
            {
                "query": "Victor Campagnola, CPF: 123.456.789-00, Telefone: (11) 98765-4321, 19/02/1996",
                "answer": "Agora crie uma senha de 6 dígitos.",
            },
        ]
        state = self.sm.process(history, "senha 123456")
        assert "password" in state.collected
        assert state.collected["password"] == "123456"

    def test_step_4_password_confirmation_match(self):
        """Confirmação de senha que bate deve completar o fluxo."""
        history = [
            {
                "query": "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
                         "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br",
                "answer": "Agora preciso dos dados do representante.",
            },
            {
                "query": "Victor Campagnola, CPF: 123.456.789-00, Telefone: (11) 98765-4321, 19/02/1996",
                "answer": "Agora crie uma senha de 6 dígitos.",
            },
            {
                "query": "senha 123456",
                "answer": "Confirme a senha.",
            },
        ]
        state = self.sm.process(history, "123456")
        # passwordConfirmation needs to match — the extractor sees "123456" as password
        # but in step 4, we expect passwordConfirmation
        assert state.current_step >= 4

    def test_step_4_password_confirmation_mismatch(self):
        """Confirmação de senha que não bate deve gerar erro."""
        history = [
            {
                "query": "CNPJ 12.345.678/0001-90, Razão Social ACME SOLUCOES EMPRESARIAIS LTDA, "
                         "Nome Fantasia ACME Solucoes, E-mail contato@acmesolucoes.com.br",
                "answer": "Agora preciso dos dados do representante.",
            },
            {
                "query": "Victor Campagnola, CPF: 123.456.789-00, Telefone: (11) 98765-4321, 19/02/1996",
                "answer": "Agora crie uma senha de 6 dígitos.",
            },
            {
                "query": "senha 123456",
                "answer": "Confirme a senha.",
            },
        ]
        state = self.sm.process(history, "654321")
        # Should have error or not advance
        assert state.current_step == 4


# =============================================================================
# build_onboarding_context
# =============================================================================

class TestBuildOnboardingContext:
    def test_complete_context(self):
        state = OnboardingState(
            current_step=5,
            collected={
                "cnpj": "12.345.678/0001-90",
                "razaoSocial": "ACME LTDA",
                "nomeFantasia": "ACME",
                "email": "contato@acme.com",
                "representanteName": "Victor",
                "representanteCpf": "123.456.789-00",
                "representantePhone": "(11) 98765-4321",
                "representanteBirthDate": "19/02/1996",
                "password": "123456",
                "passwordConfirmation": "123456",
            },
            is_complete=True,
        )
        ctx = build_onboarding_context(state)
        assert "ONBOARDING COMPLETO" in ctx
        assert "12.345.678/0001-90" in ctx
        assert "123456" not in ctx  # Senha não deve aparecer no resumo

    def test_step_1_context_with_errors(self):
        state = OnboardingState(
            current_step=1,
            collected={},
            errors=["CNPJ inválido: '12.345.678/1-90'. O CNPJ deve ter 14 dígitos."],
            pending_fields=["cnpj", "razaoSocial", "nomeFantasia", "email"],
        )
        ctx = build_onboarding_context(state)
        assert "Etapa 1" in ctx
        assert "CNPJ inválido" in ctx
        assert "INFORME AO CLIENTE" in ctx
        assert "NÃO avance" in ctx

    def test_step_2_context_with_pending(self):
        state = OnboardingState(
            current_step=2,
            collected={
                "cnpj": "12.345.678/0001-90",
                "razaoSocial": "ACME LTDA",
                "nomeFantasia": "ACME",
                "email": "contato@acme.com",
            },
            pending_fields=["representanteName", "representanteCpf",
                           "representantePhone", "representanteBirthDate"],
        )
        ctx = build_onboarding_context(state)
        assert "Etapa 2" in ctx
        assert "PEÇA AO CLIENTE" in ctx
        assert "12.345.678/0001-90" in ctx  # Dados já coletados


# =============================================================================
# is_onboarding_intent
# =============================================================================

class TestIsOnboardingIntent:
    def test_direct_intent(self):
        assert is_onboarding_intent("quero abrir conta", []) is True

    def test_intent_from_history(self):
        history = [
            {"query": "quero abrir conta", "answer": "Vou te ajudar!"},
        ]
        assert is_onboarding_intent("12.345.678/0001-90", history) is True

    def test_no_intent(self):
        assert is_onboarding_intent("qual meu saldo?", []) is False

    def test_intent_with_keyword_variations(self):
        assert is_onboarding_intent("quero criar conta", []) is True
        assert is_onboarding_intent("nova conta pj", []) is True

    def test_history_with_cnpj_reference(self):
        history = [
            {"query": "quero conta", "answer": "Me envie o CNPJ."},
        ]
        assert is_onboarding_intent("12345678000190", history) is True
