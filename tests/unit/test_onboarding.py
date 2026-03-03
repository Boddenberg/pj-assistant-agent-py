"""
Testes unitários — onboarding campo-a-campo (v9.0.0).

Arquitetura v9:
  O BFA (Go) envia history com `step` e `validated` por turno.
  O agente lê esses campos para saber onde parou — não conta turnos.

  Cada turno no history:
    { "query": "...", "answer": "...", "step": "cnpj", "validated": true }

  O agente retorna:
    step      → step que o cliente respondeu
    next_step → próximo step a ser pedido
"""

import pytest
from src.agent.onboarding import (
    OnboardingField,
    OnboardingState,
    FIELD_SEQUENCE,
    DATA_FIELDS,
    FIELD_PROMPTS,
    FIELD_LABELS,
    FIELD_FORMAT_HINTS,
    MAX_RETRIES,
    determine_current_field,
    build_onboarding_context,
    build_onboarding_response,
    validate_field_format,
    is_onboarding_intent,
)


# =============================================================================
# Helpers — history com step + validated (v9)
# =============================================================================

def _make_enriched_history(n_validated_fields: int) -> list[dict]:
    """
    Cria histórico enriquecido com n_validated_fields campos validados.

    Cada turno tem step + validated = True.
    """
    history: list[dict] = []

    # Turno 0 — welcome (sem step, não é campo de dados)
    history.append({
        "query": "Quero abrir minha conta PJ",
        "answer": "Vamos lá!",
        "step": None,
        "validated": None,
    })

    field_values = [
        ("12.345.678/0001-99", "cnpj"),
        ("Empresa Teste LTDA", "razaoSocial"),
        ("Empresa Teste", "nomeFantasia"),
        ("contato@empresa.com", "email"),
        ("João da Silva Santos", "representanteName"),
        ("123.456.789-00", "representanteCpf"),
        ("(11) 99999-8888", "representantePhone"),
        ("15/03/1990", "representanteBirthDate"),
        ("123456", "password"),
        ("123456", "passwordConfirmation"),
    ]

    for i in range(min(n_validated_fields, len(field_values))):
        value, step = field_values[i]
        history.append({
            "query": value,
            "answer": f"Campo {step} recebido! ✅",
            "step": step,
            "validated": True,
        })

    return history


# =============================================================================
# TestOnboardingField — enum e sequência
# =============================================================================

class TestOnboardingField:
    """Testes da enum OnboardingField e constantes relacionadas."""

    def test_field_count(self):
        """São 12 membros no enum (welcome + 10 dados + completed)."""
        assert len(OnboardingField) == 12

    def test_field_sequence_order(self):
        """A sequência começa com WELCOME e termina com COMPLETED."""
        assert FIELD_SEQUENCE[0] == OnboardingField.WELCOME
        assert FIELD_SEQUENCE[-1] == OnboardingField.COMPLETED

    def test_data_fields_exclude_welcome_and_completed(self):
        """DATA_FIELDS tem 10 campos (sem welcome e completed)."""
        assert len(DATA_FIELDS) == 10
        assert OnboardingField.WELCOME not in DATA_FIELDS
        assert OnboardingField.COMPLETED not in DATA_FIELDS

    def test_data_fields_in_correct_order(self):
        """DATA_FIELDS segue a ordem: CNPJ → ... → PASSWORD_CONFIRMATION."""
        assert DATA_FIELDS[0] == OnboardingField.CNPJ
        assert DATA_FIELDS[-1] == OnboardingField.PASSWORD_CONFIRMATION

    def test_every_data_field_has_prompt(self):
        """Cada campo de dados deve ter um template de prompt."""
        for field in DATA_FIELDS:
            assert field in FIELD_PROMPTS, f"{field.value} missing from FIELD_PROMPTS"

    def test_welcome_has_prompt(self):
        """Welcome também tem prompt."""
        assert OnboardingField.WELCOME in FIELD_PROMPTS

    def test_every_data_field_has_format_hint(self):
        """Cada campo de dados deve ter dica de formato."""
        for field in DATA_FIELDS:
            assert field in FIELD_FORMAT_HINTS, f"{field.value} missing from FIELD_FORMAT_HINTS"

    def test_label_fields(self):
        """Labels existem para os campos que aparecem no resumo final."""
        for field in [
            OnboardingField.CNPJ,
            OnboardingField.RAZAO_SOCIAL,
            OnboardingField.NOME_FANTASIA,
            OnboardingField.EMAIL,
            OnboardingField.REPRESENTANTE_NAME,
            OnboardingField.REPRESENTANTE_CPF,
            OnboardingField.REPRESENTANTE_PHONE,
            OnboardingField.REPRESENTANTE_BIRTH_DATE,
        ]:
            assert field in FIELD_LABELS, f"{field.value} missing from FIELD_LABELS"

    def test_max_retries_is_positive(self):
        """MAX_RETRIES deve ser um número positivo."""
        assert MAX_RETRIES > 0
        assert MAX_RETRIES == 3


# =============================================================================
# TestDetermineCurrentField — state machine (v9 enriched history)
# =============================================================================

class TestDetermineCurrentField:
    """Testes da função determine_current_field com history enriquecido."""

    def test_empty_history_returns_welcome(self):
        """Sem histórico → WELCOME (primeira interação)."""
        state = determine_current_field([], "Quero abrir conta")
        assert state.step == OnboardingField.WELCOME
        assert state.next_step == OnboardingField.WELCOME
        assert state.field_value == "Quero abrir conta"
        assert not state.is_complete
        assert not state.has_validation_error

    def test_after_welcome_asks_cnpj(self):
        """Após welcome (turno sem step), cliente responde CNPJ."""
        history = _make_enriched_history(0)  # só welcome
        state = determine_current_field(history, "12.345.678/0001-99")
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.RAZAO_SOCIAL
        assert state.field_value == "12.345.678/0001-99"

    def test_after_cnpj_validated_asks_razao_social(self):
        """Após CNPJ validado, próximo é Razão Social."""
        history = _make_enriched_history(1)  # CNPJ validated
        state = determine_current_field(history, "Empresa Teste LTDA")
        assert state.step == OnboardingField.RAZAO_SOCIAL
        assert state.next_step == OnboardingField.NOME_FANTASIA

    def test_after_razao_social_asks_nome_fantasia(self):
        """Após Razão Social validada, próximo é Nome Fantasia."""
        history = _make_enriched_history(2)
        state = determine_current_field(history, "Empresa Teste")
        assert state.step == OnboardingField.NOME_FANTASIA
        assert state.next_step == OnboardingField.EMAIL

    def test_after_nome_fantasia_asks_email(self):
        """Após Nome Fantasia validado, próximo é Email."""
        history = _make_enriched_history(3)
        state = determine_current_field(history, "contato@empresa.com")
        assert state.step == OnboardingField.EMAIL
        assert state.next_step == OnboardingField.REPRESENTANTE_NAME

    def test_after_email_asks_representante_name(self):
        """Após Email validado, próximo é nome do representante."""
        history = _make_enriched_history(4)
        state = determine_current_field(history, "João da Silva Santos")
        assert state.step == OnboardingField.REPRESENTANTE_NAME
        assert state.next_step == OnboardingField.REPRESENTANTE_CPF

    def test_after_name_asks_cpf(self):
        """Após nome validado, próximo é CPF."""
        history = _make_enriched_history(5)
        state = determine_current_field(history, "123.456.789-00")
        assert state.step == OnboardingField.REPRESENTANTE_CPF
        assert state.next_step == OnboardingField.REPRESENTANTE_PHONE

    def test_after_cpf_asks_phone(self):
        """Após CPF validado, próximo é telefone."""
        history = _make_enriched_history(6)
        state = determine_current_field(history, "(11) 99999-8888")
        assert state.step == OnboardingField.REPRESENTANTE_PHONE
        assert state.next_step == OnboardingField.REPRESENTANTE_BIRTH_DATE

    def test_after_phone_asks_birth_date(self):
        """Após telefone validado, próximo é data de nascimento."""
        history = _make_enriched_history(7)
        state = determine_current_field(history, "15/03/1990")
        assert state.step == OnboardingField.REPRESENTANTE_BIRTH_DATE
        assert state.next_step == OnboardingField.PASSWORD

    def test_after_birth_date_asks_password(self):
        """Após data nascimento validada, próximo é senha."""
        history = _make_enriched_history(8)
        state = determine_current_field(history, "123456")
        assert state.step == OnboardingField.PASSWORD
        assert state.next_step == OnboardingField.PASSWORD_CONFIRMATION

    def test_after_password_asks_confirmation(self):
        """Após senha validada, próximo é confirmação."""
        history = _make_enriched_history(9)
        state = determine_current_field(history, "123456")
        assert state.step == OnboardingField.PASSWORD_CONFIRMATION
        assert state.next_step == OnboardingField.COMPLETED

    def test_all_fields_validated_returns_completed(self):
        """Após todos 10 campos validados → COMPLETED."""
        history = _make_enriched_history(10)
        state = determine_current_field(history, "pronto")
        assert state.step == OnboardingField.COMPLETED
        assert state.next_step == OnboardingField.COMPLETED
        assert state.is_complete is True

    def test_collected_tracks_validated_fields(self):
        """Campos validados devem ser rastreados no collected."""
        history = _make_enriched_history(3)  # CNPJ, razaoSocial, nomeFantasia
        state = determine_current_field(history, "contato@empresa.com")
        # Validated fields from history
        assert OnboardingField.CNPJ.value in state.collected
        assert OnboardingField.RAZAO_SOCIAL.value in state.collected
        assert OnboardingField.NOME_FANTASIA.value in state.collected
        # Current field also collected (format valid)
        assert OnboardingField.EMAIL.value in state.collected
        assert state.collected[OnboardingField.CNPJ.value] == "12.345.678/0001-99"
        assert state.collected[OnboardingField.EMAIL.value] == "contato@empresa.com"

    def test_field_value_captures_current_query(self):
        """field_value deve ser a query atual (valor cru do campo)."""
        history = _make_enriched_history(2)
        state = determine_current_field(history, "Minha Empresa Legal")
        assert state.field_value == "Minha Empresa Legal"

    def test_history_with_unknown_step_ignored(self):
        """Turnos com step desconhecido devem ser ignorados."""
        history = [
            {"query": "oi", "answer": "olá", "step": "unknown_field", "validated": True},
        ]
        state = determine_current_field(history, "12345678000199")
        # Unknown step ignored → still at CNPJ
        assert state.step == OnboardingField.CNPJ


# =============================================================================
# TestDetermineCurrentField — BFA validation_error
# =============================================================================

class TestDetermineCurrentFieldValidationError:
    """Testes de reenvio quando o BFA rejeita um campo (validated=False)."""

    def test_bfa_validation_error_repeats_field(self):
        """Se BFA enviou validation_error, repetir o campo rejeitado."""
        history = _make_enriched_history(0)  # welcome only
        state = determine_current_field(
            history,
            "12345",
            validation_error="CNPJ inválido: deve ter 14 dígitos",
        )
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.CNPJ
        assert state.has_validation_error is True
        assert state.validation_error == "CNPJ inválido: deve ter 14 dígitos"

    def test_bfa_rejects_after_one_validated(self):
        """BFA rejeita o segundo campo (razaoSocial) → repetir."""
        history = _make_enriched_history(1)  # CNPJ validated
        state = determine_current_field(
            history,
            "AB",
            validation_error="Razão Social: mínimo 3 caracteres",
        )
        assert state.step == OnboardingField.RAZAO_SOCIAL
        assert state.next_step == OnboardingField.RAZAO_SOCIAL
        assert state.has_validation_error is True
        # CNPJ still in collected
        assert OnboardingField.CNPJ.value in state.collected

    def test_bfa_rejects_password(self):
        """BFA rejeita senha → repetir PASSWORD."""
        history = _make_enriched_history(8)  # up to birth date validated
        state = determine_current_field(
            history,
            "abc",
            validation_error="Senha deve ter 6 dígitos numéricos",
        )
        assert state.step == OnboardingField.PASSWORD
        assert state.has_validation_error is True

    def test_no_validation_error_advances(self):
        """Sem validation_error, o fluxo avança normalmente."""
        history = _make_enriched_history(1)  # CNPJ validated
        state = determine_current_field(history, "Empresa LTDA")
        assert state.step == OnboardingField.RAZAO_SOCIAL
        assert state.next_step == OnboardingField.NOME_FANTASIA
        assert state.has_validation_error is False

    def test_validated_false_in_history_counts_as_retry(self):
        """Turnos com validated=False no history contam como retries."""
        history = [
            {"query": "oi", "answer": "olá", "step": None, "validated": None},
            {"query": "123", "answer": "inválido", "step": "cnpj", "validated": False},
            {"query": "456", "answer": "inválido", "step": "cnpj", "validated": False},
        ]
        state = determine_current_field(history, "12345678000199")
        # 2 retries from history, but valid format now → should advance
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.RAZAO_SOCIAL
        assert state.has_validation_error is False
        assert state.retry_count == 0  # reset since format valid


# =============================================================================
# TestRetryLimit — max retries exceeded
# =============================================================================

class TestRetryLimit:
    """Testes do limite de retries por campo."""

    def test_max_retries_exceeded_via_bfa(self):
        """Após MAX_RETRIES validated=False, agente encerra."""
        history = [
            {"query": "oi", "answer": "olá", "step": None, "validated": None},
        ]
        # Add MAX_RETRIES failed attempts
        for i in range(MAX_RETRIES):
            history.append({
                "query": f"tentativa_{i}",
                "answer": "inválido",
                "step": "cnpj",
                "validated": False,
            })

        state = determine_current_field(
            history,
            "outra tentativa",
            validation_error="CNPJ ainda inválido",
        )
        assert state.max_retries_exceeded is True
        assert state.has_validation_error is True
        assert state.step == OnboardingField.CNPJ

    def test_max_retries_exceeded_response(self):
        """Resposta de max retries deve ser amigável."""
        state = OnboardingState(
            step=OnboardingField.CNPJ,
            next_step=OnboardingField.CNPJ,
            has_validation_error=True,
            validation_error="Limite excedido",
            retry_count=MAX_RETRIES,
            max_retries_exceeded=True,
        )
        resp = build_onboarding_response(state)
        assert "CNPJ" in resp
        assert "abrir conta" in resp.lower()
        assert "😕" in resp

    def test_inline_validation_counts_toward_retry_limit(self):
        """Validação inline de formato também conta como retry."""
        history = [
            {"query": "oi", "answer": "olá", "step": None, "validated": None},
            {"query": "123", "answer": "err", "step": "cnpj", "validated": False},
            {"query": "456", "answer": "err", "step": "cnpj", "validated": False},
        ]
        # 2 retries from history. Now inline validation fails → 3rd retry → MAX
        state = determine_current_field(history, "abc")  # invalid CNPJ format
        assert state.max_retries_exceeded is True
        assert state.has_validation_error is True

    def test_retries_reset_after_validated(self):
        """Retries resetam quando um campo é validado com sucesso."""
        history = [
            {"query": "oi", "answer": "olá", "step": None, "validated": None},
            {"query": "123", "answer": "err", "step": "cnpj", "validated": False},
            {"query": "456", "answer": "err", "step": "cnpj", "validated": False},
            {"query": "12345678000199", "answer": "ok", "step": "cnpj", "validated": True},
        ]
        # CNPJ validated → retry count reset → razaoSocial starts fresh
        state = determine_current_field(history, "AB")
        # "AB" fails inline validation → 1 retry (not 3)
        assert state.retry_count == 1
        assert state.max_retries_exceeded is False

    def test_under_max_retries_still_asks(self):
        """Abaixo do limite, agente pede o campo de novo normalmente."""
        history = [
            {"query": "oi", "answer": "olá", "step": None, "validated": None},
            {"query": "123", "answer": "err", "step": "cnpj", "validated": False},
        ]
        state = determine_current_field(
            history,
            "456",
            validation_error="CNPJ inválido",
        )
        # 1 from history + 1 from validation_error = 2 < MAX_RETRIES(3)
        assert state.max_retries_exceeded is False
        assert state.has_validation_error is True
        assert state.retry_count == 2


# =============================================================================
# TestBuildOnboardingContext — geração de instrução para o LLM (legado)
# =============================================================================

class TestBuildOnboardingContext:
    """Testes da função build_onboarding_context."""

    def test_welcome_context(self):
        """Welcome: gera instrução com prompt de boas-vindas."""
        state = OnboardingState(
            step=OnboardingField.WELCOME,
            next_step=OnboardingField.WELCOME,
            field_value="Quero abrir conta",
        )
        ctx = build_onboarding_context(state)
        assert "[INSTRUÇÃO DE ONBOARDING" in ctx
        assert "CNPJ" in ctx
        assert "search_knowledge_base" in ctx

    def test_normal_field_context(self):
        """Campo normal: LLM recebe instrução para pedir o PRÓXIMO campo."""
        state = OnboardingState(
            step=OnboardingField.RAZAO_SOCIAL,
            next_step=OnboardingField.NOME_FANTASIA,
            collected={
                OnboardingField.CNPJ.value: "12.345.678/0001-99",
                OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            },
            field_value="Empresa Teste LTDA",
        )
        ctx = build_onboarding_context(state)
        assert "Nome Fantasia" in ctx
        assert "SOMENTE" in ctx

    def test_validation_error_context(self):
        """Erro de validação: gera instrução com erro e dica de formato."""
        state = OnboardingState(
            step=OnboardingField.CNPJ,
            next_step=OnboardingField.CNPJ,
            has_validation_error=True,
            validation_error="CNPJ deve ter 14 dígitos",
            field_value="123",
        )
        ctx = build_onboarding_context(state)
        assert "rejeitado" in ctx.lower() or "⚠️" in ctx
        assert "CNPJ deve ter 14 dígitos" in ctx
        assert FIELD_FORMAT_HINTS[OnboardingField.CNPJ] in ctx

    def test_completed_context(self):
        """Completo: gera resumo sem a senha."""
        collected = {
            OnboardingField.CNPJ.value: "12.345.678/0001-99",
            OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            OnboardingField.NOME_FANTASIA.value: "Empresa Teste",
            OnboardingField.EMAIL.value: "contato@empresa.com",
            OnboardingField.REPRESENTANTE_NAME.value: "João da Silva",
            OnboardingField.REPRESENTANTE_CPF.value: "123.456.789-00",
            OnboardingField.REPRESENTANTE_PHONE.value: "(11) 99999-8888",
            OnboardingField.REPRESENTANTE_BIRTH_DATE.value: "15/03/1990",
            OnboardingField.PASSWORD.value: "123456",
            OnboardingField.PASSWORD_CONFIRMATION.value: "123456",
        }
        state = OnboardingState(
            step=OnboardingField.PASSWORD_CONFIRMATION,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        ctx = build_onboarding_context(state)
        assert "COMPLETO" in ctx or "✅" in ctx
        assert "12.345.678/0001-99" in ctx
        assert "João da Silva" in ctx
        assert "123456" not in ctx  # senha NÃO deve aparecer

    def test_completed_context_excludes_password_fields(self):
        """No resumo final, PASSWORD e PASSWORD_CONFIRMATION não aparecem."""
        collected = {f.value: f"valor_{f.value}" for f in DATA_FIELDS}
        state = OnboardingState(
            step=OnboardingField.PASSWORD_CONFIRMATION,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        ctx = build_onboarding_context(state)
        assert "CNPJ" in ctx
        assert "E-mail" in ctx
        assert "valor_password" not in ctx
        assert "valor_passwordConfirmation" not in ctx

    def test_context_always_has_no_search_instruction(self):
        """Toda instrução deve dizer para NÃO chamar search_knowledge_base."""
        pairs = [
            (OnboardingField.WELCOME, OnboardingField.WELCOME),
            (OnboardingField.CNPJ, OnboardingField.RAZAO_SOCIAL),
            (OnboardingField.EMAIL, OnboardingField.REPRESENTANTE_NAME),
        ]
        for step, nxt in pairs:
            state = OnboardingState(
                step=step,
                next_step=nxt,
                field_value="qualquer",
            )
            ctx = build_onboarding_context(state)
            assert "search_knowledge_base" in ctx


# =============================================================================
# TestBuildOnboardingResponse — resposta determinística (sem LLM)
# =============================================================================

class TestBuildOnboardingResponse:
    """Testes da função build_onboarding_response (v9 — bypass do LLM)."""

    def test_welcome_response(self):
        """Welcome: retorna template de boas-vindas pedindo CNPJ."""
        state = OnboardingState(
            step=OnboardingField.WELCOME,
            next_step=OnboardingField.WELCOME,
            field_value="Quero abrir conta",
        )
        resp = build_onboarding_response(state)
        assert "CNPJ" in resp
        assert "passo a passo" in resp.lower() or "guiar" in resp.lower()

    def test_normal_field_uses_template(self):
        """Campo normal: resposta É o template de FIELD_PROMPTS do next_step."""
        state = OnboardingState(
            step=OnboardingField.CNPJ,
            next_step=OnboardingField.RAZAO_SOCIAL,
            collected={OnboardingField.CNPJ.value: "12.345.678/0001-99"},
            field_value="12.345.678/0001-99",
        )
        resp = build_onboarding_response(state)
        assert resp == FIELD_PROMPTS[OnboardingField.RAZAO_SOCIAL]

    def test_nome_fantasia_to_email_response(self):
        """Caso que causava alucinação: Nome Fantasia → Email."""
        state = OnboardingState(
            step=OnboardingField.NOME_FANTASIA,
            next_step=OnboardingField.EMAIL,
            collected={
                OnboardingField.CNPJ.value: "87382356000115",
                OnboardingField.RAZAO_SOCIAL.value: "Kasjsjskaja",
                OnboardingField.NOME_FANTASIA.value: "Uauauahaha",
            },
            field_value="Uauauahaha",
        )
        resp = build_onboarding_response(state)
        assert "Nome Fantasia recebido" in resp
        assert "e-mail" in resp.lower()
        assert "telefone" not in resp.lower()

    def test_each_field_transition_uses_correct_template(self):
        """Cada transição de campo deve usar o template correto."""
        for i, field in enumerate(DATA_FIELDS):
            if i + 1 < len(DATA_FIELDS):
                next_field = DATA_FIELDS[i + 1]
            else:
                next_field = OnboardingField.COMPLETED
            state = OnboardingState(
                step=field,
                next_step=next_field,
                collected={field.value: "valor_qualquer"},
                is_complete=(next_field == OnboardingField.COMPLETED),
                field_value="valor_qualquer",
            )
            resp = build_onboarding_response(state)
            if next_field == OnboardingField.COMPLETED:
                assert "✅" in resp
            else:
                expected_template = FIELD_PROMPTS[next_field]
                assert resp == expected_template, (
                    f"Transition {field.value} → {next_field.value}: "
                    f"expected template for {next_field.value}"
                )

    def test_validation_error_response(self):
        """Erro de validação: mensagem amigável com motivo e dica."""
        state = OnboardingState(
            step=OnboardingField.CNPJ,
            next_step=OnboardingField.CNPJ,
            has_validation_error=True,
            validation_error="CNPJ deve ter 14 dígitos",
            field_value="123",
        )
        resp = build_onboarding_response(state)
        assert "⚠️" in resp
        assert "CNPJ" in resp
        assert "14 dígitos" in resp
        assert "novamente" in resp.lower()

    def test_validation_error_includes_hint(self):
        """Erro de validação deve incluir dica de formato."""
        state = OnboardingState(
            step=OnboardingField.EMAIL,
            next_step=OnboardingField.EMAIL,
            has_validation_error=True,
            validation_error="Email inválido",
            field_value="invalido",
        )
        resp = build_onboarding_response(state)
        assert "contato@empresa.com" in resp

    def test_completed_response(self):
        """Completo: mostra resumo sem a senha."""
        collected = {
            OnboardingField.CNPJ.value: "12.345.678/0001-99",
            OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            OnboardingField.NOME_FANTASIA.value: "Empresa Teste",
            OnboardingField.EMAIL.value: "contato@empresa.com",
            OnboardingField.REPRESENTANTE_NAME.value: "João da Silva",
            OnboardingField.REPRESENTANTE_CPF.value: "123.456.789-00",
            OnboardingField.REPRESENTANTE_PHONE.value: "(11) 99999-8888",
            OnboardingField.REPRESENTANTE_BIRTH_DATE.value: "15/03/1990",
            OnboardingField.PASSWORD.value: "123456",
            OnboardingField.PASSWORD_CONFIRMATION.value: "123456",
        }
        state = OnboardingState(
            step=OnboardingField.PASSWORD_CONFIRMATION,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        resp = build_onboarding_response(state)
        assert "✅" in resp
        assert "12.345.678/0001-99" in resp
        assert "João da Silva" in resp
        assert "123456" not in resp

    def test_completed_response_excludes_password_fields(self):
        """No resumo, PASSWORD e PASSWORD_CONFIRMATION não aparecem."""
        collected = {f.value: f"valor_{f.value}" for f in DATA_FIELDS}
        state = OnboardingState(
            step=OnboardingField.PASSWORD_CONFIRMATION,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        resp = build_onboarding_response(state)
        assert "valor_password" not in resp
        assert "valor_passwordConfirmation" not in resp

    def test_response_is_deterministic(self):
        """Mesma entrada → mesma saída, sempre."""
        state = OnboardingState(
            step=OnboardingField.RAZAO_SOCIAL,
            next_step=OnboardingField.NOME_FANTASIA,
            collected={
                OnboardingField.CNPJ.value: "12345678000199",
                OnboardingField.RAZAO_SOCIAL.value: "Teste",
            },
            field_value="Teste",
        )
        resp1 = build_onboarding_response(state)
        resp2 = build_onboarding_response(state)
        assert resp1 == resp2

    def test_max_retries_exceeded_response(self):
        """Resposta de max retries deve ser amigável e sugerir recomeçar."""
        state = OnboardingState(
            step=OnboardingField.EMAIL,
            next_step=OnboardingField.EMAIL,
            has_validation_error=True,
            validation_error="Email inválido",
            max_retries_exceeded=True,
            retry_count=MAX_RETRIES,
        )
        resp = build_onboarding_response(state)
        assert "E-mail" in resp  # label do campo
        assert "abrir conta" in resp.lower()
        assert "😕" in resp


# =============================================================================
# TestValidateFieldFormat — validação inline de formato
# =============================================================================

class TestValidateFieldFormat:
    """Testes da função validate_field_format."""

    # --- CNPJ ---
    @pytest.mark.parametrize("value", [
        "12345678000199",
        "12.345.678/0001-99",
        "11222333000181",
    ])
    def test_cnpj_valid(self, value):
        assert validate_field_format(OnboardingField.CNPJ, value) is None

    @pytest.mark.parametrize("value,expected_digits", [
        ("123456", 6),
        ("123", 3),
        ("1234567890", 10),
        ("abc", 0),
    ])
    def test_cnpj_invalid(self, value, expected_digits):
        error = validate_field_format(OnboardingField.CNPJ, value)
        assert error is not None
        assert "14 dígitos" in error
        assert str(expected_digits) in error

    # --- Razão Social ---
    def test_razao_social_valid(self):
        assert validate_field_format(OnboardingField.RAZAO_SOCIAL, "Empresa LTDA") is None

    def test_razao_social_too_short(self):
        error = validate_field_format(OnboardingField.RAZAO_SOCIAL, "AB")
        assert error is not None
        assert "3 caracteres" in error

    # --- Nome Fantasia ---
    def test_nome_fantasia_valid(self):
        assert validate_field_format(OnboardingField.NOME_FANTASIA, "MF") is None

    def test_nome_fantasia_too_short(self):
        error = validate_field_format(OnboardingField.NOME_FANTASIA, "A")
        assert error is not None
        assert "2 caracteres" in error

    # --- Email ---
    @pytest.mark.parametrize("value", [
        "contato@empresa.com",
        "teste@empresa.com.br",
        "a@b.co",
    ])
    def test_email_valid(self, value):
        assert validate_field_format(OnboardingField.EMAIL, value) is None

    @pytest.mark.parametrize("value", [
        "email-sem-arroba",
        "email@",
        "@semdominio",
        "teste@dominio",
    ])
    def test_email_invalid(self, value):
        error = validate_field_format(OnboardingField.EMAIL, value)
        assert error is not None
        assert "@" in error

    # --- Representante Name ---
    def test_representante_name_valid(self):
        assert validate_field_format(OnboardingField.REPRESENTANTE_NAME, "João da Silva") is None

    def test_representante_name_too_short(self):
        error = validate_field_format(OnboardingField.REPRESENTANTE_NAME, "João")
        assert error is not None
        assert "5 caracteres" in error

    # --- CPF ---
    @pytest.mark.parametrize("value", [
        "12345678901",
        "123.456.789-01",
    ])
    def test_cpf_valid(self, value):
        assert validate_field_format(OnboardingField.REPRESENTANTE_CPF, value) is None

    def test_cpf_invalid(self):
        error = validate_field_format(OnboardingField.REPRESENTANTE_CPF, "123456")
        assert error is not None
        assert "11 dígitos" in error

    # --- Phone ---
    @pytest.mark.parametrize("value", [
        "(11) 99999-8888",
        "11999998888",
        "(11) 3333-4444",
    ])
    def test_phone_valid(self, value):
        assert validate_field_format(OnboardingField.REPRESENTANTE_PHONE, value) is None

    def test_phone_invalid(self):
        error = validate_field_format(OnboardingField.REPRESENTANTE_PHONE, "12345")
        assert error is not None
        assert "10 dígitos" in error

    # --- Birth Date ---
    @pytest.mark.parametrize("value", [
        "15/03/1990",
        "01-12-2000",
        "28.02.1985",
    ])
    def test_birth_date_valid(self, value):
        assert validate_field_format(OnboardingField.REPRESENTANTE_BIRTH_DATE, value) is None

    @pytest.mark.parametrize("value", [
        "1990-03-15",
        "15/03",
        "nascimento",
    ])
    def test_birth_date_invalid(self, value):
        error = validate_field_format(OnboardingField.REPRESENTANTE_BIRTH_DATE, value)
        assert error is not None
        assert "DD/MM/AAAA" in error

    # --- Password ---
    def test_password_valid(self):
        assert validate_field_format(OnboardingField.PASSWORD, "123456") is None

    @pytest.mark.parametrize("value", [
        "12345",
        "1234567",
        "abcdef",
        "12345a",
    ])
    def test_password_invalid(self, value):
        error = validate_field_format(OnboardingField.PASSWORD, value)
        assert error is not None
        assert "6 dígitos" in error

    # --- Password Confirmation ---
    def test_password_confirmation_valid(self):
        assert validate_field_format(OnboardingField.PASSWORD_CONFIRMATION, "123456") is None

    def test_password_confirmation_invalid(self):
        error = validate_field_format(OnboardingField.PASSWORD_CONFIRMATION, "abc")
        assert error is not None
        assert "6 dígitos" in error


# =============================================================================
# TestInlineValidationRetry — retry de campo rejeitado inline
# =============================================================================

class TestInlineValidationRetry:
    """Testes de retry quando a validação inline rejeita um campo."""

    def test_cnpj_invalid_triggers_retry(self):
        """CNPJ inválido deve ser rejeitado e pedir CNPJ de novo."""
        history = [
            {"query": "Quero abrir conta", "answer": "Vamos lá!", "step": None, "validated": None},
        ]
        state = determine_current_field(history, "123456")
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.CNPJ
        assert state.has_validation_error is True
        assert "14 dígitos" in state.validation_error

    def test_cnpj_valid_after_inline_retry(self):
        """CNPJ válido após retry inline deve avançar."""
        history = [
            {"query": "Quero abrir conta", "answer": "Vamos lá!", "step": None, "validated": None},
            {"query": "123456", "answer": "⚠️ CNPJ inválido", "step": "cnpj", "validated": False},
        ]
        state = determine_current_field(history, "12345678000199")
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.RAZAO_SOCIAL
        assert state.has_validation_error is False

    def test_email_invalid_triggers_retry(self):
        """Email inválido deve pedir email de novo."""
        history = _make_enriched_history(3)
        state = determine_current_field(history, "email-invalido")
        assert state.step == OnboardingField.EMAIL
        assert state.next_step == OnboardingField.EMAIL
        assert state.has_validation_error is True
        assert "@" in state.validation_error

    def test_email_valid_after_retry(self):
        """Email válido após retry deve avançar para representante."""
        history = _make_enriched_history(3)
        # Add failed attempt
        history.append({
            "query": "invalido",
            "answer": "⚠️ E-mail inválido",
            "step": "email",
            "validated": False,
        })
        state = determine_current_field(history, "contato@empresa.com")
        assert state.step == OnboardingField.EMAIL
        assert state.next_step == OnboardingField.REPRESENTANTE_NAME
        assert state.has_validation_error is False

    def test_full_flow_with_retries(self):
        """Fluxo completo com retries em CNPJ e Email."""
        h: list[dict] = []

        # 1. Welcome
        state = determine_current_field(h, "Quero abrir conta")
        r = build_onboarding_response(state)
        h.append({"query": "Quero abrir conta", "answer": r, "step": None, "validated": None})

        # 2. CNPJ inválido
        state = determine_current_field(h, "abc")
        r = build_onboarding_response(state)
        assert state.has_validation_error
        h.append({"query": "abc", "answer": r, "step": "cnpj", "validated": False})

        # 3. CNPJ válido
        state = determine_current_field(h, "12345678000199")
        r = build_onboarding_response(state)
        assert state.step == OnboardingField.CNPJ
        assert state.next_step == OnboardingField.RAZAO_SOCIAL
        h.append({"query": "12345678000199", "answer": r, "step": "cnpj", "validated": True})

        # 4. Razão Social
        state = determine_current_field(h, "Empresa LTDA")
        r = build_onboarding_response(state)
        assert state.step == OnboardingField.RAZAO_SOCIAL
        h.append({"query": "Empresa LTDA", "answer": r, "step": "razaoSocial", "validated": True})

        # 5. Nome Fantasia
        state = determine_current_field(h, "Empresa")
        r = build_onboarding_response(state)
        assert state.step == OnboardingField.NOME_FANTASIA
        h.append({"query": "Empresa", "answer": r, "step": "nomeFantasia", "validated": True})

        # 6. Email inválido
        state = determine_current_field(h, "sem-arroba")
        r = build_onboarding_response(state)
        assert state.has_validation_error
        h.append({"query": "sem-arroba", "answer": r, "step": "email", "validated": False})

        # 7. Email válido
        state = determine_current_field(h, "contato@empresa.com")
        r = build_onboarding_response(state)
        assert state.step == OnboardingField.EMAIL
        assert state.next_step == OnboardingField.REPRESENTANTE_NAME
        h.append({"query": "contato@empresa.com", "answer": r, "step": "email", "validated": True})

        # Continuar sem erros
        remaining = [
            ("João da Silva Santos", OnboardingField.REPRESENTANTE_NAME, "representanteName"),
            ("12345678901", OnboardingField.REPRESENTANTE_CPF, "representanteCpf"),
            ("11999998888", OnboardingField.REPRESENTANTE_PHONE, "representantePhone"),
            ("15/03/1990", OnboardingField.REPRESENTANTE_BIRTH_DATE, "representanteBirthDate"),
            ("123456", OnboardingField.PASSWORD, "password"),
            ("123456", OnboardingField.PASSWORD_CONFIRMATION, "passwordConfirmation"),
        ]
        for value, expected_field, step_str in remaining:
            state = determine_current_field(h, value)
            r = build_onboarding_response(state)
            assert state.step == expected_field
            h.append({"query": value, "answer": r, "step": step_str, "validated": True})

        assert state.is_complete is True
        assert state.next_step == OnboardingField.COMPLETED


# =============================================================================
# TestIsOnboardingIntent — detecção de intenção (v9)
# =============================================================================

class TestIsOnboardingIntent:
    """Testes da função is_onboarding_intent."""

    @pytest.mark.parametrize("query", [
        "Quero abrir conta",
        "Preciso abrir uma conta PJ",
        "Abertura de conta",
        "Criar conta",
        "quero abrir minha conta",
    ])
    def test_detects_opening_queries(self, query):
        assert is_onboarding_intent(query, []) is True

    @pytest.mark.parametrize("query", [
        "Qual meu saldo?",
        "Oi, tudo bem?",
        "Preciso de ajuda com PIX",
        "Bom dia",
    ])
    def test_ignores_non_opening_queries(self, query):
        assert is_onboarding_intent(query, []) is False

    def test_detects_from_history_keywords(self):
        """Se o histórico contém keywords de abertura, retorna True."""
        history = [
            {"query": "Quero abrir conta", "answer": "Vamos abrir sua conta PJ!"},
        ]
        assert is_onboarding_intent("12.345.678/0001-99", history) is True

    def test_detects_from_step_in_history(self):
        """Se algum turno tem step preenchido, é onboarding."""
        history = [
            {"query": "12345678000199", "answer": "ok", "step": "cnpj", "validated": True},
        ]
        assert is_onboarding_intent("Empresa LTDA", history) is True

    def test_detects_step_even_neutral_query(self):
        """Step no history detecta onboarding mesmo com query neutra."""
        history = [
            {"query": "oi", "answer": "olá", "step": "cnpj", "validated": True},
        ]
        assert is_onboarding_intent("Bom dia", history) is True

    def test_empty_history_and_neutral_query(self):
        """Sem histórico e query neutra → não é onboarding."""
        assert is_onboarding_intent("Bom dia", []) is False

    # ── Negação: NÃO deve ativar onboarding ────────────────────────
    @pytest.mark.parametrize("query", [
        "não quero abrir conta",
        "não quero abrir conta pj",
        "Não quero criar conta",
        "nao quero abrir conta",
        "não preciso de conta",
        "não preciso abrir conta",
        "não vou abrir conta",
        "sem interesse em abrir conta",
        "cancelar abertura",
        "desistir da conta",
        "não quero mais abrir conta",
    ])
    def test_negation_does_not_trigger_onboarding(self, query):
        """Frases com negação NÃO devem ativar onboarding."""
        assert is_onboarding_intent(query, []) is False

    def test_negation_ignored_when_history_has_step(self):
        """Se history já tem step, negação é irrelevante (onboarding em andamento)."""
        history = [
            {"query": "12345678000199", "answer": "ok", "step": "cnpj", "validated": True},
        ]
        # Mesmo com negação na query, o history com step prevalece
        assert is_onboarding_intent("não quero abrir conta", history) is True


# =============================================================================
# TestOnboardingState — dataclass
# =============================================================================

class TestOnboardingState:
    """Testes do dataclass OnboardingState (v9)."""

    def test_defaults(self):
        """Defaults devem ser seguros."""
        state = OnboardingState(
            step=OnboardingField.CNPJ,
            next_step=OnboardingField.RAZAO_SOCIAL,
        )
        assert state.collected == {}
        assert state.is_complete is False
        assert state.has_validation_error is False
        assert state.validation_error == ""
        assert state.field_value == ""
        assert state.retry_count == 0
        assert state.max_retries_exceeded is False

    def test_with_all_fields(self):
        """Deve aceitar todos os campos."""
        state = OnboardingState(
            step=OnboardingField.EMAIL,
            next_step=OnboardingField.EMAIL,
            collected={"cnpj": "12345678000199"},
            is_complete=False,
            has_validation_error=True,
            validation_error="Email inválido",
            field_value="invalido",
            retry_count=2,
            max_retries_exceeded=False,
        )
        assert state.step == OnboardingField.EMAIL
        assert state.next_step == OnboardingField.EMAIL
        assert state.has_validation_error is True
        assert state.validation_error == "Email inválido"
        assert state.retry_count == 2


# =============================================================================
# TestFieldSequenceIntegration — fluxo completo campo a campo (v9)
# =============================================================================

class TestFieldSequenceIntegration:
    """Testa o fluxo completo com history enriquecido."""

    def test_full_flow_with_enriched_history(self):
        """Percorre todos os campos de WELCOME até COMPLETED."""
        field_values = [
            ("12.345.678/0001-99", "cnpj"),
            ("Empresa Teste LTDA", "razaoSocial"),
            ("Empresa Teste", "nomeFantasia"),
            ("contato@empresa.com", "email"),
            ("João da Silva Santos", "representanteName"),
            ("123.456.789-00", "representanteCpf"),
            ("(11) 99999-8888", "representantePhone"),
            ("15/03/1990", "representanteBirthDate"),
            ("123456", "password"),
            ("123456", "passwordConfirmation"),
        ]

        # 1. Welcome
        state = determine_current_field([], "Quero abrir conta")
        assert state.step == OnboardingField.WELCOME
        assert state.next_step == OnboardingField.WELCOME

        history: list[dict] = [
            {"query": "Quero abrir conta", "answer": "Vamos lá!", "step": None, "validated": None},
        ]

        # 2-11. Um campo por vez
        for i, (value, step_str) in enumerate(field_values):
            state = determine_current_field(history, value)
            expected_current = DATA_FIELDS[i]
            assert state.step == expected_current, (
                f"Turn {i + 1}: expected step={expected_current.value}, "
                f"got {state.step.value}"
            )
            if i + 1 < len(DATA_FIELDS):
                expected_next = DATA_FIELDS[i + 1]
            else:
                expected_next = OnboardingField.COMPLETED
            assert state.next_step == expected_next, (
                f"Turn {i + 1}: expected next_step={expected_next.value}, "
                f"got {state.next_step.value}"
            )
            assert state.field_value == value
            history.append({
                "query": value,
                "answer": f"Recebido {i + 1}!",
                "step": step_str,
                "validated": True,
            })

        assert state.is_complete is True
        assert len(state.collected) == 10

    def test_flow_with_bfa_validation_error(self):
        """Fluxo com BFA rejeitando CNPJ → deve repetir."""
        history: list[dict] = [
            {"query": "Quero abrir conta", "answer": "Vamos lá!", "step": None, "validated": None},
        ]

        # CNPJ enviado (formato OK) mas BFA rejeita
        state = determine_current_field(
            history,
            "12.345.678/0001-99",
            validation_error="CNPJ já cadastrado no sistema",
        )
        assert state.step == OnboardingField.CNPJ
        assert state.has_validation_error is True
        assert state.validation_error == "CNPJ já cadastrado no sistema"

    def test_completed_state_has_all_data(self):
        """No estado COMPLETED, collected deve ter os 10 campos."""
        history = _make_enriched_history(10)
        state = determine_current_field(history, "finalizar")
        assert state.is_complete is True
        assert state.next_step == OnboardingField.COMPLETED
        for field in DATA_FIELDS:
            assert field.value in state.collected, (
                f"{field.value} missing from collected"
            )
